from pathlib import Path
import pytest
from slm.restart.candidate_custody import profile,readable_files

ROOT=Path(__file__).resolve().parents[1]


def test_data_allowlist_excludes_final_sources_and_whole_execution_root():
    paths=readable_files(ROOT)
    assert all(p.is_file() for p in paths)
    assert not any('/final/' in str(p) or '/data-final/' in str(p) or '/evaluation-draft/' in str(p) for p in paths)
    assert not any('audit.sqlite' in str(p) or 'accepted-manifest' in str(p) for p in paths)
    assert ROOT/'restart/execution-v1/data-train/tokens.u16' in paths
    assert ROOT/'restart/execution-v1/data-dev/tokens.u16' in paths


@pytest.mark.parametrize('name',['arbitrary','candidate-run-v1'])
def test_output_outside_execution_directory_refused(tmp_path,name):
    output=tmp_path/name;output.mkdir()
    with pytest.raises(ValueError):profile(ROOT,output)


def test_broad_execution_write_root_refused():
    with pytest.raises(ValueError):profile(ROOT,ROOT/'restart/execution-v1')
