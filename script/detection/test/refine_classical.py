"""Execute the prospectively registered static-classical local refinement."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.core.paths import REPOSITORY_ROOT, resolve_from_repository
from src.experiments.classical_detection_refinement import (
    DEFAULT_PLAN, expand_candidates, load_parents, load_refinement_sample,
    run_batch, load_plan,
)
from src.experiments.config import config_hash
from src.experiments.runs import _git_dirty


def main(argv: list[str] | None = None) -> Path | None:
    parser = argparse.ArgumentParser(description="Refinamento local prospectivo de cinco famílias clássicas, somente no treino.")
    parser.add_argument("--plan", default=DEFAULT_PLAN)
    parser.add_argument("--mode", required=True, choices=("smoke", "refine"))
    parser.add_argument("--smoke-manifest")
    parser.add_argument("--smoke-qa")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    plan = load_plan(resolve_from_repository(args.plan))
    mode = "refinement_smoke" if args.mode == "smoke" else "refinement"
    # Dry-run authenticates existing parent metadata/bytes, never cache pixels,
    # source video decoding or a detector. It is valid before the new commit.
    began = time.perf_counter()
    parents = load_parents(plan)
    parent_seconds = time.perf_counter() - began
    candidates = expand_candidates(plan, parents["parents"])
    if args.dry_run:
        print(json.dumps({"plan_id": plan["plan_id"], "plan_hash": config_hash(plan, 64), "mode": mode, "candidate_count": len(candidates), "family_counts": {family: sum(row["family"] == family for row in candidates) for family in plan["expected_by_family"]}, "proposals": plan["expected_proposals"], "valid_proposals": plan["expected_valid_proposals"], "frames_per_candidate": 12 if args.mode == "smoke" else 576, "frame_evaluations": len(candidates) * (12 if args.mode == "smoke" else 576), "historical_threshold_reference_reexecuted": False, "budget": plan["budget"], "promotion_allowed": False, "validation_released": False}, indent=2))
        return None
    if (args.mode == "refine" and not (args.smoke_manifest and args.smoke_qa)) or (args.mode == "smoke" and (args.smoke_manifest or args.smoke_qa)):
        raise ValueError("Refinamento exige --smoke-manifest e --smoke-qa; smoke não recebe esses argumentos.")
    if _git_dirty(REPOSITORY_ROOT) is not False:
        raise ValueError("Registre código e protocolo em Git limpo antes de acessar a amostra.")
    began = time.perf_counter()
    sample = load_refinement_sample(plan)
    return run_batch(plan, sample, mode, parents=parents, cache_validation_seconds=time.perf_counter() - began, parent_validation_seconds=parent_seconds, smoke_manifest=resolve_from_repository(args.smoke_manifest) if args.smoke_manifest else None, smoke_qa=resolve_from_repository(args.smoke_qa) if args.smoke_qa else None)


if __name__ == "__main__":
    main()
