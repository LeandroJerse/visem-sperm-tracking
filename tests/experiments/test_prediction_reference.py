from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from src.experiments.config import config_hash
from src.prediction import reference as reader


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def file_ref(path):
    content = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}


@pytest.fixture
def exported(tmp_path):
    root = tmp_path
    # Versioned metadata only. All exported observations, segments, windows,
    # raw GT and certification below are independently synthetic, with no
    # use of the producer's ground_truth builder or original source files.
    for name in reader._METADATA_PATHS:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((reader.REPOSITORY_ROOT / name).read_bytes())
    config = yaml.safe_load((root / reader._METADATA_PATHS[0]).read_text(encoding="utf-8"))
    folder = root / "data/derived/synthetic_reference/preparation/run"
    folder.mkdir(parents=True)
    videos, artifact_paths, input_hashes = [], [], {}
    for video in reader.TRAIN_IDS:
        count = reader.EXPECTED_FRAMES[video]
        missing = {i for a, b in reader._GAPS.get(video, ()) for i in range(a, b + 1)}
        identity, segment = f"cell-{video}", f"{video}/cell-{video}/0"
        observations = []
        for frame in range(32):
            cx, cy = 100.125 + frame / 8, 200.375 - frame / 8
            observations.append({"video_id": video, "frame_index": frame, "annotated": True,
                "track_id": identity, "segment_id": segment, "class_id": 0 if frame < 16 else 2,
                "cx": cx, "cy": cy, "w": 4.0, "h": 6.0, "x": cx - 2, "y": cy - 3})
        segments = [{"video_id": video, "track_id": identity, "segment_id": segment, "split": "train",
            "start_frame": 0, "end_frame": 31, "observation_count": 32,
            "start_reason": "video_start", "end_reason": "id_absent", "end_boundary_frame": 32}]
        windows = [{"window_id": f"{segment}/{origin}/h20_f10", "video_id": video,
            "track_id": identity, "segment_id": segment, "split": "train", "history_start": origin - 19,
            "origin_frame": origin, "future_end": origin + 10, "history_length": 20,
            "forecast_horizon": 10} for origin in (19, 20, 21)]
        status = [{"video_id": video, "frame_index": frame, "annotated": frame not in missing,
                   "raw_count": 2 if frame < 32 else 0, "individual_count": 1 if frame < 32 else 0,
                   "cluster_count": 1 if frame < 32 else 0} for frame in range(count)]
        start_counts = {reason: int(reason == "video_start") for reason in reader._START}
        end_counts = {reason: int(reason == "id_absent") for reason in reader._END}
        summary = {"schema_version": 1, "video_id": video, "split": "train", "expected_frame_count": count,
            "frames_total": count, "frames_annotated": count - len(missing), "frames_unannotated": len(missing),
            "frames_annotated_empty": count - len(missing) - 32, "frames_with_individuals": 32,
            "frames_with_clusters": 32, "frames_cluster_only": 0, "raw_observations": 64,
            "individual_observations": 32, "cluster_observations": 32,
            "class_observations": {"0": 16, "1": 32, "2": 16}, "unique_raw_track_ids": 2,
            "unique_individual_track_ids": 1, "segments_total": 1, "segments_with_windows": 1,
            "segments_without_windows": 0, "segment_start_reasons": start_counts, "segment_end_reasons": end_counts,
            "history_length": 20, "forecast_horizon": 10, "stride": 1,
            "origins_with_complete_history": 13, "windows_total": 3, "origins_excluded_incomplete_future": 10,
            "excluded_origins_by_end_reason": {reason: 10 * int(reason == "id_absent") for reason in reader._END}}
        input_hashes[video] = hashlib.sha256(video.encode()).hexdigest()
        contract = {"contract": "full_video_input_v1", "video_id": video, "expected_width": 640,
            "expected_height": 480, "expected_frame_count": count, "input_hash": input_hashes[video],
            "video_metadata": {"width": 640, "height": 480, "frame_count": count, "fps": 49.0 if video == "11" else 50.0},
            "ground_truth": {"annotated_frames": count - len(missing), "unannotated_frames": len(missing),
                             "unannotated_indices": sorted(missing)}}
        base = folder / "by_video" / video
        base.mkdir(parents=True)
        for table, rows in (("observations", observations), ("segments", segments), ("windows", windows), ("frame_status", status)):
            write_csv(base / f"{table}.csv", reader._FIELDS[table], rows)
        raw = [{"video_id": video, "frame": row["frame_index"], "object_id": row["track_id"], "class_id": row["class_id"]}
               for row in observations]
        raw += [{"video_id": video, "frame": frame, "object_id": "cluster", "class_id": 1} for frame in range(32)]
        write_csv(base / "ground_truth_raw.csv", ("video_id", "frame", "object_id", "class_id"), raw)
        write_json(base / "summary.json", summary)
        write_json(base / "input_contract.json", contract)
        videos.append(summary)
        artifact_paths.extend(base / name for name in reader._ARTIFACT_NAMES)
    summary = {"status": "prepared_training_reference_not_prediction_evaluation", "video_ids": list(reader.TRAIN_IDS),
               "totals": {key: sum(video[key] for video in videos) for key in reader._TOTALS}, "videos": videos,
               "model_evaluated": False, "validation_sources_read": False, "test_sources_read": False,
               "pixels_decoded": False, "statistical_unit": "video", "future_reference_conditioned_eligibility": True}
    write_json(folder / "summary.json", summary)
    artifact_paths.append(folder / "summary.json")
    manifest_path, qa_path = folder / "manifest.json", folder.parent / "verification.json"
    manifest = {"status": "complete", "module": "prediction", "method": "ground_truth_individuals",
        "stage": "preparation", "git_dirty": False, "git_sha": "synthetic", "source_hash": "b" * 64,
        "config": config, "config_hash": config_hash(config), "summary": summary,
        "provenance_capture": {"snapshot_sha256": "a" * 64},
        "repository_recheck": {"status": "verified", "snapshot_sha256": "a" * 64},
        "input_rechecks": [{"status": "verified", "input_hash": input_hashes[v]} for v in reader.TRAIN_IDS],
        "metadata": [file_ref(root / name) for name in reader._METADATA_PATHS]}
    qa = {"status": "passed", "run_manifest": str(manifest_path), "plan_hash": config_hash(config, 64),
        "git_sha_of_verified_run": "synthetic", "source_hash_of_verified_run": "b" * 64,
        "shared_snapshot_sha256": "a" * 64, "video_ids": list(reader.TRAIN_IDS),
        "expected_frames_per_video": reader.EXPECTED_FRAMES, "totals_rebuilt": summary["totals"],
        "video_summaries_rebuilt": videos, "all_observations_segments_windows_compared": True,
        "coordinates_compared_as_exact_binary_floats": True,
        "original_sources_opened": False, "project_implementation_imported": False,
        "input_hashes_recorded": input_hashes, "files_verified": 86}

    def refresh():
        manifest["artifacts"] = [file_ref(path) for path in artifact_paths]
        write_json(manifest_path, manifest)
        qa["run_manifest_sha256"] = file_ref(manifest_path)["sha256"]
        qa["input_files"] = [file_ref(manifest_path), *manifest["artifacts"]]
        write_json(qa_path, qa)

    def load():
        return reader.load_prediction_reference(manifest_path,
            expected_manifest_sha256=file_ref(manifest_path)["sha256"],
            verification_path=qa_path, expected_verification_sha256=file_ref(qa_path)["sha256"], repo_root=root)

    refresh()
    return SimpleNamespace(root=root, folder=folder, manifest_path=manifest_path, qa_path=qa_path,
                           manifest=manifest, qa=qa, refresh=refresh, load=load)


def change_table(exported, table, mutate, video="11"):
    path = exported.folder / "by_video" / video / f"{table}.csv"
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    mutate(rows)
    write_csv(path, reader._FIELDS[table], rows)
    # New synthetic expected parent/QA hashes intentionally let semantic
    # checks run. Separate tamper tests retain pinned original hashes.
    exported.refresh()


def test_loads_exact_cohort_without_original_sources_and_separates_future(exported):
    reference = exported.load()
    assert reference.video_ids == reader.TRAIN_IDS
    video = reference.load_video("11")
    assert video.n_windows == 3 and video.fps == 49.0
    assert video.track_ids_with_windows == ("cell-11",)
    assert video.summary["class_observations"] == {"0": 16, "1": 32, "2": 16}
    batches = list(video.iter_batches(2))
    assert [b.histories.shape for b in batches] == [(2, 20, 2), (1, 20, 2)]
    assert [b.targets.shape for b in batches] == [(2, 10, 2), (1, 10, 2)]
    batch = batches[0]
    assert batch.histories.dtype == batch.targets.dtype == np.float64
    np.testing.assert_array_equal(batch.histories[0, :, 0], 100.125 + np.arange(20) / 8)
    np.testing.assert_array_equal(batch.targets[0, :, 0], 100.125 + np.arange(20, 30) / 8)
    assert batch.window_rows[0]["window_id"] == "11/cell-11/0/19/h20_f10"
    assert batch.window_rows[0]["origin_frame"] == 19
    assert not np.shares_memory(batch.histories, batch.targets)
    assert reference.verify_current()["files_verified"] == 91
    assert not (exported.root / "data/sources").exists()


def test_batches_summary_and_provenance_are_detached_and_immutable(exported):
    reference = exported.load()
    video = reference.load_video("11")
    batch = next(video.iter_batches())
    with pytest.raises(ValueError):
        batch.histories[0, 0, 0] = -1
    with pytest.raises(ValueError):
        batch.targets.setflags(write=True)
    with pytest.raises(TypeError):
        batch.window_rows[0]["origin_frame"] = 30
    summary = video.summary
    summary["windows_total"] = 0
    provenance = reference.provenance
    provenance["validated_inputs"].clear()
    assert video.summary["windows_total"] == 3
    assert len(reference.provenance["validated_inputs"]) == 91
    assert next(video.iter_batches()).histories[0, 0, 0] == 100.125


def test_window_key_hash_matches_consumption_across_batches_and_detects_order(exported):
    video = exported.load().load_video("11")
    keys = "window_id video_id track_id segment_id split history_start origin_frame future_end".split()

    def digest(rows):
        result = hashlib.sha256()
        for row in rows:
            result.update(json.dumps([row[key] for key in keys], ensure_ascii=True,
                                     separators=(",", ":")).encode("utf-8") + b"\n")
        return result.hexdigest()

    for batch_size in (1, 2, 512):
        rows = [row for batch in video.iter_batches(batch_size) for row in batch.window_rows]
        assert digest(rows) == video.window_keys_sha256
        assert digest(reversed(rows)) != video.window_keys_sha256
        assert digest(rows[:-1]) != video.window_keys_sha256


@pytest.mark.parametrize("size", [0, -1, True, 1.5])
def test_invalid_batch_size_rejected(exported, size):
    with pytest.raises(ValueError, match="batch_size"):
        next(exported.load().load_video("11").iter_batches(size))


@pytest.mark.parametrize("video", ["14", "24", "A", "all", "../11", 11])
def test_unregistered_video_cannot_be_loaded(exported, video):
    with pytest.raises(ValueError, match="training video"):
        exported.load().load_video(video)


@pytest.mark.parametrize("table,field,value,error", [
    ("observations", "class_id", "1", "class/frame"),
    ("observations", "track_id", "different-id", "one ID"),
    ("observations", "segment_id", "12/cell-11/0", "consecutive|segment"),
    ("observations", "annotated", "1", "flag"),
    ("observations", "cx", "nan", "Nonfinite"),
    ("observations", "x", "50", "geometry"),
    ("segments", "split", "test", "split"),
    ("segments", "segment_id", "12/cell-11/0", "segment ID"),
    ("segments", "end_boundary_frame", "31", "boundary"),
    ("segments", "end_reason", "annotation_absent", "reason"),
    ("windows", "history_start", "1", "Window"),
    ("windows", "origin_frame", "20", "Window"),
    ("windows", "future_end", "30", "Window"),
    ("windows", "history_length", "19", "Window"),
    ("windows", "forecast_horizon", "11", "Window"),
    ("windows", "track_id", "different-id", "Window"),
    ("windows", "video_id", "12", "Window"),
    ("windows", "window_id", "12/cell-11/0/19/h20_f10", "Window"),
    ("frame_status", "frame_index", "1", "ordered"),
    ("frame_status", "raw_count", "3", "counts"),
    ("frame_status", "annotated", "False", "coverage"),
])
def test_semantic_corruption_rejected_even_with_new_synthetic_hashes(exported, table, field, value, error):
    index = 10 if table == "observations" and field == "track_id" else 0
    change_table(exported, table, lambda rows: rows[index].update({field: value}))
    with pytest.raises(ValueError, match=error):
        exported.load().load_video("11")


@pytest.mark.parametrize("table", ["observations", "frame_status", "windows", "segments"])
def test_missing_rows_cannot_be_silently_skipped(exported, table):
    change_table(exported, table, lambda rows: rows.pop())
    with pytest.raises(ValueError):
        exported.load().load_video("11")


@pytest.mark.parametrize("table", ["observations", "frame_status", "windows", "segments"])
def test_duplicate_rows_cannot_create_extra_eligible_windows(exported, table):
    change_table(exported, table, lambda rows: rows.append(dict(rows[-1])))
    with pytest.raises(ValueError):
        exported.load().load_video("11")


def test_missing_annotation_gap_is_not_converted_to_a_negative_frame(exported):
    change_table(exported, "frame_status", lambda rows: rows[823].update({"annotated": "True"}), video="23")
    with pytest.raises(ValueError, match="coverage"):
        exported.load().load_video("23")


@pytest.mark.parametrize("field,value", [("status", "failed"), ("git_dirty", True), ("stage", "test")])
def test_invalid_parent_status_or_provenance_is_rejected(exported, field, value):
    exported.manifest[field] = value
    exported.refresh()
    with pytest.raises(ValueError):
        exported.load()


@pytest.mark.parametrize("field,value", [("status", "failed"), ("all_observations_segments_windows_compared", False),
                                           ("original_sources_opened", True), ("shared_snapshot_sha256", "c" * 64)])
def test_missing_or_mismatched_independent_qa_is_rejected(exported, field, value):
    exported.qa[field] = value
    exported.refresh()
    with pytest.raises(ValueError):
        exported.load()


def test_non_train_parent_contract_is_rejected(exported):
    exported.manifest["config"]["run"]["split"] = "val"
    exported.refresh()
    with pytest.raises(ValueError, match="split"):
        exported.load()


@pytest.mark.parametrize("key,value", [("root", "data/sources/another_cohort"), ("missing_label_ranges", {})])
def test_changed_reference_source_or_gap_plan_is_rejected(exported, key, value):
    exported.manifest["config"]["input"][key] = value
    exported.refresh()
    with pytest.raises(ValueError, match="contract|gaps"):
        exported.load()


def test_observation_gap_inside_a_window_cannot_be_bridged(exported):
    change_table(exported, "observations", lambda rows: rows.pop(10))
    with pytest.raises(ValueError, match="counts|consecutive"):
        exported.load().load_video("11")


@pytest.mark.parametrize("target", ["manifest", "qa", "table", "raw"])
def test_hash_tamper_is_rejected_without_recalculating_expected_hashes(exported, target):
    parent_hash, qa_hash = file_ref(exported.manifest_path)["sha256"], file_ref(exported.qa_path)["sha256"]
    path = {"manifest": exported.manifest_path, "qa": exported.qa_path,
            "table": exported.folder / "by_video/11/observations.csv",
            "raw": exported.folder / "by_video/11/ground_truth_raw.csv"}[target]
    with path.open("a", encoding="utf-8") as stream:
        stream.write("tampered")
    with pytest.raises(ValueError, match="changed"):
        reader.load_prediction_reference(exported.manifest_path, expected_manifest_sha256=parent_hash,
            verification_path=exported.qa_path, expected_verification_sha256=qa_hash, repo_root=exported.root)


def test_recheck_detects_changes_after_detached_batch_creation(exported):
    reference = exported.load()
    batch = next(reference.load_video("11").iter_batches())
    path = exported.folder / "by_video/11/windows.csv"
    with path.open("a", encoding="utf-8") as stream:
        stream.write("changed")
    assert batch.histories[0, 0, 0] == 100.125
    with pytest.raises(ValueError, match="changed"):
        reference.verify_current()
    with pytest.raises(ValueError, match="changed"):
        reference.load_video("11")


def test_original_source_path_rejected_before_read(exported):
    with pytest.raises(ValueError, match="original sources"):
        reader.load_prediction_reference(exported.root / "data/sources/not_opened.json",
            expected_manifest_sha256="a" * 64, verification_path=exported.qa_path,
            expected_verification_sha256=file_ref(exported.qa_path)["sha256"], repo_root=exported.root)


def test_swapped_artifact_path_cannot_relabel_another_video(exported):
    exported.manifest["artifacts"][0]["path"] = str(exported.folder / "by_video/12/observations.csv")
    write_json(exported.manifest_path, exported.manifest)
    exported.qa["run_manifest_sha256"] = file_ref(exported.manifest_path)["sha256"]
    write_json(exported.qa_path, exported.qa)
    with pytest.raises(ValueError, match="85 reference artifacts"):
        exported.load()
