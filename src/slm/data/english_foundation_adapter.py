"""Private foundation-only category adapter over unchanged finite data engines.

Isolated module namespaces keep the original conversation-category registry and
readers unchanged. Scheduling, token accounting and numerical training are reused.
"""
# Creator: Navneet Prabhakar
import importlib.util
import json
from pathlib import Path
from slm.data import mixture as original_mixture, curriculum as original_curriculum
from slm.data.stream_hash import sha


def isolated(module, name):
    spec = importlib.util.spec_from_file_location(name, module.__file__)
    instance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instance)
    return instance


_mixture = isolated(original_mixture, '_private_english_mixture_v1')
_mixture.CATEGORIES = frozenset({'unreviewed'})


def check_manifest(path, kind):
    manifest = json.loads((Path(path) / 'manifest.json').read_text())
    if manifest.get('english_foundation_adapter_sha256') != sha(__file__):
        raise ValueError('Pinned private foundation category adapter required')
    if kind == 'mixture' and (manifest.get('objective') != 'foundation'
                            or manifest.get('allowed_categories') != ['unreviewed']):
        raise ValueError('Unreviewed data is restricted to private foundation research')


def bind_adapter(output, result):
    path = Path(output) / 'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['english_foundation_adapter_sha256'] = sha(__file__)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    temp.replace(path)
    return {**result, 'dataset_hash': sha(path)}


def build_mixture(components, tokenizer, output, **kwargs):
    if kwargs.get('objective') != 'foundation' or tuple(kwargs.get('allowed_categories', ())) != ('unreviewed',):
        raise ValueError('Explicit unreviewed private foundation scope required')
    return bind_adapter(output, _mixture.build_mixture(components, tokenizer, output, **kwargs))


class FoundationMixtureBatches(_mixture.MixtureBatches):
    def __init__(self, path, components, tokenizer, expected_fingerprint=None):
        check_manifest(path, 'mixture')
        super().__init__(path, components, tokenizer, expected_fingerprint)


_curriculum = isolated(original_curriculum, '_private_english_curriculum_v1')
_curriculum.MixtureBatches = FoundationMixtureBatches


def build_curriculum(stages, tokenizer, output, **kwargs):
    return bind_adapter(output, _curriculum.build_curriculum(stages, tokenizer, output, **kwargs))


class CurriculumBatches(original_curriculum.CurriculumBatches):
    # Preserve the original trainer's isinstance contract and all original methods.
    # Only construction resolves stages through the isolated foundation reader.
    def __init__(self, path, bindings, tokenizer, expected_fingerprint=None):
        check_manifest(path, 'curriculum')
        _curriculum.CurriculumBatches.__init__(self, path, bindings, tokenizer, expected_fingerprint)
