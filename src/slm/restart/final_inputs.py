"""Final-suite loader; intentionally separate from development worker loaders."""
import hashlib,json
from .evaluation_snapshot import MANIFEST_SHA256,_file


def load(project,suite):
    if suite not in ('grammar','grounded','narrative','copy'):raise ValueError('Unknown final suite')
    root=project/'restart/execution-v1/evaluation-frozen-v1'
    raw=_file(root,'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA256:raise ValueError('Changed frozen evaluation manifest')
    manifest=json.loads(raw);relative='final/'+suite+'.jsonl';raw=_file(root,relative).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest['files_sha256'][relative]:raise ValueError('Changed final suite')
    rows=[json.loads(line) for line in raw.splitlines()];key='pair_id' if suite=='copy' else 'id'
    expected=200 if suite=='grammar' else 100
    if (len(rows)!=expected or len({r[key] for r in rows})!=expected
            or any(not r[key].startswith('final:') for r in rows)):
        raise ValueError('Invalid final denominator or identity')
    if suite in ('grammar','grounded') and any(r['split']!='final' for r in rows):raise ValueError('Wrong final split')
    return rows
