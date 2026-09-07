"""Dataset split and manifest helpers with leakage validation."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import ConfigError, load_config


def _as_ids(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(str(value) for value in values)


@dataclass(frozen=True)
class SplitSpec:
    train: tuple[str, ...]
    val: tuple[str, ...]
    test: tuple[str, ...]
    folds: dict[str, tuple[str, ...]]
    seeds: tuple[int, ...]

    @property
    def all_ids(self) -> tuple[str, ...]:
        return self.train + self.val + self.test

    def ids_for(self, split: str) -> tuple[str, ...]:
        key = split.lower()
        if key in {"train", "training"}:
            return self.train
        if key in {"val", "validation"}:
            return self.val
        if key == "test":
            return self.test
        if key in {name.lower() for name in self.folds}:
            real = next(name for name in self.folds if name.lower() == key)
            return self.folds[real]
        if key == "all":
            return self.all_ids
        raise KeyError(f"Split/fold desconhecido: {split}")

    def validate(self) -> None:
        split_sets = {
            "train": set(self.train),
            "val": set(self.val),
            "test": set(self.test),
        }
        for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
            overlap = split_sets[left] & split_sets[right]
            if overlap:
                raise ConfigError(f"Vazamento entre {left}/{right}: {sorted(overlap)}")
        all_ids = set(self.all_ids)
        if len(all_ids) != len(self.all_ids):
            raise ConfigError("Há IDs duplicados no fixed_split.")
        fold_ids = [video_id for fold in self.folds.values() for video_id in fold]
        if len(fold_ids) != len(set(fold_ids)):
            raise ConfigError("Um vídeo aparece em mais de um fold OOF.")
        if set(fold_ids) != all_ids:
            missing = sorted(all_ids - set(fold_ids))
            extra = sorted(set(fold_ids) - all_ids)
            raise ConfigError(f"Folds não cobrem o split fixo. missing={missing}, extra={extra}")


def load_split_spec(path: str | Path = "configs/protocol/splits.yaml") -> SplitSpec:
    raw = load_config(path)
    fixed = raw.get("fixed_split", {})
    folds_raw = raw.get("oof_folds", {})
    spec = SplitSpec(
        train=_as_ids(fixed.get("train", [])),
        val=_as_ids(fixed.get("val", [])),
        test=_as_ids(fixed.get("test", [])),
        folds={str(name): _as_ids(ids) for name, ids in folds_raw.items()},
        seeds=tuple(int(seed) for seed in raw.get("seeds", [])),
    )
    spec.validate()
    return spec


def load_manifest(path: str | Path = "data/manifests/visem_tracking.csv") -> list[dict[str, str]]:
    manifest_path = Path(path)
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_manifest_against_split(
    split: SplitSpec,
    rows: list[dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    by_id = {row.get("video_id", ""): row for row in rows}
    if len(by_id) != len(rows):
        errors.append("manifest contains duplicated video_id")
    if set(by_id) != set(split.all_ids):
        errors.append(
            f"manifest/split IDs differ: manifest={sorted(by_id)}, split={sorted(split.all_ids)}"
        )
    expected = {
        **{video_id: "train" for video_id in split.train},
        **{video_id: "val" for video_id in split.val},
        **{video_id: "test" for video_id in split.test},
    }
    for video_id, split_name in expected.items():
        if by_id.get(video_id, {}).get("split") != split_name:
            errors.append(f"video {video_id}: expected split {split_name}")
    return errors
