from __future__ import annotations

from pathlib import Path

import pytest

from src.detection import split_runner as run_split


def _fake_annotated_tree(root: Path, ids: tuple[str, ...]) -> None:
    for video_id in ids:
        folder = root / video_id
        (folder / "labels_ftid").mkdir(parents=True)
        (folder / f"{video_id}.mp4").write_bytes(b"video")


def test_split_runner_selects_validation_videos_and_builds_full_video_commands(
    tmp_path, monkeypatch
):
    root = tmp_path / "Train"
    ids = ("14", "19", "36", "52")
    _fake_annotated_tree(root, ids)
    calls = []

    def fake_main(command):
        calls.append(command)
        return {"video_id": Path(command[command.index("--video") + 1]).stem}

    monkeypatch.setattr(run_split.detection_pipeline, "main", fake_main)
    summaries = run_split.main(
        [
            "--config", "configs/detection/threshold/t200_o1_c2.yaml",
            "--split", "val",
            "--train-root", str(root),
            "--save-video",
        ]
    )
    assert [summary["video_id"] for summary in summaries] == list(ids)
    assert len(calls) == 4
    assert all("--max-frames" not in command for command in calls)
    assert all("--no-video" not in command for command in calls)


def test_split_runner_blocks_test_until_configuration_is_frozen(tmp_path):
    with pytest.raises(SystemExit, match="bloqueado|congelada"):
        run_split.main(
            [
                "--config", "configs/detection/threshold/t200_o1_c2.yaml",
                "--split", "test",
                "--train-root", str(tmp_path),
            ]
        )


def test_video_filter_cannot_escape_declared_split(tmp_path):
    with pytest.raises(SystemExit, match="fora do split"):
        run_split.main(
            [
                "--config", "configs/detection/threshold/t200_o1_c2.yaml",
                "--split", "val",
                "--video-id", "24",
                "--train-root", str(tmp_path),
            ]
        )


def test_all_alias_cannot_leak_test_videos_during_search(tmp_path):
    with pytest.raises(SystemExit, match="inclui o teste"):
        run_split.main(
            [
                "--config", "configs/detection/threshold/t200_o1_c2.yaml",
                "--split", "all",
                "--stage", "search",
                "--train-root", str(tmp_path),
            ]
        )
    with pytest.raises(SystemExit, match="inclui o teste"):
        run_split.main(
            [
                "--config", "configs/detection/threshold/t200_o1_c2.yaml",
                "--split", "all",
                "--stage", "search",
                "--frozen",
                "--train-root", str(tmp_path),
            ]
        )


def test_fold_defaults_to_five_fold_and_uses_only_promoted_yaml(tmp_path, monkeypatch):
    root = tmp_path / "Train"
    ids = ("13", "14", "19", "60")  # fold B
    _fake_annotated_tree(root, ids)
    calls = []
    monkeypatch.setattr(
        run_split.detection_pipeline,
        "main",
        lambda command: calls.append(command) or {"ok": True},
    )

    summaries = run_split.main(
        [
            "--config", "configs/frozen/detection/threshold/t200_o1_c2.yaml",
            "--split", "B",
            "--frozen",
            "--train-root", str(root),
        ]
    )
    assert len(summaries) == 4
    assert all(command[command.index("--stage") + 1] == "five_fold" for command in calls)
    assert all(command[command.index("--split") + 1] == "B" for command in calls)


def test_frozen_split_runner_rejects_candidate_yaml_before_touching_video_tree(tmp_path):
    with pytest.raises(SystemExit, match="configs/frozen"):
        run_split.main(
            [
                "--config", "configs/detection/threshold/t200_o1_c2.yaml",
                "--split", "test",
                "--stage", "test",
                "--frozen",
                "--train-root", str(tmp_path / "does-not-exist"),
            ]
        )


def test_frozen_split_runner_rejects_scientific_and_reserved_overrides(tmp_path):
    base = [
        "--config", "configs/frozen/detection/threshold/t200_o1_c2.yaml",
        "--split", "test",
        "--stage", "test",
        "--frozen",
        "--train-root", str(tmp_path / "does-not-exist"),
    ]
    with pytest.raises(SystemExit, match="parâmetros científicos"):
        run_split.main([*base, "--set", "threshold_value=190"])
    with pytest.raises(SystemExit, match="argumentos dedicados"):
        run_split.main([*base, "--set", "input.video=11.mp4"])


def test_frozen_split_runner_forbids_partial_video(tmp_path):
    with pytest.raises(SystemExit, match="vídeo completo"):
        run_split.main(
            [
                "--config", "configs/frozen/detection/threshold/t200_o1_c2.yaml",
                "--split", "test",
                "--stage", "test",
                "--frozen",
                "--max-frames", "10",
                "--train-root", str(tmp_path / "does-not-exist"),
            ]
        )
