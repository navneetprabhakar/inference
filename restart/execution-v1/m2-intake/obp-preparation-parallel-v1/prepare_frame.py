"""Offline metadata selection only. Never downloads, clears rights, or admits text."""
import argparse
import hashlib
import json
import uuid
from pathlib import Path
from urllib.parse import urlsplit

SEED = 'm2-obp-native-epub-pilot-v1'
ALLOWED = {'creativecommons.org/licenses/by/4.0', 'creativecommons.org/publicdomain/zero/1.0'}
ALLOWED_TYPES = {'MONOGRAPH', 'EDITED_BOOK', 'TEXTBOOK'}

def digest(value):
    return hashlib.sha256(value).hexdigest()

def license_key(value):
    if not isinstance(value, str):
        return None
    url = urlsplit(value)
    if url.scheme not in {'http', 'https'} or url.query or url.fragment:
        return None
    if url.username or url.password or url.port:
        return None
    return (url.hostname or '').lower() + url.path.rstrip('/').lower()

def evaluate(work):
    reasons = []
    try:
        identity = str(uuid.UUID(work['workId']))
    except (KeyError, ValueError, TypeError):
        return None, ['missing_or_invalid_work_uuid']
    if work.get('workStatus') != 'ACTIVE' or work.get('withdrawnDate'):
        reasons.append('not_active_or_withdrawn')
    if work.get('workType') not in ALLOWED_TYPES:
        reasons.append('not_supported_book_type')
    if license_key(work.get('license')) not in ALLOWED:
        reasons.append('license_not_exact_ccby4_or_cc0')
    languages = work.get('languages')
    if not isinstance(languages, list) or not languages or any(x.get('languageCode') != 'ENG' for x in languages):
        reasons.append('missing_or_nonexclusive_english_language')
    publisher = work.get('imprint', {}).get('publisher', {}).get('publisherName')
    if publisher != 'Open Book Publishers':
        reasons.append('publisher_not_bound')
    doi = work.get('doi')
    if not isinstance(doi, str) or not doi.lower().removeprefix('https://doi.org/').removeprefix('http://doi.org/').startswith('10.11647/obp.'):
        reasons.append('missing_obp_doi')
    titles = [x['fullTitle'] for x in work.get('titles', []) if x.get('canonical') and x.get('localeCode') in {'EN', 'EN-GB', 'EN-US'} and x.get('fullTitle')]
    if len(titles) != 1:
        reasons.append('missing_or_ambiguous_canonical_english_title')
    urls = set()
    for publication in work.get('publications', []):
        if publication.get('publicationType') != 'EPUB':
            continue
        for location in publication.get('locations', []):
            if location.get('canonical') is not True:
                continue
            value = location.get('fullTextUrl') or ''
            split = urlsplit(value)
            if split.scheme == 'https' and split.hostname == 'books.openbookpublishers.com' and not split.query and not split.fragment and split.path.lower().endswith('.epub') and not split.username and not split.password and not split.port:
                urls.add(value)
    if len(urls) != 1:
        reasons.append('missing_or_ambiguous_native_canonical_epub')
    for relation in work.get('relations', []):
        if relation.get('relationType') != 'HAS_CHILD':
            continue
        chapter = relation.get('relatedWork')
        if not isinstance(chapter, dict) or license_key(chapter.get('license')) not in ALLOWED:
            reasons.append('child_license_missing_or_incompatible')
            break
        if chapter.get('workStatus') != 'ACTIVE' or chapter.get('withdrawnDate'):
            reasons.append('child_not_active_or_withdrawn')
            break
    if reasons:
        return None, sorted(set(reasons))
    return {'work_id': identity, 'title': titles[0], 'doi': doi, 'edition': work.get('edition'), 'license': work['license'], 'epub_url': next(iter(urls)), 'metadata_record_sha256': digest(json.dumps(work, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()), 'order_key': digest((SEED+'\n'+identity).encode()), 'family': doi.lower().removeprefix('https://doi.org/').removeprefix('http://doi.org/'), 'genre': None, 'license_artifact_verification': 'PENDING', 'admitted': False}, []

def build(records, excluded_work_ids=(), limit=40):
    if not isinstance(records, list) or not all(isinstance(x, dict) for x in records):
        raise ValueError('Expected explicit list of work dictionaries')
    if not 1 <= limit <= 40:
        raise ValueError('Pilot limit must be1..40')
    seen, seen_dois = set(), set()
    eligible, exclusions = [], []
    for work in records:
        row, reasons = evaluate(work)
        identity = work.get('workId')
        if identity in seen:
            raise ValueError('Duplicate work UUID in metadata frame')
        seen.add(identity)
        if row and identity in excluded_work_ids:
            row, reasons = None, ['discovery_work_excluded_from_fresh_acceptance_frame']
        if row:
            if row['family'] in seen_dois:
                raise ValueError('Duplicate DOI family requires edition reconciliation')
            seen_dois.add(row['family'])
            eligible.append(row)
        else:
            exclusions.append({'work_id': identity, 'reasons': reasons})
    eligible.sort(key=lambda x: (x['order_key'], x['work_id']))
    return {'status': 'METADATA_CANDIDATES_ONLY', 'selection_seed': SEED, 'raw_records': len(records), 'eligible_records': len(eligible), 'eligible_frame': eligible, 'exclusions': exclusions, 'selected': eligible[:limit], 'usable_documents': 0, 'usable_tokens': 0, 'frame_complete': False, 'frame_completeness_note': 'Caller must provide complete timestamped publisher export and verify expected publisher/coverage; successful parsing does not certify completeness.'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exclude-work', action='append', default=[])
    parser.add_argument('--limit', type=int, default=40)
    args = parser.parse_args()
    raw = args.metadata.read_bytes()
    obj = json.loads(raw)
    records = obj if isinstance(obj, list) else obj.get('works') if isinstance(obj, dict) else None
    result = build(records, args.exclude_work, args.limit)
    result['metadata_file_sha256'] = digest(raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        handle.write(json.dumps(result, indent=2, ensure_ascii=False)+'\n')

if __name__ == '__main__':
    main()
