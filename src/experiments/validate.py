"""Validate experiment splits and local dataset layout before long runs."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from src.core.paths import VISEM_TRACKING_TRAIN_ROOT, VISEM_VIDEOS_ROOT

from .dataset import load_manifest, load_split_spec, validate_manifest_against_split


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_video_inventory(
    inventory_rows: list[dict[str, str]],
    tracked_ids: set[str],
    raw_videos_root: Path,
) -> list[str]:
    errors: list[str] = []
    ids = [row.get("video_id", "") for row in inventory_rows]
    if len(ids) != 85 or len(set(ids)) != 85:
        errors.append(f"video inventory must contain 85 unique IDs, found {len(set(ids))}")
    inventory_tracked = {
        row.get("video_id", "")
        for row in inventory_rows
        if row.get("has_tracking", "").strip().lower() == "true"
    }
    if inventory_tracked != tracked_ids:
        errors.append(
            "inventory tracking IDs differ from experimental split: "
            f"inventory={sorted(inventory_tracked)}, split={sorted(tracked_ids)}"
        )
    for row in inventory_rows:
        filename = row.get("filename", "")
        if not filename or not (raw_videos_root / filename).is_file():
            errors.append(f"missing raw video from inventory: {filename!r}")
        expected_role = (
            "development_validation"
            if row.get("video_id") in tracked_ids
            else "post_validation_application"
        )
        if row.get("role") != expected_role:
            errors.append(f"video {row.get('video_id')}: expected role {expected_role}")
    return errors


def validate_annotation_gaps(
    manifest_rows: list[dict[str, str]], gap_rows: list[dict[str, str]]
) -> list[str]:
    errors: list[str] = []
    missing_by_video: dict[str, set[int]] = {}
    for row in gap_rows:
        video_id = row.get("video_id", "")
        try:
            start = int(row["start_frame"])
            end = int(row["end_frame"])
            declared = int(row["frame_count"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"invalid annotation gap row: {row}")
            continue
        if start < 0 or end < start or declared != end - start + 1:
            errors.append(f"invalid annotation gap interval: {row}")
            continue
        frames = set(range(start, end + 1))
        overlap = missing_by_video.setdefault(video_id, set()) & frames
        if overlap:
            errors.append(f"overlapping gaps for video {video_id}: {min(overlap)}")
        missing_by_video[video_id].update(frames)
        if row.get("policy") != "exclude":
            errors.append(f"video {video_id}: annotation gaps must use policy=exclude")

    known_ids = {row["video_id"] for row in manifest_rows}
    if set(missing_by_video) - known_ids:
        errors.append(f"gaps reference unknown videos: {sorted(set(missing_by_video) - known_ids)}")
    for row in manifest_rows:
        video_id = row["video_id"]
        expected = int(row["total_frames"]) - int(row["annotated_frames"])
        declared = len(missing_by_video.get(video_id, set()))
        if declared != expected:
            errors.append(
                f"video {video_id}: missing frames={expected}, gap manifest={declared}"
            )
    return errors


def validate_local_layout(train_root: Path, manifest_rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for row in manifest_rows:
        video_id = row["video_id"]
        folder = train_root / video_id
        video = folder / f"{video_id}.mp4"
        labels = folder / "labels_ftid"
        if not video.is_file():
            errors.append(f"missing video: {video}")
        if not labels.is_dir():
            errors.append(f"missing labels directory: {labels}")
            continue
        expected = int(row["annotated_frames"])
        actual = len(list(labels.glob("*.txt")))
        if actual != expected:
            errors.append(f"video {video_id}: manifest labels={expected}, filesystem={actual}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits", default="configs/protocol/splits.yaml")
    parser.add_argument("--manifest", default="data/manifests/visem_tracking.csv")
    parser.add_argument("--video-inventory", default="data/manifests/visem_videos.csv")
    parser.add_argument("--annotation-gaps", default="data/manifests/annotation_gaps.csv")
    parser.add_argument("--raw-videos-root", default=str(VISEM_VIDEOS_ROOT))
    parser.add_argument(
        "--train-root", default=str(VISEM_TRACKING_TRAIN_ROOT)
    )
    args = parser.parse_args(argv)

    split = load_split_spec(args.splits)
    rows = load_manifest(args.manifest)
    errors = validate_manifest_against_split(split, rows)
    errors.extend(validate_local_layout(Path(args.train_root), rows))
    inventory_rows = _read_csv(args.video_inventory)
    gap_rows = _read_csv(args.annotation_gaps)
    errors.extend(
        validate_video_inventory(
            inventory_rows, set(split.all_ids), Path(args.raw_videos_root)
        )
    )
    errors.extend(validate_annotation_gaps(rows, gap_rows))
    if errors:
        print("Falhas de validação:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(
        f"OK: {len(split.all_ids)} vídeos, splits disjuntos, "
        f"{len(split.folds)} folds, 85 vídeos no inventário e lacunas consistentes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
