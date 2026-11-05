"""Create an isolated four-row role-embedding ablation; never overwrite a source."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from safetensors.numpy import load_file, save_file


ROLE_IDS = [2, 3, 4, 6]  # system, user, assistant, tool_result; NOT tool_call/EOS


def reset_roles(embedding, seed):
    result = embedding.copy()
    target_norm = float(np.median(np.linalg.norm(embedding[256:], axis=1)))
    rng = np.random.default_rng(seed)
    # Orthonormal directions, matched to ordinary-token norms; no text knowledge.
    q, _ = np.linalg.qr(rng.standard_normal((embedding.shape[1], len(ROLE_IDS))))
    result[ROLE_IDS] = (q.T * target_norm).astype(embedding.dtype)
    return result, target_norm


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(a):
    source = Path(a.source).resolve()
    output = Path(a.output).resolve()
    if output.exists():
        raise RuntimeError('Refusing to overwrite a derived checkpoint')
    before = sha(source)
    weights = load_file(str(source))
    original = weights['embed.weight']
    replacement, norm = reset_roles(original, a.seed)
    changed = np.flatnonzero(np.any(original != replacement, axis=1)).tolist()
    assert changed == ROLE_IDS
    weights['embed.weight'] = replacement
    output.mkdir(parents=True)
    save_file(weights, str(output / 'model.safetensors'))
    reloaded = load_file(str(output / 'model.safetensors'))
    assert set(reloaded) == set(weights)
    assert all(np.array_equal(weights[k], reloaded[k]) for k in weights)
    assert sha(source) == before
    manifest = {
        'kind': 'experimental_role_embedding_reset_not_trained_or_selected',
        'source': str(source), 'source_sha256': before,
        'derived_sha256': sha(output / 'model.safetensors'),
        'changed_embedding_rows': changed, 'seed': a.seed,
        'new_role_norm': norm,
        'parameters': sum(v.size for v in weights.values()),
        'limitations': ['Tied output rows also change.',
                       'Not gradient gating or an implementation of the cited papers.',
                       'High cosine similarity is not proof of the quality failure cause.',
                       'Requires matched SFT and development review before any selection.'],
    }
    (output / 'derivation.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--seed', type=int, default=2026110395)
    main(p.parse_args())
