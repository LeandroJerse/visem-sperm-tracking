"""Synthetic checks of independent audit arithmetic and historical QA schema."""
import copy

import pytest

from script.flow.test.verify_causal_smoke import Audit, parent_qa_references, self_test


def test_independent_numeric_controls_do_not_read_experiments():
    result = self_test()
    assert result["status"] == "passed"
    assert result["experiment_artifacts_read"] is False


def records(root):
    parent = root / "data/derived/reference/manifest.json"
    artifact = parent.parent / "observations.csv"
    return parent, [{"path": str(path), "sha256": digest * 64, "bytes": size,
                     "mtime_ns": 123456, "expected_hash_verified": flag}
                    for path, digest, size, flag in ((parent, "a", 100, False), (artifact, "b", 50, True))]


def test_parent_qa_evidence_fields_are_checked_without_opening_files(tmp_path):
    parent, inputs = records(tmp_path)
    audit = Audit(tmp_path)
    got = parent_qa_references(audit, inputs, parent)
    assert got == [{k: r[k] for k in ("path", "sha256", "bytes")} for r in inputs]
    assert not audit.files


@pytest.mark.parametrize("fault", ["extra", "missing", "parent_flag", "artifact_flag", "flag_type", "mtime_type", "negative_mtime"])
def test_malformed_qa_evidence_is_rejected(tmp_path, fault):
    parent, inputs = records(tmp_path)
    rows = copy.deepcopy(inputs)
    if fault == "extra":
        rows[0]["extra"] = 1
    elif fault == "missing":
        del rows[0]["mtime_ns"]
    elif fault == "parent_flag":
        rows[0]["expected_hash_verified"] = True
    elif fault == "artifact_flag":
        rows[1]["expected_hash_verified"] = False
    elif fault == "flag_type":
        rows[1]["expected_hash_verified"] = 1
    elif fault == "mtime_type":
        rows[0]["mtime_ns"] = 1.2
    else:
        rows[0]["mtime_ns"] = -1
    with pytest.raises(ValueError):
        parent_qa_references(Audit(tmp_path), rows, parent)
