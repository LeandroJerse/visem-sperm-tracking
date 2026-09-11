"""Synthetic closed-universe, source-preservation and annotation-parity checks."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
import yaml

from src.core.artifacts import sha256_file
from src.detection import yolo_dataset as dataset


@pytest.fixture
def mini_plan(tmp_path):
    template = Path(dataset.REPOSITORY_ROOT)/dataset.DEFAULT_PLAN
    config = yaml.safe_load(template.read_text(encoding="utf-8"))
    config["expected_counts"] = {"train": 2, "val": 1, "unlabeled": 1}
    config["image"].update(width=8, height=6)
    videos = ({"video_id": "11", "split": "train", "total_frames": 3, "annotated_frames": 2},
              {"video_id": "14", "split": "val", "total_frames": 1, "annotated_frames": 1})
    gaps = {"11": (1,), "14": ()}
    plan = dataset.DatasetPlan(tmp_path, config, "plan.yaml", "0"*64, videos, gaps)
    for video in videos:
        vid = video["video_id"]
        base = tmp_path/config["source_root"]/vid
        for name in ("images", "labels", "labels_ftid"):
            (base/name).mkdir(parents=True)
        for frame in range(video["total_frames"]):
            stem = f"{vid}_frame_{frame}"
            ok, encoded = cv2.imencode(".jpg", np.full((6, 8, 3), frame*20, dtype=np.uint8))
            assert ok
            (base/"images"/f"{stem}.jpg").write_bytes(encoded.tobytes())
            if frame in gaps[vid]:
                continue
            # Metadata-only exclusion, deliberately not a valid numpy cache.
            (base/"images"/f"{stem}.npy").write_bytes(b"legacy cache preserved")
            (base/"labels"/f"{stem}.txt").write_text("0 0.5 0.5 0.2 0.2\n1 0.8 0.8 0.1 0.1\n", encoding="utf-8")
            (base/"labels_ftid"/f"{stem}_with_ftid.txt").write_text(
                "cluster 1 0.8 0.8 0.1 0.1\nsperm 0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    blocked = tmp_path/config["source_root"]/"24"
    blocked.mkdir()
    (blocked/"DO_NOT_READ").write_text("test remains untouched")
    return plan


def test_metadata_phase_never_opens_pixels_labels_ftid_or_blocked_video(mini_plan, monkeypatch):
    original = Path.open
    def guarded(path, *args, **kwargs):
        if "sources" in path.parts:
            raise AssertionError(f"source content opened during metadata phase: {path}")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    inventory = dataset.inspect_metadata(mini_plan)
    assert inventory["counts"] == {"train": 2, "val": 1, "unlabeled": 1}
    assert len(inventory["excluded_legacy_sidecars"]) == 3
    assert inventory["source_content_read"] is False
    assert {r["frame"] for r in inventory["records"] if r["video_id"] == "11"} == {0, 2}


@pytest.mark.parametrize("relative", [
    "11/images/11_frame_9.jpg", "11/images/11_frame_9.npy", "11/images/extra.png",
    "11/images/11_frame_00.jpg", "11/labels/11_frame_1.txt", "11/labels/labels.cache",
    "11/labels_ftid/11_frame_1_with_ftid.txt",
])
def test_unexpected_files_and_unlabeled_annotation_are_rejected(mini_plan, relative):
    (mini_plan.root/mini_plan.config["source_root"]/relative).write_bytes(b"unexpected")
    with pytest.raises(dataset.DatasetError, match="Unexpected|sidecar"):
        dataset.inspect_metadata(mini_plan)


@pytest.mark.parametrize("relative", ["11/images/11_frame_0.jpg", "11/labels/11_frame_0.txt",
                                       "11/labels_ftid/11_frame_0_with_ftid.txt"])
def test_missing_files_abort_instead_of_subsampling(mini_plan, relative):
    (mini_plan.root/mini_plan.config["source_root"]/relative).unlink()
    with pytest.raises(dataset.DatasetError, match="missing"):
        dataset.inspect_metadata(mini_plan)


@pytest.mark.parametrize("text", [
    "0 0.5 0.5 0.2", "0 0.5 0.5 0.2 0.2 id", "3 0.5 0.5 0.2 0.2",
    "0 nan 0.5 0.2 0.2", "0 0.5 inf 0.2 0.2", "0 0.5 0.5 0 0.2",
    "0 0.99 0.5 0.2 0.2", "0 0 0.5 0.2 0.2", "0 0.5 0.5 -0.2 0.2",
    "0 0.5 0.5 0.2 0.2\n0 0.50 0.50 0.20 0.20",
])
def test_invalid_annotation_is_rejected_without_repair(text):
    with pytest.raises(dataset.DatasetError):
        dataset.parse_yolo_labels(text)


def test_float_boundary_tolerance_preserves_original_coordinates_and_empty_annotation():
    rows = dataset.parse_yolo_labels("2 0.9500000000000001 0.5 0.1 0.2")
    assert rows[0][1] == 0.9500000000000001
    assert dataset.parse_yolo_labels("\n") == []
    with pytest.raises(dataset.DatasetError):
        dataset.parse_yolo_labels("2 0.95000001 0.5 0.1 0.2")


def test_ftid_multiset_parity_ignores_order_and_ids_only():
    rows = dataset.parse_yolo_labels("0 0.5 0.5 0.2 0.2\n2 0.7 0.7 0.1 0.1")
    exact = dataset.compare_ftid_reference(rows, "b 2 0.7 0.7 0.1 0.1\na 0 0.5 0.5 0.2 0.2")
    assert exact == {"annotations": 2, "exact_multiset": True, "maximum_difference": 0.0}
    near = dataset.compare_ftid_reference(rows, "b 2 0.7000000001 0.7 0.1 0.1\na 0 0.5 0.5 0.2 0.2")
    assert near["exact_multiset"] is False
    assert 0 < near["maximum_difference"] <= 1e-9


@pytest.mark.parametrize("text", [
    "a 0 0.5 0.5 0.2 0.2\na 0 0.7 0.7 0.1 0.1",
    "a 1 0.5 0.5 0.2 0.2", "a 0 0.50001 0.5 0.2 0.2",
    "a 0 0.5 0.5 0.2", "-1 0 0.5 0.5 0.2 0.2", "",
])
def test_ftid_identity_class_count_or_geometry_divergence_aborts(text):
    rows = dataset.parse_yolo_labels("0 0.5 0.5 0.2 0.2")
    with pytest.raises(dataset.DatasetError):
        dataset.compare_ftid_reference(rows, text)


def test_complete_copy_is_independent_authenticated_and_has_no_test_ftid_or_cache(mini_plan):
    inventory = dataset.inspect_metadata(mini_plan)
    source = mini_plan.root/mini_plan.config["source_root"]
    before = {p.relative_to(source).as_posix(): sha256_file(p) for p in source.rglob("*") if p.is_file()}
    target = mini_plan.root/"run/dataset"
    result = dataset.copy_dataset(mini_plan, inventory, target)
    assert result["class_counts"] == {"0": 3, "1": 3, "2": 0}
    assert result["labels_ftid_copied"] is False
    assert result["originals_rehashed_after"] is True
    descriptor = yaml.safe_load((target/"visem.yaml").read_text())
    assert set(descriptor) == {"path", "train", "val", "nc", "names"}
    assert not list(target.rglob("*.npy")) and not list(target.rglob("*ftid*"))
    assert not (target/"test.txt").exists()
    assert len((target/"train.txt").read_text().splitlines()) == 2
    for row in result["files"]:
        for kind in ("image", "label"):
            src = mini_plan.root/row[kind]["source"]
            dst = target/row[kind]["path"]
            assert not os.path.samefile(src, dst)
            assert dst.stat().st_nlink == 1
            assert sha256_file(src) == sha256_file(dst) == row[kind]["sha256"]
    after = {p.relative_to(source).as_posix(): sha256_file(p) for p in source.rglob("*") if p.is_file()}
    assert before == after
    with pytest.raises(FileExistsError):
        dataset.copy_dataset(mini_plan, inventory, target)


def test_changed_metadata_after_plan_aborts_before_copy(mini_plan):
    inventory = dataset.inspect_metadata(mini_plan)
    (mini_plan.root/inventory["records"][0]["label"]["path"]).write_text("0 0.5 0.5 0.2 0.2\n")
    target = mini_plan.root/"run/dataset"
    with pytest.raises(dataset.DatasetError, match="metadata changed"):
        dataset.copy_dataset(mini_plan, inventory, target)
    assert not target.exists()


def test_original_changed_during_copy_is_detected(mini_plan, monkeypatch):
    inventory = dataset.inspect_metadata(mini_plan)
    original_validate = dataset._validate_jpeg_copy
    changed = False
    def change_source(path, width, height):
        nonlocal changed
        original_validate(path, width, height)
        if not changed:
            changed = True
            source = mini_plan.root/inventory["records"][0]["image"]["path"]
            source.write_bytes(source.read_bytes()+b"external mutation")
    monkeypatch.setattr(dataset, "_validate_jpeg_copy", change_source)
    with pytest.raises(dataset.DatasetError, match="authentication"):
        dataset.copy_dataset(mini_plan, inventory, mini_plan.root/"run/dataset")


def test_invalid_jpeg_is_not_repaired_or_removed_from_sources(mini_plan):
    source = mini_plan.root/mini_plan.config["source_root"]/"11/images/11_frame_0.jpg"
    source.write_bytes(b"invalid original JPEG")
    before = sha256_file(source)
    with pytest.raises(dataset.DatasetError, match="JPEG"):
        dataset.copy_dataset(mini_plan, dataset.inspect_metadata(mini_plan), mini_plan.root/"run/dataset")
    assert sha256_file(source) == before


def test_added_output_file_is_rejected_by_closed_universe(mini_plan, monkeypatch):
    original_validate = dataset._validate_jpeg_copy
    target = mini_plan.root/"run/dataset"
    def extra(path, width, height):
        original_validate(path, width, height)
        (target/"unexpected.cache").write_text("cache")
    monkeypatch.setattr(dataset, "_validate_jpeg_copy", extra)
    with pytest.raises(dataset.DatasetError, match="Unexpected/missing files"):
        dataset.copy_dataset(mini_plan, dataset.inspect_metadata(mini_plan), target)


def test_source_hardlink_is_rejected(mini_plan):
    source = mini_plan.root/mini_plan.config["source_root"]/"11/images/11_frame_0.jpg"
    os.link(source, mini_plan.root/"hardlink.jpg")
    with pytest.raises(dataset.DatasetError, match="independent regular file"):
        dataset.inspect_metadata(mini_plan)


def test_path_traversal_and_absolute_paths_are_rejected():
    for path in ("../outside", "a/../b", "/absolute", "C:/absolute", "a\\b", "a//b", "./a"):
        with pytest.raises(dataset.DatasetError):
            dataset._relative(path)


def test_resource_failures_abort_without_silent_fallback(mini_plan, monkeypatch):
    monkeypatch.setattr(dataset.shutil, "disk_usage", lambda path: SimpleNamespace(free=1))
    with pytest.raises(dataset.DatasetError, match="free space"):
        dataset.copy_dataset(mini_plan, dataset.inspect_metadata(mini_plan), mini_plan.root/"run/dataset")
    assert not (mini_plan.root/"run/dataset").exists()
    monitor = SimpleNamespace(summary=lambda: {"ram_rss_peak_mb": 1025})
    with pytest.raises(dataset.DatasetError, match="RAM"):
        dataset._resource_guard(monitor, mini_plan.config, bytes_written=1)


def test_yaml_duplicate_and_unknown_keys_are_rejected(tmp_path):
    (tmp_path/"plan.yaml").write_text("kind: a\nkind: b\n", encoding="utf-8")
    with pytest.raises(dataset.DatasetError, match="Duplicate YAML"):
        dataset.load_dataset_plan("plan.yaml", root=tmp_path)
    config = yaml.safe_load((Path(dataset.REPOSITORY_ROOT)/dataset.DEFAULT_PLAN).read_text())
    config["test"] = [24]
    (tmp_path/"plan.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(dataset.DatasetError, match="Unexpected/missing keys"):
        dataset.load_dataset_plan("plan.yaml", root=tmp_path)


def test_materialization_requires_clean_snapshot_before_source_reads(mini_plan, monkeypatch):
    def dirty(*args):
        raise RuntimeError("clean Git required")
    monkeypatch.setattr(dataset.RunSnapshot, "capture", dirty)
    monkeypatch.setattr(dataset, "inspect_metadata", lambda plan: pytest.fail("read before clean Git gate"))
    with pytest.raises(RuntimeError, match="clean Git"):
        dataset.materialize_dataset(mini_plan)


def test_materialization_failure_retains_context_and_partial_outputs(mini_plan, monkeypatch):
    run = mini_plan.root/"run"
    run.mkdir()
    captured = {}
    def fail(exc, **kwargs):
        captured.update(kwargs)
        (run/"manifest.json").write_text(json.dumps({"status": "failed", "error": str(exc), **kwargs}))
    monkeypatch.setattr(dataset.RunSnapshot, "capture", lambda *args: object())
    monkeypatch.setattr(dataset.RunContext, "create", lambda **kwargs: SimpleNamespace(path=run, fail=fail))
    def partial(*args, **kwargs):
        (run/"partial.txt").write_text("preserved")
        raise dataset.DatasetError("injected failure")
    monkeypatch.setattr(dataset, "copy_dataset", partial)
    with pytest.raises(dataset.DatasetError, match="injected"):
        dataset.materialize_dataset(mini_plan)
    assert (run/"partial.txt").read_text() == "preserved"
    assert json.loads((run/"manifest.json").read_text())["status"] == "failed"
    assert captured["partial_outputs_preserved"] is True
