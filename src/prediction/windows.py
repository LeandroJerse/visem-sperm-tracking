"""Leakage-safe trajectory windows grouped exclusively by source video."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class TrajectoryWindow:
    """One contiguous history/future sample from one video and one track."""

    video_id: str
    track_id: str
    split: str
    history_frames: np.ndarray
    future_frames: np.ndarray
    history: np.ndarray
    future: np.ndarray
    flow_history: np.ndarray | None = None
    future_flow: np.ndarray | None = None

    def __post_init__(self) -> None:
        history_frames = np.asarray(self.history_frames, dtype=int)
        future_frames = np.asarray(self.future_frames, dtype=int)
        history = np.asarray(self.history, dtype=np.float32)
        future = np.asarray(self.future, dtype=np.float32)
        if history.shape != (len(history_frames), 2) or future.shape != (len(future_frames), 2):
            raise ValueError("position arrays must align with their frame arrays")
        frames = np.concatenate((history_frames, future_frames))
        if len(frames) > 1 and not np.all(np.diff(frames) == 1):
            raise ValueError("a trajectory window cannot cross a frame gap")
        if self.flow_history is not None:
            flow_history = np.asarray(self.flow_history, dtype=np.float32)
            if flow_history.shape != (max(len(history) - 1, 0), 2):
                raise ValueError("flow_history must align with history transitions")
            object.__setattr__(self, "flow_history", flow_history)
        if self.future_flow is not None:
            future_flow = np.asarray(self.future_flow, dtype=np.float32)
            if future_flow.shape != (len(future), 2):
                raise ValueError("future_flow must align with future transitions")
            object.__setattr__(self, "future_flow", future_flow)
        object.__setattr__(self, "history_frames", history_frames)
        object.__setattr__(self, "future_frames", future_frames)
        object.__setattr__(self, "history", history)
        object.__setattr__(self, "future", future)

    def targets_at(self, horizons: Sequence[int]) -> np.ndarray:
        requested = np.asarray(tuple(horizons), dtype=int)
        if np.any(requested <= 0) or np.any(requested > len(self.future)):
            raise ValueError("requested horizon is outside this window")
        return self.future[requested - 1]


def _normalize_transition_flows(
    flow: np.ndarray | None, number_of_positions: int
) -> np.ndarray | None:
    if flow is None:
        return None
    values = np.asarray(flow, dtype=np.float32)
    if values.shape == (number_of_positions, 2):
        values = values[:-1]
    if values.shape != (max(number_of_positions - 1, 0), 2):
        raise ValueError(
            "flow must contain one vector per position or per inter-frame transition"
        )
    if not np.isfinite(values).all():
        raise ValueError("flow contains NaN or infinite values")
    return values


def make_trajectory_windows(
    positions: np.ndarray,
    frame_ids: Sequence[int],
    *,
    video_id: str,
    track_id: str,
    split: str,
    history_length: int = 20,
    forecast_horizon: int = 10,
    stride: int = 1,
    flow: np.ndarray | None = None,
    annotated: Sequence[bool] | None = None,
) -> list[TrajectoryWindow]:
    """Create only fully annotated, consecutive windows from one trajectory.

    Gaps (including the unannotated intervals in VISEM video 23) invalidate a
    candidate window instead of being interpreted as motion or negative data.
    """

    if history_length < 2 or forecast_horizon <= 0 or stride <= 0:
        raise ValueError("history_length >= 2, forecast_horizon > 0, stride > 0 required")
    positions_array = np.asarray(positions, dtype=np.float32)
    frames = np.asarray(frame_ids, dtype=int)
    if positions_array.shape != (len(frames), 2):
        raise ValueError("positions must have shape (len(frame_ids), 2)")
    if not np.isfinite(positions_array).all():
        raise ValueError("positions contain NaN or infinite values")
    annotation_mask = (
        np.ones(len(frames), dtype=bool)
        if annotated is None
        else np.asarray(annotated, dtype=bool)
    )
    if annotation_mask.shape != (len(frames),):
        raise ValueError("annotated must have one value per frame")
    transition_flows = _normalize_transition_flows(flow, len(frames))
    sample_length = history_length + forecast_horizon
    windows: list[TrajectoryWindow] = []
    for start in range(0, len(frames) - sample_length + 1, stride):
        stop = start + sample_length
        segment_frames = frames[start:stop]
        if not annotation_mask[start:stop].all() or not np.all(np.diff(segment_frames) == 1):
            continue
        future_start = start + history_length
        flow_history = None
        future_flow = None
        if transition_flows is not None:
            flow_history = transition_flows[start : future_start - 1]
            # Transition H-1 maps the last history point to the first future point.
            future_flow = transition_flows[
                future_start - 1 : future_start - 1 + forecast_horizon
            ]
        windows.append(
            TrajectoryWindow(
                video_id=str(video_id),
                track_id=str(track_id),
                split=str(split),
                history_frames=segment_frames[:history_length],
                future_frames=segment_frames[history_length:],
                history=positions_array[start:future_start],
                future=positions_array[future_start:stop],
                flow_history=flow_history,
                future_flow=future_flow,
            )
        )
    return windows


def validate_video_splits(split_by_video: Mapping[str, Iterable[str]]) -> dict[str, str]:
    """Validate disjoint video groups and return ``video -> split``."""

    video_to_split: dict[str, str] = {}
    for split, video_ids in split_by_video.items():
        for video_id in video_ids:
            normalized = str(video_id)
            previous = video_to_split.get(normalized)
            if previous is not None:
                raise ValueError(
                    f"video {normalized} appears in both '{previous}' and '{split}'"
                )
            video_to_split[normalized] = str(split)
    return video_to_split


def build_windows_by_split(
    records: Iterable[Mapping[str, Any]],
    split_by_video: Mapping[str, Iterable[str]],
    *,
    history_length: int = 20,
    forecast_horizon: int = 10,
    stride: int = 1,
) -> dict[str, list[TrajectoryWindow]]:
    """Build samples without ever splitting one video across data partitions.

    Each record must contain ``video_id``, ``track_id``, ``positions``, and
    ``frame_ids``; optional keys are ``flow`` and ``annotated``.
    """

    video_to_split = validate_video_splits(split_by_video)
    output = {str(split): [] for split in split_by_video}
    for record in records:
        video_id = str(record["video_id"])
        if video_id not in video_to_split:
            raise ValueError(f"video {video_id} has no assigned split")
        split = video_to_split[video_id]
        output[split].extend(
            make_trajectory_windows(
                record["positions"],
                record["frame_ids"],
                video_id=video_id,
                track_id=str(record["track_id"]),
                split=split,
                history_length=history_length,
                forecast_horizon=forecast_horizon,
                stride=stride,
                flow=record.get("flow"),
                annotated=record.get("annotated"),
            )
        )
    return output
