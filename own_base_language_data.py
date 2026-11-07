"""Pure metadata helpers for prospective own-base continuation; no I/O or training.

Document token spans include their admitted EOT. These helpers do not tokenize,
pack, admit sources, infer budgets, or silently repeat an exhausted stream.
"""
import bisect
import copy
import hashlib
import json
import math


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


class MixedSchedule:
    """Immutable whole-document ordering and explicit source rows per update.

    A pass exposes floor((tokens-1)/length)*length targets. Remaining tail
    positions are disclosed and never silently consumed or joined to a new pass.
    Unique exposure counts exact (source,document,token-position) ranges using
    the bounded complement omitted at complete pass boundaries.
    """
    def __init__(self, plan):
        self.plan = copy.deepcopy(plan)
        require(set(plan) == {'schema', 'seed', 'length', 'sources', 'row_source_cycle'}, 'complete schedule plan required')
        require(plan['schema'] == 1 and integer(plan['seed']), 'schema/seed')
        require(plan['length'] in (512, 1024), 'explicit 512 or 1024 layout')
        self.length = plan['length']; self.rows_per_update = 8192 // self.length
        self.sources = {}
        for source in plan['sources']:
            require(set(source) == {'name', 'passes', 'documents'}, 'source schema')
            name = source['name']
            require(isinstance(name, str) and name and name not in self.sources, 'unique source name')
            require(integer(source['passes'], 1), 'explicit finite passes')
            docs = source['documents']; seen = set()
            require(isinstance(docs, list) and docs, 'source documents required')
            for doc in docs:
                require(set(doc) == {'id', 'tokens', 'family', 'split', 'sha256'}, 'document schema')
                require(isinstance(doc['id'], str) and doc['id'] and doc['id'] not in seen, 'unique document ID within source')
                require(integer(doc['tokens'], 2) and doc['split'] == 'train', 'admitted training spans including EOT required')
                require(isinstance(doc['family'], str) and doc['family'], 'document family required')
                require(isinstance(doc['sha256'], str) and len(doc['sha256']) == 64 and all(c in '0123456789abcdef' for c in doc['sha256']), 'document content hash')
                seen.add(doc['id'])
            total = sum(d['tokens'] for d in docs)
            require(total > self.length, 'source cannot supply one shifted row')
            self.sources[name] = copy.deepcopy(source)
        cycle = plan['row_source_cycle']
        require(isinstance(cycle, list) and cycle and len(cycle) % self.rows_per_update == 0, 'whole-update source cycle required')
        require(set(cycle) == set(self.sources), 'cycle must reference every declared source and no others')
        self.identity = digest(self.plan)
        self._pass_cache = {}
        self._missing_cache = {}
        self._capacities = {}
        for name, source in self.sources.items():
            total = sum(d['tokens'] for d in source['documents']); targets = ((total-1)//self.length)*self.length
            self._capacities[name] = dict(tokens_per_pass=total, targets_per_pass=targets, unused_target_tail_per_pass=total-1-targets, maximum_targets=targets*source['passes'])

    def _ordered(self, source, epoch):
        require(source in self.sources and integer(epoch) and epoch < self.sources[source]['passes'], 'finite source pass exhausted')
        cached = self._pass_cache.get(source)
        if cached is None or cached[0] != epoch:
            docs = sorted(self.sources[source]['documents'], key=lambda d: (digest([self.plan['seed'], source, epoch, d['id']]), d['id']))
            starts = []; cursor = 0
            for doc in docs: starts.append(cursor); cursor += doc['tokens']
            cached = (epoch, docs, starts, {d['id']: offset for d, offset in zip(docs, starts)}); self._pass_cache[source] = cached
        return cached[1], cached[2]

    def order(self, source, epoch):
        return copy.deepcopy(self._ordered(source, epoch)[0])

    def capacity(self, source):
        return dict(self._capacities[source])

    def initial(self):
        return dict(plan_sha256=self.identity, updates=0, sources={name: dict(pass_index=0, offset=0, targets=0,
            unique_targets=0, repeated_targets=0) for name in self.sources})

    def spans(self, source, epoch, offset, count):
        require(integer(offset) and integer(count, 1), 'nonnegative bounded span')
        docs, starts = self._ordered(source, epoch); result = []
        index = max(0, bisect.bisect_right(starts, offset)-1)
        while index < len(docs) and starts[index] < offset + count:
            doc = docs[index]; cursor = starts[index]
            start = max(offset, cursor); end = min(offset + count, cursor + doc['tokens'])
            if end > start: result.append(dict(document=doc['id'], offset=start-cursor, count=end-start))
            index += 1
        require(sum(x['count'] for x in result) == count, 'requested span exceeds pass')
        return result

    @staticmethod
    def _overlap(a, b):
        if a['document'] != b['document']: return 0
        return max(0, min(a['offset']+a['count'], b['offset']+b['count'])-max(a['offset'], b['offset']))

    def _missing_after(self, source, completed_passes):
        # Each complete pass leaves at most length target positions unseen:
        # its first input token plus its disclosed final partial-row tail.
        require(integer(completed_passes, 1), 'positive completed passes')
        cap = self._capacities[source]
        for count in range(1, completed_passes+1):
            key = (source, count)
            if key in self._missing_cache: continue
            prior = self._missing_cache.get((source, count-1))
            if prior == []: self._missing_cache[key] = []; continue
            omitted = self.spans(source,count-1,0,1)
            tail = cap['unused_target_tail_per_pass']
            if tail: omitted += self.spans(source,count-1,cap['targets_per_pass']+1,tail)
            if prior is None: remaining = omitted
            else:
                remaining = [dict(document=a['document'],offset=max(a['offset'],b['offset']),count=self._overlap(a,b))
                             for a in prior for b in omitted if self._overlap(a,b)]
            self._missing_cache[key] = remaining
        return self._missing_cache[(source,completed_passes)]

    def _unique_total(self, source, epoch, offset):
        if epoch == 0: return offset
        missing = self._missing_after(source,epoch); self._ordered(source,epoch)
        starts = self._pass_cache[source][3]
        added = sum(max(0,min(starts[x['document']]+x['offset']+x['count'],offset+1)-max(starts[x['document']]+x['offset'],1)) for x in missing)
        return self._capacities[source]['tokens_per_pass']-sum(x['count'] for x in missing)+added

    def next_update(self, state):
        require(state.get('plan_sha256') == self.identity and integer(state.get('updates')), 'schedule state identity')
        require(set(state['sources']) == set(self.sources), 'source cursor inventory')
        nxt = copy.deepcopy(state); rows = []; cycle = self.plan['row_source_cycle']
        for index in range(self.rows_per_update):
            name = cycle[(state['updates'] * self.rows_per_update + index) % len(cycle)]
            cur = nxt['sources'][name]; cap = self.capacity(name)
            require(cur['targets'] == cur['pass_index'] * cap['targets_per_pass'] + cur['offset'], 'source cursor/targets mismatch')
            require(cur['offset'] % self.length == 0 and 0 <= cur['offset'] <= cap['targets_per_pass'], 'source row alignment')
            if cur['offset'] == cap['targets_per_pass']:
                cur['pass_index'] += 1; cur['offset'] = 0
            require(cur['pass_index'] < self.sources[name]['passes'], 'finite source passes exhausted; no wrap')
            missing = self._missing_after(name,cur['pass_index']) if cur['pass_index'] else None
            spans = self.spans(name, cur['pass_index'], cur['offset'], self.length + 1)
            targets = self.spans(name, cur['pass_index'], cur['offset'] + 1, self.length)
            unique = self.length if cur['pass_index'] == 0 else sum(self._overlap(span, omitted) for span in targets for omitted in missing)
            rows.append(dict(source=name, pass_index=cur['pass_index'], offset=cur['offset'], input_spans=spans,
                             target_spans=targets, targets=self.length, unique_targets=unique, repeated_targets=self.length-unique))
            cur['offset'] += self.length; cur['targets'] += self.length
            cur['unique_targets'] += unique; cur['repeated_targets'] += self.length-unique
        nxt['updates'] += 1
        return rows, nxt

    def state_at(self, updates):
        """Reconstruct counters from cycle arithmetic and pass boundary omissions.

        Cost depends on documents/passes, never on optimizer-update history.
        No materialized per-token exposure set is stored in checkpoints.
        """
        require(integer(updates), 'invalid update cursor')
        require(updates <= sum(c['maximum_targets'] for c in self._capacities.values())//8192, 'resume exceeds finite source capacity')
        expected = self.initial(); expected['updates'] = updates
        cycle = self.plan['row_source_cycle']; whole, remainder = divmod(updates*self.rows_per_update,len(cycle))
        for name in self.sources:
            targets = (whole*cycle.count(name)+cycle[:remainder].count(name))*self.length
            cap = self._capacities[name]; require(targets <= cap['maximum_targets'], 'source schedule exceeds finite passes')
            epoch = (targets-1)//cap['targets_per_pass'] if targets else 0
            offset = targets-epoch*cap['targets_per_pass']; unique = self._unique_total(name,epoch,offset)
            expected['sources'][name] = dict(pass_index=epoch,offset=offset,targets=targets,unique_targets=unique,repeated_targets=targets-unique)
        return expected

    def validate_resume(self, state):
        require(state == self.state_at(state.get('updates')), 'resume schedule/exposure state differs')
        return True


def validation_manifest(documents, windows, maximum_targets=512):
    """Freeze one unpadded window per held-out document; never filter by length."""
    require(integer(maximum_targets, 32) and maximum_targets <= 1024, 'validation maximum')
    index = {}
    for doc in documents:
        key = (doc['source'], doc['id'])
        require(key not in index and doc['split'] in ('validation', 'exposed-development'), 'held-out unique document required')
        require(integer(doc['tokens'], 33), 'document too short for minimum window')
        require(isinstance(doc.get('sha256'), str) and len(doc['sha256']) == 64 and all(c in '0123456789abcdef' for c in doc['sha256']), 'validation document content hash')
        index[key] = doc
    selected = set(); result = []
    for window in windows:
        require(set(window) == {'source', 'id', 'offset', 'targets'}, 'validation window schema')
        key = (window['source'], window['id']); require(key in index and key not in selected, 'one window per known document')
        require(integer(window['offset']) and integer(window['targets'], 32) and window['targets'] <= maximum_targets, 'window length/offset')
        require(window['offset'] + window['targets'] < index[key]['tokens'], 'shifted window crosses document boundary')
        selected.add(key); result.append(dict(window, stratum='short' if window['targets'] < 128 else 'long', document_sha256=index[key]['sha256']))
    require(result, 'nonempty explicit validation selection')
    coverage = {name: dict(eligible_documents=sum(k[0] == name for k in index), selected_documents=sum(w['source'] == name for w in result), short_windows=sum(w['source'] == name and w['stratum'] == 'short' for w in result), long_windows=sum(w['source'] == name and w['stratum'] == 'long' for w in result)) for name in sorted({k[0] for k in index})}
    body = dict(schema=1, maximum_targets=maximum_targets, windows=result, coverage_by_source=coverage,
                eligible_documents=len(index), selected_documents=len(result), evaluation_targets=sum(w['targets'] for w in result))
    return dict(body, sha256=digest(body))


def aggregate_validation(manifest, results):
    """Results supply summed NLL, never padded mean loss; no model dependency."""
    body = {k:v for k,v in manifest.items() if k != 'sha256'}
    require(digest(body) == manifest['sha256'], 'validation manifest hash')
    require(len(results) == len(manifest['windows']), 'complete validation results required')
    groups = {}; documents = []
    for window, row in zip(manifest['windows'], results):
        require(set(row) == {'source','id','targets','nll'} and all(row[k] == window[k] for k in ('source','id','targets')), 'validation order/identity/target mismatch')
        require(isinstance(row['nll'], (int,float)) and not isinstance(row['nll'],bool) and math.isfinite(row['nll']) and row['nll'] >= 0, 'finite summed NLL required')
        documents.append(dict(row, mean_ce=row['nll']/row['targets']))
        for key in (row['source']+'/all', row['source']+'/'+window['stratum']): groups.setdefault(key, []).append(documents[-1])
    return dict(manifest_sha256=manifest['sha256'], documents=documents, groups={key:dict(documents=len(rows),
        targets=sum(r['targets'] for r in rows), summed_nll=sum(r['nll'] for r in rows),
        document_mean_ce=sum(r['mean_ce'] for r in rows)/len(rows),
        token_mean_ce=sum(r['nll'] for r in rows)/sum(r['targets'] for r in rows)) for key,rows in groups.items()})
