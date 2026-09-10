"""Independent compact audit checks built only from disposable synthetic data."""
from __future__ import annotations

import csv
import hashlib
import json

import numpy as np
import pytest

from script.flow.test.verify_compact_benchmark import (
    Audit, VIDEOS, canonical_sample_id, diagnostics, independent_witness,
    parent_qa_references, parse_json, projection, rebuild_coverage, verify_video,
)
import script.flow.test.verify_compact_benchmark as verifier


def witness(points=None):
    if points is None:
        points = np.array([[0.25, 0.75], [1, 1], [0, 0], [-1e-12, 0]], dtype=np.float64)
    points = np.asarray(points, dtype=np.float64)
    field = np.array([[[2, 3], [4, 2]], [[5, 7], [7, 6]]], dtype=np.float32)
    xy = np.full((len(points), 4, 2), -1, dtype=np.int64)
    uv = np.full((len(points), 4, 2), np.nan, dtype=np.float32)
    valid = np.zeros((len(points), 4), dtype=bool)
    inside = np.zeros(len(points), dtype=bool)
    for index, (x, y) in enumerate(points):
        if 0 <= x <= 1 and 0 <= y <= 1:
            inside[index] = True
            x0, y0 = int(x), int(y)
            corners = ((x0, y0), (min(x0 + 1, 1), y0), (x0, min(y0 + 1, 1)), (min(x0 + 1, 1), min(y0 + 1, 1)))
            xy[index] = corners
            uv[index] = [field[row, col] for col, row in corners]
            valid[index] = True
    return [points, xy, uv, valid, inside]


def rebuild(arrays):
    return independent_witness(*arrays, width=2, height=2)


def test_witness_reconstruction_matches_analytic_affine_field():
    arrays = witness()
    values, valid, reasons = rebuild(arrays)
    points = arrays[0][:3]
    expected = np.column_stack((2 + 2 * points[:, 0] + 3 * points[:, 1],
                                3 - points[:, 0] + 4 * points[:, 1]))
    np.testing.assert_array_equal(values[:3], expected)
    assert valid.tolist() == [True, True, True, False]
    assert reasons == ["", "", "", "outside_image"]
    assert np.isnan(values[3]).all()


def test_zero_weight_invalid_corner_is_ignored_but_positive_tiny_weight_is_not():
    arrays = witness([[0, 0], [1e-12, 1e-12]])
    arrays[2][:, 3] = np.nan
    arrays[3][:, 3] = False
    values, valid, reasons = rebuild(arrays)
    assert valid.tolist() == [True, False]
    np.testing.assert_array_equal(values[0], [2, 3])
    assert np.isnan(values[1]).all()
    assert reasons == ["", "invalid_contributor"]


def test_nonfinite_positive_corner_is_invalid_even_when_flag_claims_validity():
    arrays = witness([[0.5, 0.5]])
    arrays[2][0, 1, 0] = np.inf
    values, valid, reasons = rebuild(arrays)
    assert not valid[0] and np.isnan(values).all() and reasons == ["invalid_contributor"]


@pytest.mark.parametrize("array_index,value", [(1, 0), (2, 0), (3, True), (4, True)])
def test_outside_sentinel_tampering_is_rejected(array_index, value):
    arrays = witness([[-1e-12, 0]])
    arrays[array_index][0] = value
    with pytest.raises(ValueError):
        rebuild(arrays)


@pytest.mark.parametrize("corner", range(4))
def test_witness_corner_geometry_must_match_source_coordinate(corner):
    arrays = witness([[0.25, 0.75]])
    arrays[1][0, corner, 0] += 1
    with pytest.raises(ValueError, match="geometry"):
        rebuild(arrays)


@pytest.mark.parametrize("array_index,dtype", [(0, np.float32), (1, np.int32), (2, np.float64), (3, np.int8), (4, np.int8)])
def test_witness_storage_dtypes_are_exact(array_index, dtype):
    arrays = witness()
    arrays[array_index] = arrays[array_index].astype(dtype)
    with pytest.raises(ValueError):
        rebuild(arrays)


def test_witness_contract_accepts_empty_request_set_for_one_pair():
    arrays = witness(np.empty((0, 2)))
    values, valid, reasons = rebuild(arrays)
    assert values.shape == (0, 2) and valid.shape == (0,) and reasons == []


def test_sample_hash_uses_named_video_original_id_segment_and_source_frame():
    key = ["11", "003", "s_2", 17]
    expected = hashlib.sha256(json.dumps(key, separators=(",", ":")).encode()).hexdigest()
    assert canonical_sample_id(*key) == expected
    assert len({canonical_sample_id("11", "003", "s_2", 17),
                canonical_sample_id("12", "003", "s_2", 17),
                canonical_sample_id("11", "3", "s_2", 17),
                canonical_sample_id("11", "003", "s_3", 17),
                canonical_sample_id("11", "003", "s_2", 18)}) == 5


def fixture_projection():
    plan = {"sources": {video: {"full_unique_samples": 20, "full_windows": 30,
                               "total_frames": 119} for video in VIDEOS},
            "projection": {"max_projected_seconds": 7200, "max_projected_artifact_mb": 4096}}
    rows = [{"video_id": video, "unique_samples": 10, "windows": 10,
             "loop_seconds": 3.0, "table_seconds": 5.0, "checkpoint_seconds": 7.0,
             "compact_bytes": 11, "checkpoint_bytes": 13} for video in VIDEOS]
    return plan, rows


def test_projection_scales_named_cost_components_with_single_fixed_overhead():
    plan, rows = fixture_projection()
    result = projection(plan, rows, 197)
    assert result["projected_seconds"] == 2 * (17 + 12 * (3 * 2 + 5 * 3 + 7))
    assert result["projected_artifact_bytes"] == 2 * 12 * (11 * 3 + 13) + 16 * 1024**2
    assert result["status"] == "provisional_within_budget"
    assert result["full_rss_certified"] is False
    assert result["full_extraction_released"] is False


def test_projection_uses_request_scaling_when_it_dominates_both_components():
    plan, rows = fixture_projection()
    plan["sources"]["11"]["full_unique_samples"] = 100
    result = projection(plan, rows, 180)
    first = result["terms"][0]
    assert first["loop_scale"] == 10 and first["table_scale"] == 10
    assert first["variable_seconds"] == 3 * 10 + 5 * 10 + 7


def test_projection_accounts_for_full_frame_and_pair_indexes_when_windows_are_dense():
    plan, rows = fixture_projection()
    plan["sources"]["11"]["total_frames"] = 1200
    result = projection(plan, rows, 180)
    first = result["terms"][0]
    assert first["table_scale"] == max(3, 2, 1200 / 60, 1199 / 59)
    assert first["loop_scale"] == 1199 / 59


@pytest.mark.parametrize("field", ["unique_samples", "windows"])
def test_zero_denominator_refuses_a_cost_gate(field):
    plan, rows = fixture_projection()
    rows[0][field] = 0
    with pytest.raises(ValueError, match="Zero denominator"):
        projection(plan, rows, 197)


@pytest.mark.parametrize("gate", ["max_projected_seconds", "max_projected_artifact_mb"])
def test_projection_refuses_each_exceeded_budget(gate):
    plan, rows = fixture_projection()
    plan["projection"][gate] = 0
    assert projection(plan, rows, 197)["status"] == "exceeds_planning_budget"


def test_projection_rejects_nonregistered_cohort_or_duplicate_video():
    plan, rows = fixture_projection()
    rows[1]["video_id"] = "11"
    with pytest.raises(ValueError, match="cohort"):
        projection(plan, rows, 197)


def coverage_fixture():
    windows = [{"window_id": "w", "video_id": "11", "track_id": "track", "segment_id": "segment", "origin_frame": "19"}]
    requests = [{"sample_id": str(index)} for index in range(19)]
    links = [{"window_id": "w", "sample_ids": [row["sample_id"] for row in requests]}]
    features = [{**row, "valid": index != 0, "reason": "outside_image" if index == 0 else ""}
                for index, row in enumerate(requests)]
    rows = [{**windows[0], "sample_count": "19", "valid_history19": "18", "valid_last5": "5",
             "eligible_last5": "True", "invalid_reasons_history19": '{"outside_image":1}',
             "invalid_reasons_last5": "{}"}]
    return windows, requests, links, features, rows


def test_older_invalid_sample_is_reported_without_excluding_last5_cohort():
    result = rebuild_coverage(Audit(), *coverage_fixture())
    assert result == {"historical_uses": 19, "valid_historical_uses": 18,
                      "invalid_historical_uses": 1, "eligible_last5_windows": 1,
                      "ineligible_last5_windows": 0}


@pytest.mark.parametrize("field,value", [("valid_history19", "19"), ("valid_last5", "4"), ("eligible_last5", "False"),
                                         ("sample_count", "18"), ("invalid_reasons_history19", "[]")])
def test_coverage_count_and_reason_tampering_is_rejected(field, value):
    arguments = coverage_fixture()
    arguments[-1][0][field] = value
    with pytest.raises(ValueError):
        rebuild_coverage(Audit(), *arguments)


def test_diagnostics_keep_common_photometric_support_and_known_translation_direction():
    y, x = np.indices((4, 5))
    source = (x * 3 + y * 7).astype(np.uint8)
    following = np.zeros_like(source)
    following[:, 1:] = source[:, :-1]
    forward = np.zeros((4, 5, 2), dtype=np.float32)
    forward[..., 0] = 1
    validity = np.ones((4, 5), dtype=bool)
    result = diagnostics(source, following, forward, -forward, validity, validity)
    assert result["photometric_warp_mae"] == 0 and result["forward_backward_mae"] == 0
    assert result["photometric_valid_pixels"] == result["forward_backward_valid_pixels"] == 16
    expected_zero = np.abs(source[:, :-1].astype(float) - following[:, :-1]).mean() / 255
    assert result["photometric_zero_mae"] == expected_zero


def test_audit_rejects_raw_sources_unregistered_files_and_json_duplicates(tmp_path):
    audit = Audit(tmp_path)
    for operation in (lambda: audit.path("data/sources/anything.json"),
                      lambda: audit.read("data/derived/unregistered.json"),
                      lambda: parse_json(b'{"x":1,"x":2}'),
                      lambda: parse_json(b'{"x":NaN}')):
        with pytest.raises(ValueError):
            operation()


def test_parent_qa_five_field_schema_remains_strict_and_requires_no_reads(tmp_path):
    audit = Audit(tmp_path)
    parent = tmp_path / "data/derived/reference/manifest.json"
    records = [{"path": str(parent), "sha256": "a" * 64, "bytes": 10,
                "mtime_ns": 123, "expected_hash_verified": False}]
    assert parent_qa_references(audit, records, parent) == [{key: records[0][key] for key in ("path", "sha256", "bytes")}]
    records[0]["expected_hash_verified"] = True
    with pytest.raises(ValueError):
        parent_qa_references(audit, records, parent)
    assert not audit.files


def test_absolute_tolerance_does_not_become_relative_for_large_numbers():
    audit = Audit()
    audit.near(1 + 5e-10, 1, "acceptable")
    with pytest.raises(ValueError):
        audit.near(1e8 + 1e-6, 1e8, "not relative")
    with pytest.raises(ValueError):
        audit.coordinate(1 + 1e-15, 1, "exact historical coordinate")


def synthetic_video_fixture(root):
    """Build the exported video schema without a decoder or project imports."""
    run, parent = root / "data/tests/run", root / "data/derived/reference"
    folder, parent_video = run / "by_video/11", parent / "by_video/11"
    folder.mkdir(parents=True)
    parent_video.mkdir(parents=True)
    artifacts = {}

    def reference(path):
        data = path.read_bytes()
        return {"path": str(path.relative_to(root)), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

    def csv_file(path, rows):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def json_file(path, value):
        path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
        return path

    window = {"window_id": "window", "video_id": "11", "track_id": "track", "segment_id": "segment",
              "split": "train", "history_start": 0, "origin_frame": 19, "future_end": 29,
              "history_length": 20, "forecast_horizon": 10}
    csv_file(parent_video / "windows.csv", [window])
    csv_file(parent_video / "observations.csv", [{"video_id": "11", "track_id": "track", "segment_id": "segment",
        "frame_index": frame, "cx": 0.25, "cy": 0.75, "annotated": True, "class_id": 0} for frame in range(20)])
    csv_file(folder / "selected_windows.csv", [window])
    requests = [{"sample_id": canonical_sample_id("11", "track", "segment", frame), "video_id": "11",
                 "track_id": "track", "segment_id": "segment", "frame_from": frame, "frame_to": frame + 1,
                 "cx": 0.25, "cy": 0.75} for frame in range(19)]
    csv_file(folder / "requests.csv", requests)
    csv_file(folder / "links.csv", [{"window_id": "window", "sample_ids": json.dumps([row["sample_id"] for row in requests])}])
    csv_file(folder / "features.csv", [{**row, "u": 0.5, "v": -0.25, "valid": True, "reason": ""} for row in requests])
    csv_file(folder / "window_coverage.csv", [{"window_id": "window", "video_id": "11", "track_id": "track", "segment_id": "segment",
        "origin_frame": 19, "sample_count": 19, "valid_history19": 19, "valid_last5": 5,
        "eligible_last5": True, "invalid_reasons_history19": "{}", "invalid_reasons_last5": "{}"}])
    identity = {"schema_version": 1, "video_id": "11", "source_sha256": "a" * 64, "estimator_hash": "b" * 64,
                "width": 640, "height": 480}
    arrays = witness(np.tile([0.25, 0.75], (19, 1)))
    arrays[2][:] = [0.5, -0.25]
    np.savez_compressed(folder / "witnesses.npz", metadata=np.asarray(json.dumps(identity)),
        sample_ids=np.asarray([row["sample_id"] for row in requests], dtype="U64"), points_xy=arrays[0],
        corners_xy=arrays[1], corner_uv=arrays[2], corner_valid=arrays[3], inside=arrays[4])
    gray = np.zeros((480, 640), dtype=np.uint8)
    flow = np.tile(np.array([0.5, -0.25], dtype=np.float32), (480, 640, 1))
    validity = np.ones((480, 640), dtype=bool)
    (folder / "frames").mkdir()
    frames = []
    for frame in range(60):
        row = {"frame_index": frame, "gray_sha256": hashlib.sha256(gray.tobytes()).hexdigest()}
        if frame in (0, 1, 58, 59):
            path = folder / "frames" / f"{frame:06d}.npy"
            np.save(path, gray, allow_pickle=False)
            row["artifact"] = reference(path)
        frames.append(row)
    json_file(folder / "frame_index.json", {**identity, "backend": "synthetic", "frames": frames,
        "last_frame_returned": 59, "full_video_decoding_verified": False})
    (folder / "checkpoints").mkdir()
    pairs, diagnostic_rows = [], []
    for frame in range(59):
        row = {"frame_from": frame, "frame_to": frame + 1,
               "forward_sha256": hashlib.sha256(flow.tobytes() + validity.tobytes()).hexdigest()}
        if frame in (0, 58):
            path = folder / "checkpoints" / f"{frame:06d}_{frame + 1:06d}.npz"
            pair_identity = {**identity, "frame_from": frame, "frame_to": frame + 1}
            np.savez_compressed(path, metadata=np.asarray(json.dumps(pair_identity)), forward=flow,
                                backward=-flow, forward_valid=validity, backward_valid=validity)
            row["checkpoint"] = {"path": path.name, "sha256": reference(path)["sha256"],
                                 **{key: value for key, value in pair_identity.items() if key != "schema_version"}}
            diagnostic_rows.append({"video_id": "11", "frame_from": frame, "frame_to": frame + 1,
                                    **diagnostics(gray, gray, flow, -flow, validity, validity)})
        pairs.append(row)
    json_file(folder / "pair_index.json", {**identity, "pairs": pairs})
    csv_file(folder / "checkpoint_metrics.csv", diagnostic_rows)
    compact_bytes = sum(path.stat().st_size for path in folder.iterdir() if path.is_file())
    checkpoint_bytes = sum(path.stat().st_size for path in folder.rglob("*") if path.is_file()) - compact_bytes
    summary = {"video_id": "11", "frames": 60, "forward_fields": 59, "backward_fields": 2,
        "windows": 1, "unique_samples": 19, "historical_uses": 19, "valid_samples": 19,
        "eligible_last5_windows": 1, "loop_seconds": 1.0, "checkpoint_seconds": 2.0,
        "table_seconds": 3.0, "checkpoint_bytes": checkpoint_bytes, "compact_bytes": compact_bytes}
    json_file(folder / "summary.json", summary)
    artifacts.update({path: reference(path) for path in folder.rglob("*") if path.is_file()})
    audit = Audit(root)
    audit.allow([*artifacts, parent_video / "windows.csv", parent_video / "observations.csv"])
    for record in artifacts.values():
        audit.reference(record)
    plan = {"sources": {"11": {"sha256": "a" * 64, "full_windows": 1, "full_segments_with_windows": 1,
                               "full_unique_samples": 19}}}
    return audit, parent, run, plan, artifacts, folder


def test_complete_synthetic_video_exports_reconcile_with_independent_reconstruction(tmp_path):
    audit, parent, run, plan, artifacts, _ = synthetic_video_fixture(tmp_path)
    summary, coverage = verify_video(audit, parent, run, "11", plan, "b" * 64, artifacts)
    assert summary["windows"] == 1 and summary["unique_samples"] == 19
    assert coverage["checkpoint_samples_compared_to_dense_fields"] == 1
    assert coverage["witness_corners_verified"] == 76
    assert audit.pair_pixels_diagnosed == 2 * 480 * 640
    assert audit.directional_field_pixels_validated == 4 * 480 * 640
    assert audit.coordinate_comparisons == 19 * 6


def test_artifact_reauthentication_detects_changes_after_initial_inventory(tmp_path):
    audit, _, _, _, _, folder = synthetic_video_fixture(tmp_path)
    path = folder / "requests.csv"
    path.write_bytes(path.read_bytes().replace(b"0.25", b"0.26"))
    with pytest.raises(ValueError, match="changed"):
        audit.read(path)


def test_cli_self_test_does_not_accept_experiment_paths():
    assert verifier.main(["--self-test"]) == 0
    with pytest.raises(ValueError, match="scientific paths"):
        verifier.main(["--self-test", "--manifest", "any.json"])


def test_cli_preserves_failed_report_and_refuses_overwriting_it(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    run = root / "data/tests/flow/farneback/config/benchmark/run"
    run.mkdir(parents=True)
    output = run.parent / "verification.json"
    monkeypatch.setattr(verifier, "ROOT", root)

    def failure(manifest, audit):
        raise ValueError("synthetic schema failure before any source read")

    monkeypatch.setattr(verifier, "verify", failure)
    arguments = ["--manifest", str(run / "manifest.json"), "--output", str(output)]
    assert verifier.main(arguments) == 1
    original = output.read_bytes()
    report = json.loads(original)
    assert report["status"] == "failed" and report["files_verified"] == 0
    assert report["original_sources_opened"] is False and report["project_implementation_imported"] is False
    with pytest.raises(FileExistsError):
        verifier.main(arguments)
    assert output.read_bytes() == original
