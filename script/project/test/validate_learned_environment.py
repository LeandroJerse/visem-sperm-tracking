"""Validate the isolated CUDA runtime with synthetic inputs and random weights.

This engineering check does not load VISEM data, download model weights, train
on observations, calculate accuracy, or certify a scientific comparison.
Run as a module from the repository root; commands are in script/README.md.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[3]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args: list[str]) -> dict:
    process = subprocess.run(args, capture_output=True, text=True, check=False)
    return {
        "command": args,
        "returncode": process.returncode,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
    }


@contextmanager
def no_network():
    """Reject socket connections during imports and synthetic computations."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create = socket.create_connection

    def blocked(*args, **kwargs):
        raise OSError("Network disabled for the synthetic environment validation")

    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.create_connection = blocked
    try:
        yield
    finally:
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
        socket.create_connection = original_create


def validate(report: dict) -> None:
    """Perform checks sequentially so a failure identifies the exact stage."""
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError("This locked Windows environment requires Python 3.13")
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Use a virtual environment, not the system Python")
    report["pip_check"] = command([sys.executable, "-m", "pip", "check"])
    if report["pip_check"]["returncode"]:
        raise RuntimeError("pip check failed")
    lock = ROOT / "requirements-ml.lock"
    expected = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "--")):
            name, version = line.split("==", 1)
            expected[name] = version
            actual = importlib.metadata.version(name)
            if actual != version:
                raise RuntimeError(f"Locked package differs: {name}: {actual} != {version}")
    report["locked_packages"] = expected
    report["lock_sha256"] = digest(lock)
    for env_name, folder in {
        "YOLO_CONFIG_DIR": "ultralytics",
        "TORCH_HOME": "torch",
        "MPLCONFIGDIR": "matplotlib",
    }.items():
        directory = Path(sys.prefix) / "local_cache" / folder
        directory.mkdir(parents=True, exist_ok=True)
        os.environ[env_name] = str(directory)
    os.environ["YOLO_OFFLINE"] = "true"
    os.environ["YOLO_AUTOINSTALL"] = "false"
    report["stages"] = []
    with no_network():
        import numpy as np
        import torch
        import torchvision
        from torchvision.ops import nms

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required; CPU fallback is not a pass")
        torch.manual_seed(report["seed"])
        torch.cuda.manual_seed_all(report["seed"])
        torch.set_num_threads(2)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.cuda.reset_peak_memory_stats()
        device = torch.device("cuda:0")
        properties = torch.cuda.get_device_properties(device)
        report["cuda"] = {
            "torch_version": torch.__version__,
            "torchvision_version": torchvision.__version__,
            "runtime_version": torch.version.cuda,
            "cudnn_version": torch.backends.cudnn.version(),
            "device": str(device),
            "name": properties.name,
            "total_memory_bytes": properties.total_memory,
            "compute_capability": [properties.major, properties.minor],
            "compiled_architectures": torch.cuda.get_arch_list(),
            "device_count": torch.cuda.device_count(),
        }
        matrix = torch.ones((64, 64), device=device)
        product = matrix @ matrix
        torch.cuda.synchronize()
        if not bool(torch.all(product == 64).item()):
            raise RuntimeError("CUDA matrix multiplication returned unexpected values")
        report["stages"].append({"name": "cuda_matmul", "status": "passed", "shape": [64, 64]})

        boxes = torch.tensor([[0, 0, 10, 10], [1, 1, 11, 11], [30, 30, 40, 40]], dtype=torch.float32, device=device)
        scores = torch.tensor([0.9, 0.8, 0.7], device=device)
        kept = nms(boxes, scores, 0.5).cpu().tolist()
        if kept != [0, 2]:
            raise RuntimeError(f"CUDA torchvision NMS returned {kept}")
        report["stages"].append({"name": "torchvision_nms_cuda", "status": "passed", "kept_indices": kept})

        from src.flow.learned.raft import RAFTFlow

        rng = np.random.default_rng(report["seed"])
        previous = rng.integers(0, 256, (128, 128, 3), dtype=np.uint8)
        following = np.roll(previous, 1, axis=1)
        raft = RAFTFlow(variant="small", weights=None, device="cuda:0", mixed_precision=False)
        flow = raft.estimate(previous, following)
        if flow.flow.shape != (128, 128, 2) or not np.isfinite(flow.flow).all():
            raise RuntimeError("Random RAFT did not return finite dense output")
        if not flow.valid.all():
            raise RuntimeError("Unexpected invalid support in unmasked RAFT architecture check")
        report["stages"].append({
            "name": "repository_raft_small_cuda", "status": "passed",
            "weights": None, "input_shape": [128, 128, 3], "output_shape": list(flow.flow.shape),
            "mixed_precision": False, "accuracy_evaluated": False,
        })
        del raft, flow
        torch.cuda.empty_cache()

        import ultralytics
        from ultralytics.nn.tasks import DetectionModel
        from ultralytics.utils import SETTINGS
        import yaml

        SETTINGS.update({"sync": False})
        architecture_file = Path(ultralytics.__file__).parent / "cfg" / "models" / "v8" / "yolov8.yaml"
        architecture = yaml.safe_load(architecture_file.read_text(encoding="utf-8"))
        architecture["scale"] = "n"
        architecture["nc"] = 3
        detector = DetectionModel(architecture, ch=3, nc=3, verbose=False).to(device).eval()
        with torch.inference_mode():
            raw = detector(torch.zeros((1, 3, 128, 128), device=device))
        prediction = raw[0] if isinstance(raw, tuple) else raw
        if prediction.ndim != 3 or prediction.shape[:2] != (1, 7) or not bool(torch.isfinite(prediction).all().item()):
            raise RuntimeError("Random YOLOv8n did not return finite 3-class output")
        report["stages"].append({
            "name": "ultralytics_yolov8n_cuda", "status": "passed", "weights": None,
            "classes": 3, "input_shape": [1, 3, 128, 128], "output_shape": list(prediction.shape),
            "architecture_sha256": digest(architecture_file), "accuracy_evaluated": False,
        })
        del detector, raw, prediction
        torch.cuda.empty_cache()

        from src.prediction.learned.lstm import LSTMPredictor

        for use_flow in (False, True):
            predictor = LSTMPredictor(history_length=20, max_horizon=10, hidden_size=64, use_flow=use_flow, device="cuda:0", seed=report["seed"])
            _, model = predictor._build_model()
            model.train()
            features = torch.randn((2, 19, 4 if use_flow else 2), device=device)
            output = model(features)
            loss = output.square().mean()
            loss.backward()
            if output.shape != (2, 10, 2) or not bool(torch.isfinite(output).all().item()):
                raise RuntimeError("LSTM architecture returned invalid output")
            gradients = [parameter.grad for parameter in model.parameters() if parameter.requires_grad]
            if not gradients or any(gradient is None or not bool(torch.isfinite(gradient).all().item()) for gradient in gradients):
                raise RuntimeError("LSTM backward returned missing or non-finite gradients")
            report["stages"].append({
                "name": "repository_lstm_flow_cuda" if use_flow else "repository_lstm_cuda",
                "status": "passed", "weights": None, "input_shape": list(features.shape),
                "output_shape": list(output.shape), "parameter_count": sum(p.numel() for p in model.parameters()),
                "finite_backward": True, "optimizer_steps": 0, "accuracy_evaluated": False,
            })
            del predictor, model, features, output, loss, gradients
        torch.cuda.synchronize()
        report["cuda"]["peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
        report["cuda"]["peak_reserved_bytes"] = torch.cuda.max_memory_reserved()
        report["cuda"]["free_memory_bytes_at_end"] = torch.cuda.mem_get_info()[0]
        import psutil

        report["process_memory_bytes"] = psutil.Process().memory_info()._asdict()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc)
    output = args.output or ROOT / "data" / "derived" / "project_audits" / "learned_environment" / f"{stamp:%Y%m%dT%H%M%S%fZ}.json"
    output = output.resolve()
    # Reserve the result before touching the runtime; never overwrite a receipt.
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "learned_environment_validation_v1", "started_utc": stamp.isoformat(),
        "status": "running", "seed": args.seed, "scientific_run": False,
        "source_data_read": False, "external_weights_loaded": False,
        "network_connections_disabled_during_checks": True,
        "interpreter": sys.executable, "python_version": platform.python_version(),
        "platform": platform.platform(), "source_sha256": digest(Path(__file__)),
        "implementation_sha256": {name: digest(ROOT / name) for name in (
            "src/flow/learned/raft.py", "src/prediction/learned/lstm.py",
        )},
        "git_head": command(["git", "rev-parse", "HEAD"]),
        "git_status": command(["git", "status", "--short"]),
        "nvidia_smi": command(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,compute_cap", "--format=csv,noheader"]),
    }
    started = time.perf_counter()
    exit_code = 0
    with output.open("x", encoding="utf-8") as handle:
        try:
            validate(report)
            report["status"] = "passed"
        except Exception as exc:
            exit_code = 1
            report["status"] = "failed"
            report["error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        report["elapsed_seconds"] = time.perf_counter() - started
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status": report["status"], "output": str(output), "elapsed_seconds": report["elapsed_seconds"]}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
