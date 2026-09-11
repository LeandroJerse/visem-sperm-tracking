"""Run the registered static classical comparison on the authenticated train cache."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.core.paths import resolve_from_repository
from src.experiments.classical_detection_comparison import (
    DEFAULT_PLAN, expand_candidates, load_comparison_sample, run_batch,
)
from src.experiments.config import config_hash, load_config
from src.experiments.runs import _git_dirty
from src.core.paths import REPOSITORY_ROOT


def main(argv: list[str] | None = None) -> Path | None:
    parser = argparse.ArgumentParser(description="Comparação prospectiva de detectores estáticos clássicos, somente no treino.")
    parser.add_argument("--plan", default=DEFAULT_PLAN)
    parser.add_argument("--mode", required=True, choices=("smoke", "search"))
    parser.add_argument("--smoke-manifest")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    plan = load_config(resolve_from_repository(args.plan))
    candidates = expand_candidates(plan)
    if args.dry_run:
        counts = {family: sum(item["family"] == family for item in candidates)
                  for family in dict.fromkeys(item["family"] for item in candidates)}
        print(json.dumps({"plan_id": plan["plan_id"], "plan_hash": config_hash(plan, 64),
                          "mode": args.mode, "candidate_count": len(candidates), "family_counts": counts,
                          "frames_per_candidate": 12 if args.mode == "smoke" else 576,
                          "frame_evaluations": len(candidates) * (12 if args.mode == "smoke" else 576),
                          "budget": plan["budget"], "promotion_allowed": False, "validation_released": False}, indent=2))
        return None
    if (args.mode == "search") != bool(args.smoke_manifest):
        raise ValueError("--smoke-manifest é obrigatório na busca e não se aplica ao smoke.")
    if _git_dirty(REPOSITORY_ROOT) is not False:
        raise ValueError("Registre o código e protocolo em Git limpo antes de acessar a amostra.")
    started = time.perf_counter()
    sample = load_comparison_sample(plan)
    return run_batch(plan, sample, args.mode, cache_validation_seconds=time.perf_counter() - started,
                     smoke_manifest=resolve_from_repository(args.smoke_manifest) if args.smoke_manifest else None)


if __name__ == "__main__":
    main()
