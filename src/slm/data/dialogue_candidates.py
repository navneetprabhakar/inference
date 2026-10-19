"""Source-bound OASST dialogue candidates; no content or training approval."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import tempfile
from slm.data.build import read_source
from slm.data.partitions import verify_bundle
from slm.data.schema import make_example, digest
from slm.data.staging import canonical, metadata
from slm.data.tokenized import sha, stamp


POLICY = dict(version=1, kind='oasst-dialogue-candidates-v1', release='sample_only',
              max_paths_per_tree=4, max_messages_per_path=32, max_characters_per_path=32768,
              max_tree_bytes=8*1024*1024, max_input_bytes=512*1024*1024,
              max_trees=20000, max_messages=200000,
              node_requirements='en; deleted=false; review_result=true; synthetic=false; model_name=null; nonempty text',
              selection='Maximal eligible assistant-ended prefixes, ordered by assistant rank tuple then message IDs; at most four per tree. Rank is selection metadata, not a quality grade.',
              scope='Publisher metadata eligibility only; no verified language, privacy, content, truth or training admission.')


def node_reason(node):
    if node.get('lang') != 'en':return 'declared_non_english_or_missing'
    if node.get('deleted') is not False:return 'deleted_or_missing'
    if node.get('review_result') is not True:return 'review_rejected_or_missing'
    if node.get('synthetic') is not False or node.get('model_name') is not None:return 'synthetic_or_unknown_origin'
    if not isinstance(node.get('text'), str) or not node['text'].strip():return 'empty_text'
    return None


def extract(tree, source, projection, bundle_hash):
    """Inspect the full raw identity tree, then select unchanged valid prefixes."""
    root = tree['message_tree_id']; nodes = {}; stack = [(tree['prompt'], None, 0)]
    while stack:
        node, parent, depth = stack.pop(); key = node['message_id']
        if (not isinstance(key, str) or not key or key in nodes or depth > 128
            or node.get('parent_id') != parent or node.get('message_tree_id') not in (None, root)
            or node.get('role') != ('prompter' if depth%2 == 0 else 'assistant')
            or not isinstance(node.get('text'), str) or not isinstance(node.get('replies'), list)):
            raise ValueError('Invalid raw tree identity/role/text')
        nodes[key] = node
        stack.extend((child, key, depth+1) for child in node['replies'])
    identities = sorted((key, node['parent_id']) for key,node in nodes.items())
    if (tree.get('tree_state') != 'ready_for_export' or tree['prompt']['message_id'] != root
        or projection['messages'] != len(nodes) or projection['node_identity_sha256'] != digest(identities)
        or projection['split'] not in ('train','validation','test')):
        raise ValueError('Complete official tree projection differs')
    reasons = Counter(); candidates = []
    def walk(node, path, characters):
        reason = node_reason(node)
        if reason:
            reasons[reason] += 1
            return False
        path = path+[node['message_id']]; characters += len(node['text'])
        if len(path)>POLICY['max_messages_per_path'] or characters>POLICY['max_characters_per_path']:
            reasons['path_size_attention'] += 1
            return False
        descendant = False
        for child in sorted(node['replies'], key=lambda n:n['message_id']):
            descendant = walk(child,path,characters) or descendant
        if node['role']=='assistant':
            if not descendant:candidates.append(path)
            return True
        return descendant
    walk(tree['prompt'], [], 0)
    def order(path):
        ranks = tuple(nodes[key]['rank'] if type(nodes[key].get('rank')) is int and nodes[key]['rank']>=0 else 1000000
                      for key in path if nodes[key]['role']=='assistant')
        return ranks, tuple(path)
    selected = sorted(candidates,key=order)[:POLICY['max_paths_per_tree']]
    reasons['eligible_paths_omitted_by_tree_cap'] += max(0,len(candidates)-len(selected))
    output = []
    for path in selected:
        messages = [dict(role='user' if nodes[key]['role']=='prompter' else 'assistant',content=nodes[key]['text']) for key in path]
        proof = dict(method='oasst-official-id-projection-v1',source_revision=source.revision,
                     root_id=root,split=projection['split'],bundle_sha256=bundle_hash)
        eligibility = dict(policy_sha256=digest(POLICY),tree_sha256=digest(tree),
            raw_nodes=[dict(message_id=key,text_sha256=digest(nodes[key]['text']),
                **{field:nodes[key].get(field) for field in ('lang','deleted','review_result','review_count','rank','synthetic','model_name')}) for key in path],
            language_assessment='publisher_label_only',privacy_assessment='unverified',quality_assessment='unverified',
            content_assessment='unverified',training_eligible=False)
        output.append(make_example(source,path[-1],root,messages,official_split=projection['split'],language='en',lineage=path,
                      validation_results=dict(upstream_mapping=proof,dialogue_candidate=eligibility)).to_dict())
    return output,reasons,len(nodes),len(candidates)


def prepare(snapshot, partition_report, partition_cache, output):
    snapshot, partition_report, partition_cache, output = map(Path,(snapshot,partition_report,partition_cache,output))
    if output.exists():raise FileExistsError(output)
    source = read_source(snapshot/'source.json'); acquisition = metadata(snapshot/'acquisition.json')
    report = metadata(partition_report); mapping_path = Path(report['mapping_path'])
    mapping = metadata(mapping_path); verify_bundle(partition_cache,report['cached_projection_manifest_sha256'])
    registry = metadata(partition_cache/'registry.json'); rows = snapshot/'trees.jsonl'
    if (source.source_id!='OpenAssistant/oasst2' or source.review_status=='excluded'
        or source.revision!=acquisition['source_revision'] or source.revision!=report['source_revision']
        or source.revision!=registry['revision'] or registry['source_id']!=source.source_id
        or acquisition['decoded_sha256']!=sha(rows) or report['snapshot_sha256']!=acquisition['decoded_sha256']
        or report['mapping_sha256']!=sha(mapping_path) or report['acquisition_sha256']!=sha(snapshot/'acquisition.json')
        or rows.stat().st_size>POLICY['max_input_bytes']):
        raise ValueError('Pinned snapshot/source/projection binding differs')
    paths = [*snapshot.iterdir(), partition_report, mapping_path, Path(__file__), *partition_cache.rglob('*')]
    guards = {p.resolve():stamp(p) for p in paths if p.is_file()}
    output.parent.mkdir(parents=True,exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.dialogue-candidates-',dir=output.parent))
    try:
        counts = Counter(); splits = Counter(); turns = Counter(); seen = set(); node_count = 0; eligible = 0
        exposures = Counter(); characters = Counter()
        with rows.open('rb') as incoming,(temp/'candidates.jsonl').open('w') as out:
            while True:
                line = incoming.readline(POLICY['max_tree_bytes']+1)
                if not line:break
                if len(line)>POLICY['max_tree_bytes']:raise ValueError('Tree byte ceiling exceeded')
                tree = json.loads(line); root = tree['message_tree_id']
                if root in seen or root not in mapping:raise ValueError('Duplicate or unmapped raw tree')
                seen.add(root)
                items,reasons,n,available = extract(tree,source,mapping[root],report['cached_projection_manifest_sha256'])
                counts.update(reasons);node_count += n;eligible += available
                if len(seen)>POLICY['max_trees'] or node_count>POLICY['max_messages']:raise ValueError('Raw population ceiling exceeded')
                for item in items:
                    out.write(canonical(item)+'\n');splits[item['official_split']]+=1;turns[str(len(item['messages'])//2)]+=1
                    characters[item['official_split']]+=sum(len(m['content']) for m in item['messages'])
                    exposures.update(item['lineage'])
        if set(mapping)!=seen or node_count!=acquisition['messages'] or len(seen)!=acquisition['trees']:
            raise ValueError('Complete raw/projection coverage differs')
        if any(stamp(p)!=before for p,before in guards.items()):raise ValueError('Source/projection/code changed')
        (temp/'policy.json').write_text(json.dumps(POLICY,indent=2,sort_keys=True)+'\n')
        result = dict(creator='Navneet Prabhakar',release='sample_only',trees=len(seen),raw_messages=node_count,
            candidate_paths=sum(splits.values()),eligible_maximal_paths_before_cap=eligible,splits=dict(splits),
            characters=dict(characters),user_turn_counts=dict(turns),branch_pruning_and_cap_counts=dict(counts),
            max_shared_node_exposure=max(exposures.values(),default=0),distinct_candidate_nodes=len(exposures),
            repeated_candidate_node_occurrences=sum(exposures.values())-len(exposures),
            candidates_sha256=sha(temp/'candidates.jsonl'),snapshot_sha256=sha(rows),partition_report_sha256=sha(partition_report),
            policy_sha256=digest(POLICY),implementation_sha256=sha(__file__),training_eligible=False,
            scope='Raw unchanged English publisher-reviewed prefixes only. Pruning counts are first blocked branch roots, not all descendant messages. Candidates still require grouping, privacy/content/quality review and bounded admission.')
        (temp/'report.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        os.rename(temp,output)
        return result
    except BaseException:
        shutil.rmtree(temp,ignore_errors=True);raise


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('snapshot','partition-report','partition-cache','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.snapshot,a.partition_report,a.partition_cache,a.output),indent=2,sort_keys=True))


if __name__=='__main__':main()
