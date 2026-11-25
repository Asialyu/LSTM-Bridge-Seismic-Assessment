#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
Summarize multi-seed training results (mean/std).


# --- release path bootstrap (no machine-specific absolute paths) ---
from pathlib import Path as _Path
import sys as _sys
_CODE_DIR = _Path(__file__).resolve().parents[1]  # .../code
if str(_CODE_DIR) not in _sys.path:
    _sys.path.insert(0, str(_CODE_DIR))
from paths import data_augmented_dir, hyperparams_path, ensure_models_on_path, REPO_ROOT
ensure_models_on_path()
# --- end bootstrap ---
Usage (PowerShell):
  python .\summarize_multiseed_results.py --root "..\results_parent" --pattern "results_m4_final_combined_seed*"

It looks for training_results.json in each matched folder and extracts:
  - test_metrics.* (rmse/mae/r2/ci/peak_rmse_mm) when present
  - or final_test_metrics.* if that's the key used by the trainer
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev


METRIC_KEYS = ["rmse", "mae", "r2", "ci", "peak_rmse_mm"]


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _extract_test_metrics(obj: dict) -> dict | None:
    for key in ["test_metrics", "final_test_metrics", "test", "metrics_test"]:
        v = obj.get(key)
        if isinstance(v, dict):
            return v
    return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--pattern", type=str, default="results_m4_final_combined_seed*")
    p.add_argument("--out", type=str, default="multiseed_summary.csv")
    args = p.parse_args()

    root = Path(args.root).resolve()
    dirs = sorted([d for d in root.glob(args.pattern) if d.is_dir()])
    if not dirs:
        raise SystemExit(f"No directories matched pattern under {root}: {args.pattern}")

    rows = []
    for d in dirs:
        tr = d / "training_results.json"
        if not tr.exists():
            continue
        obj = _read_json(tr)
        m = _extract_test_metrics(obj) or {}
        row = {"dir": d.name}
        for k in METRIC_KEYS:
            v = m.get(k)
            row[k] = float(v) if v is not None else None
        row["seed"] = obj.get("seed", None)
        rows.append(row)

    if not rows:
        raise SystemExit("Found directories, but none had training_results.json with test metrics.")

    # aggregate
    agg = {}
    for k in METRIC_KEYS:
        vals = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
        if not vals:
            continue
        agg[k] = {"mean": mean(vals), "std": pstdev(vals) if len(vals) > 1 else 0.0, "n": len(vals)}

    # write csv
    out_path = (Path.cwd() / args.out).resolve()
    cols = ["dir", "seed"] + METRIC_KEYS
    with out_path.open("w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(r.get(c, "")) for c in cols) + "\n")
        f.write("\n")
        f.write("metric,mean,std,n\n")
        for k, v in agg.items():
            f.write(f"{k},{v['mean']},{v['std']},{v['n']}\n")

    print(f"Wrote: {out_path}")
    print("Aggregate:")
    for k, v in agg.items():
        print(f"  {k}: mean={v['mean']:.6g}, std={v['std']:.6g}, n={v['n']}")


if __name__ == "__main__":
    main()

