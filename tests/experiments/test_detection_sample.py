"""Synthetic cache tests: canonical indices, strict GT, precision and failures."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from src.experiments import detection_sample as sample
from src.experiments.config import load_config


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pixels(video, index):
    frame = np.empty((3, 4, 3), dtype=np.uint8)
    frame[:, :, 0], frame[:, :, 1], frame[:, :, 2] = index, int(video), (index + int(video)) % 256
    return frame


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    # Preserve all 12 IDs and 48/12/1 sizes; shrink only synthetic image pixels.
    monkeypatch.setattr(sample, "_WIDTH", 4)
    monkeypatch.setattr(sample, "_HEIGHT", 3)
    monkeypatch.setattr(sample, "environment_snapshot", lambda: {"synthetic": True})
    root = tmp_path / "repository"
    split_path = root / "configs/protocol/splits.yaml"
    split_path.parent.mkdir(parents=True)
    split_path.write_text(yaml.safe_dump({
        "fixed_split": {"train": list(map(int, sample.TRAIN_IDS)), "val": [14, 19, 36, 52], "test": [24, 38, 47, 54]},
        "oof_folds": {"A": [24, 38, 47, 54], "B": [13, 14, 19, 60], "C": [11, 22, 29, 82],
                      "D": [12, 23, 35, 36], "E": [15, 21, 30, 52]}, "seeds": [42],
    }), encoding="utf-8")
    plan = copy.deepcopy(load_config(Path(__file__).resolve().parents[2] / "configs/detection/threshold/search_v3.yaml"))
    plan["sampling"].update(width=4, height=3)
    audit_path = root / plan["protocol"]["geometry_audit"]
    audit_path.mkdir(parents=True)
    frames, files = [], []
    for video in sample.TRAIN_IDS:
        folder = root / sample._SOURCES / video
        label_dir = folder / "labels_ftid"
        label_dir.mkdir(parents=True)
        (folder / f"{video}.mp4").write_bytes(f"synthetic-video-{video}".encode())
        (label_dir / "auxiliary.npy").write_bytes(b"ignored auxiliary file")
        for index in range(64):
            present = not (video == "23" and index in {7, 22})
            count = int(index != 0 and present)
            class_id = int(video) % 3
            row = {"video_id": video, "frame": index, "annotation_state": (
                "unlabeled" if not present else "annotated" if count else "annotated_empty"
            ), "labels_ftid_present": present, "image_width": 4, "image_height": 3,
                   "raw_rows": count, "valid_rows": count, "invalid_rows": 0}
            row.update({f"{kind}_class{cls}": int(count and class_id == cls)
                        for kind in ("raw", "valid") for cls in (0, 1, 2)})
            frames.append(row)
            if not present:
                continue
            path = label_dir / f"{video}_frame_{index}_with_ftid.txt"
            path.write_text(f"00001 {class_id} 0.45123456789 0.5123456789 0.123456789 0.2123456789\n" if count else "\n", encoding="utf-8")
            files.append({"path": path.relative_to(root).as_posix(), "role": "labels_ftid", "video_id": video,
                          "frame": index, "bytes": path.stat().st_size, "sha256": _digest(path)})
    _write_csv(audit_path / "per_frame_counts.csv", frames)
    _write_csv(audit_path / "input_files.csv", files)

    def update_audit_manifest():
        (audit_path / "manifest.json").write_text(json.dumps({
            "configuration": {"video_ids": list(map(int, sample.TRAIN_IDS))},
            "outputs": {name: {"sha256": _digest(audit_path / name)} for name in ("per_frame_counts.csv", "input_files.csv")},
        }), encoding="utf-8")

    update_audit_manifest()
    decoded = []

    class Capture:
        def __init__(self, path):
            self.video = Path(path).stem
            self.index = 0
            self.released = False
            decoded.append(self)

        def isOpened(self):
            return True

        def getBackendName(self):
            return "synthetic-sequential"

        def read(self):
            frame = _pixels(self.video, self.index)
            self.index += 1
            return True, frame

        def get(self, prop):
            return self.index

        def release(self):
            self.released = True

    monkeypatch.setattr(sample.cv2, "VideoCapture", Capture)
    return {"root": root, "plan": plan, "cache": root / "data/derived/cache", "frames": frames,
            "files": files, "audit": audit_path, "update_audit": update_audit_manifest,
            "decoded": decoded, "Capture": Capture}


def test_nested_universe_lossless_pixels_full_precision_gt_and_readonly_cache(inputs, capsys):
    root, plan, cache = (inputs[key] for key in ("root", "plan", "cache"))
    manifest = sample.prepare_sample(plan, cache, repo_root=root)
    progress = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [item["video_id"] for item in progress] == list(sample.TRAIN_IDS)
    assert progress[-1]["completed_videos"] == progress[-1]["planned_videos"] == 12
    assert all(item["event"] == "sample_video_cached" and item["master_frames"] == 48 for item in progress)
    original_hashes = {path: _digest(path) for path in cache.rglob("*") if path.is_file()}
    loaded = sample.load_sample(cache, plan, repo_root=root)
    assert loaded.sample_hash == manifest["sample_hash"]
    assert loaded.video_ids == sample.TRAIN_IDS
    assert len(manifest["frames"]) == 576
    assert len(list(cache.glob("frames/*.npy"))) == 12
    assert not list(cache.rglob("*.png"))
    assert len(inputs["decoded"]) == 12
    assert all(cap.released and cap.index == 64 for cap in inputs["decoded"])
    for video in loaded.video_ids:
        master, coarse, benchmark = (loaded.indices(mode, video) for mode in ("master", "coarse", "benchmark"))
        assert (len(master), len(coarse), len(benchmark)) == (48, 12, 1)
        assert set(benchmark) <= set(coarse) <= set(master)
        assert benchmark == (coarse[len(coarse) // 2],)
        assert master[0] == 0 and master[-1] == 63
    assert not ({7, 22} & set(loaded.indices("master", "23")))
    observed = list(loaded.frames("benchmark"))
    assert len(observed) == 12
    for video, index, frame, gt in observed:
        assert np.array_equal(frame, _pixels(video, index))
        assert not frame.flags.writeable
        with pytest.raises(ValueError):
            frame[0, 0, 0] = 99
        assert gt[0].object_id == "00001"
        assert gt[0].cx == 0.45123456789 * 4
    first = next(loaded.frames("master", "23"))
    assert first[1] == 0 and first[3] == ()  # actual empty label, never the gap
    observed[0][3][0].cx = 999
    assert next(loaded.frames("benchmark"))[3][0].cx == 0.45123456789 * 4
    assert original_hashes == {path: _digest(path) for path in original_hashes}
    assert manifest["cache_bytes"] == sum(path.stat().st_size for path in cache.rglob("*") if path.is_file())
    with pytest.raises(FileExistsError):
        sample.prepare_sample(plan, cache, repo_root=root)
    assert set(manifest["timings"]) >= {"decode_seconds", "source_hash_seconds", "array_write_seconds", "array_hash_seconds"}


@pytest.mark.parametrize("change", ["plan_ids", "split", "insufficient_budget"])
def test_preflight_rejects_identity_or_budget_before_source_io(inputs, monkeypatch, change):
    plan, root = inputs["plan"], inputs["root"]
    if change == "plan_ids":
        plan["protocol"]["train_ids"][0] = 24
    elif change == "split":
        path = root / "configs/protocol/splits.yaml"
        spec = yaml.safe_load(path.read_text())
        spec["fixed_split"]["train"], spec["fixed_split"]["val"] = spec["fixed_split"]["val"], spec["fixed_split"]["train"]
        path.write_text(yaml.safe_dump(spec))
    else:
        plan["budget"]["max_cache_mb"] = 0.00001
    monkeypatch.setattr(sample, "_audit_and_labels", lambda *args: pytest.fail("source I/O reached"))
    with pytest.raises(ValueError):
        sample.prepare_sample(plan, inputs["cache"], repo_root=root)
    assert not inputs["cache"].exists() and not inputs["decoded"]


@pytest.mark.parametrize("rule", [None, "upper_middle_of_master_sample"])
def test_missing_or_changed_benchmark_rule_is_rejected_before_source_io(inputs, monkeypatch, rule):
    if rule is None:
        inputs["plan"]["sampling"].pop("benchmark_rule")
    else:
        inputs["plan"]["sampling"]["benchmark_rule"] = rule
    monkeypatch.setattr(sample, "_audit_and_labels", lambda *args: pytest.fail("source I/O reached"))
    with pytest.raises(ValueError, match="benchmark_rule"):
        sample.prepare_sample(inputs["plan"], inputs["cache"], repo_root=inputs["root"])
    with pytest.raises(ValueError, match="benchmark_rule"):
        sample.load_sample(inputs["cache"], inputs["plan"], repo_root=inputs["root"])
    assert not inputs["cache"].exists() and not inputs["decoded"]


@pytest.mark.parametrize("missing", [False, True])
def test_selected_missing_or_changed_label_fails_before_decode(inputs, missing):
    path = inputs["root"] / sample._SOURCES / "11/labels_ftid/11_frame_0_with_ftid.txt"
    if missing:
        path.unlink()
    else:
        path.write_text("changed\n")
    with pytest.raises(ValueError, match="missing|hash mismatch"):
        sample.prepare_sample(inputs["plan"], inputs["cache"], repo_root=inputs["root"])
    assert not inputs["decoded"] and not inputs["cache"].exists()


def test_malformed_label_is_rejected_even_with_updated_input_hash(inputs):
    row = inputs["files"][0]
    path = inputs["root"] / row["path"]
    path.write_text("short 0 0.5\n")
    row.update(bytes=path.stat().st_size, sha256=_digest(path))
    _write_csv(inputs["audit"] / "input_files.csv", inputs["files"])
    inputs["update_audit"]()
    with pytest.raises(ValueError, match="six-field"):
        sample.prepare_sample(inputs["plan"], inputs["cache"], repo_root=inputs["root"])
    assert not inputs["decoded"]


@pytest.mark.parametrize("line", [
    "id 0 0.5 0.5 0.1 0.1 extra", "id 3 0.5 0.5 0.1 0.1",
    "id 0 nan 0.5 0.1 0.1", "id 0 0.5 0.5 0 0.1",
    "id 0 1.01 0.5 0.1 0.1", "id 0 0.01 0.5 0.5 0.1",
    "id 0 0.5 0.5 0.1 0.1\nid 0 0.5 0.5 0.1 0.1",
])
def test_tracked_label_contract_refuses_invalid_rows_instead_of_dropping_them(line):
    with pytest.raises(ValueError):
        sample._strict_gt(line.encode(), {}, Path("synthetic_label.txt"))


def test_insufficient_annotated_frames_does_not_reduce_candidate_universe(inputs):
    rows = [row for row in inputs["frames"] if row["video_id"] != "11" or row["frame"] < 47]
    _write_csv(inputs["audit"] / "per_frame_counts.csv", rows)
    inputs["update_audit"]()
    with pytest.raises(ValueError, match="fewer than 48"):
        sample.prepare_sample(inputs["plan"], inputs["cache"], repo_root=inputs["root"])


def test_new_label_in_audited_gap_cannot_silently_change_population(inputs):
    path = inputs["root"] / sample._SOURCES / "23/labels_ftid/23_frame_7_with_ftid.txt"
    path.write_text("new-id 0 0.5 0.5 0.1 0.1\n")
    with pytest.raises(ValueError, match="index differs.*extra=\\[7\\]"):
        sample.prepare_sample(inputs["plan"], inputs["cache"], repo_root=inputs["root"])
    assert not inputs["decoded"]


@pytest.mark.parametrize("failure", ["decode", "position", "shape"])
def test_failed_decode_preserves_failed_cache_and_never_loads_it(inputs, monkeypatch, failure):
    parent = inputs["Capture"]

    class BrokenCapture(parent):
        def read(self):
            if self.index == 5:
                if failure == "decode":
                    return False, None
                if failure == "shape":
                    self.index += 1
                    return True, np.zeros((2, 2, 3), dtype=np.uint8)
            return super().read()

        def get(self, prop):
            return self.index + int(failure == "position" and self.index == 6)

    monkeypatch.setattr(sample.cv2, "VideoCapture", BrokenCapture)
    with pytest.raises(ValueError, match="decode|position|dimensions"):
        sample.prepare_sample(inputs["plan"], inputs["cache"], repo_root=inputs["root"])
    manifest = json.loads((inputs["cache"] / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert inputs["decoded"][0].released
    with pytest.raises(ValueError, match="complete"):
        sample.load_sample(inputs["cache"], inputs["plan"], repo_root=inputs["root"])
    with pytest.raises(FileExistsError):
        sample.prepare_sample(inputs["plan"], inputs["cache"], repo_root=inputs["root"])


@pytest.mark.parametrize("corruption", ["pixels", "gt", "source", "plan", "universe"])
def test_load_rejects_changed_arrays_gt_source_plan_and_manifest_universe(inputs, corruption):
    root, cache, plan = (inputs[key] for key in ("root", "cache", "plan"))
    manifest = sample.prepare_sample(plan, cache, repo_root=root)
    if corruption == "pixels":
        path = cache / "frames/video_11.npy"
        array = np.load(path, mmap_mode="r+")
        array[0, 0, 0, 0] = 255
        array.flush()
        del array
    elif corruption == "gt":
        with (cache / "ground_truth.csv").open("a") as stream:
            stream.write("extra row\n")
    elif corruption == "source":
        (root / sample._SOURCES / "11/11.mp4").write_bytes(b"source changed")
    elif corruption == "plan":
        plan["plan_id"] = "changed-after-preparation"
    else:
        manifest["selections"]["11"]["coarse"].pop()
        # Even a recomputed manifest hash must not override the audited universe.
        manifest["sample_hash"] = sample._json_sha(sample._identity(manifest))
        (cache / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="hash|plan|universe"):
        sample.load_sample(cache, plan, repo_root=root)
