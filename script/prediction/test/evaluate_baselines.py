"""Run the registered training-only dense baseline comparison, with no overrides."""
from __future__ import annotations

import argparse

from src.experiments.prediction_baselines import run_baselines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(run_baselines(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
