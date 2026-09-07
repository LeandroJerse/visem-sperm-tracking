"""Traceable identity-event metrics (not a replacement for HOTA/TrackEval)."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .assignment import match_cost_matrix, pairwise_center_distance
from .types import TrackDetection, TrackResult


IdentityObject = TrackDetection | TrackResult | Any


@dataclass(frozen=True)
class IdentityEvent:
    frame_index: int
    event: Literal["id_switch", "fragmentation"]
    ground_truth_id: int | str
    previous_prediction_id: int | str | None
    current_prediction_id: int | str | None


@dataclass(frozen=True)
class IdentityMetrics:
    ground_truth_detections: int
    prediction_detections: int
    matches: int
    false_negatives: int
    false_positives: int
    id_switches: int
    fragmentations: int
    detection_recall: float
    detection_precision: float
    events: tuple[IdentityEvent, ...]


def evaluate_identity_events(
    ground_truth_by_frame: Mapping[int, Sequence[IdentityObject]],
    predictions_by_frame: Mapping[int, Sequence[IdentityObject]],
    *,
    max_center_distance: float = 15.0,
    class_aware: bool = False,
) -> IdentityMetrics:
    """Count spatial matches, ID switches and track fragmentations.

    Matching is one-to-one Hungarian matching by center distance.  A
    fragmentation is counted when a visible GT object was previously matched,
    is unmatched for one or more *annotated* frames, and is matched again.  A
    missing GT row does not create a fragmentation, which is important for
    deliberately excluded annotation gaps.
    """
    if max_center_distance <= 0:
        raise ValueError("max_center_distance must be positive")
    frames = sorted(set(ground_truth_by_frame) | set(predictions_by_frame))
    last_prediction: dict[int | str, int | str] = {}
    in_unmatched_gap: dict[int | str, bool] = {}
    events: list[IdentityEvent] = []
    total_gt = total_predictions = total_matches = 0

    for frame in frames:
        gt_objects = list(ground_truth_by_frame.get(frame, ()))
        pred_objects = list(predictions_by_frame.get(frame, ()))
        gt_ids = [_identity(item, ground_truth=True) for item in gt_objects]
        pred_ids = [_identity(item, ground_truth=False) for item in pred_objects]
        if len(set(gt_ids)) != len(gt_ids):
            raise ValueError(f"Duplicate ground-truth ID in frame {frame}")
        if len(set(pred_ids)) != len(pred_ids):
            raise ValueError(f"Duplicate prediction ID in frame {frame}")

        gt_boxes = np.asarray([_box(item) for item in gt_objects], dtype=float).reshape(-1, 4)
        pred_boxes = np.asarray([_box(item) for item in pred_objects], dtype=float).reshape(-1, 4)
        cost = pairwise_center_distance(gt_boxes, pred_boxes)
        if class_aware and cost.size:
            for gt_index, gt_object in enumerate(gt_objects):
                for pred_index, pred_object in enumerate(pred_objects):
                    if _class_id(gt_object) != _class_id(pred_object):
                        cost[gt_index, pred_index] = np.inf
        matches, unmatched_gt, _ = match_cost_matrix(
            cost, max_cost=max_center_distance
        )
        total_gt += len(gt_objects)
        total_predictions += len(pred_objects)
        total_matches += len(matches)

        for gt_index, prediction_index in matches:
            gt_id = gt_ids[gt_index]
            prediction_id = pred_ids[prediction_index]
            previous = last_prediction.get(gt_id)
            if previous is not None and previous != prediction_id:
                events.append(
                    IdentityEvent(
                        frame_index=frame,
                        event="id_switch",
                        ground_truth_id=gt_id,
                        previous_prediction_id=previous,
                        current_prediction_id=prediction_id,
                    )
                )
            if in_unmatched_gap.get(gt_id, False):
                events.append(
                    IdentityEvent(
                        frame_index=frame,
                        event="fragmentation",
                        ground_truth_id=gt_id,
                        previous_prediction_id=previous,
                        current_prediction_id=prediction_id,
                    )
                )
            last_prediction[gt_id] = prediction_id
            in_unmatched_gap[gt_id] = False

        for gt_index in unmatched_gt:
            gt_id = gt_ids[gt_index]
            if gt_id in last_prediction:
                in_unmatched_gap[gt_id] = True

    false_negatives = total_gt - total_matches
    false_positives = total_predictions - total_matches
    recall = total_matches / total_gt if total_gt else 0.0
    precision = total_matches / total_predictions if total_predictions else 0.0
    return IdentityMetrics(
        ground_truth_detections=total_gt,
        prediction_detections=total_predictions,
        matches=total_matches,
        false_negatives=false_negatives,
        false_positives=false_positives,
        id_switches=sum(event.event == "id_switch" for event in events),
        fragmentations=sum(event.event == "fragmentation" for event in events),
        detection_recall=recall,
        detection_precision=precision,
        events=tuple(events),
    )


def _box(item: IdentityObject) -> tuple[float, float, float, float]:
    try:
        return (float(item.cx), float(item.cy), float(item.w), float(item.h))
    except AttributeError as exc:
        raise TypeError("Metric objects must expose cx, cy, w and h") from exc


def _class_id(item: IdentityObject) -> int:
    return int(getattr(item, "class_id", 0))


def _identity(item: IdentityObject, *, ground_truth: bool) -> int | str:
    if isinstance(item, TrackResult):
        return item.track_id
    candidate = getattr(item, "object_id", None)
    if candidate is None or candidate == -1:
        role = "ground truth" if ground_truth else "prediction"
        raise ValueError(f"Every {role} metric object must have a persistent ID")
    return candidate
