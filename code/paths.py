"""Release-package path helpers (no machine-specific absolute paths)."""
from __future__ import annotations

import os
from pathlib import Path

# CPENG-8450-release/
REPO_ROOT = Path(__file__).resolve().parents[1]


def data_augmented_dir() -> Path:
    env = os.environ.get("CPENG_DATA_DIR")
    if env:
        return Path(env)
    return REPO_ROOT / "data" / "numerical" / "data_augmented"


def hyperparams_path() -> Path:
    env = os.environ.get("CPENG_HYPERPARAMS")
    if env:
        return Path(env)
    return REPO_ROOT / "configs" / "best_hyperparameters.json"


def checkpoints_dir() -> Path:
    return REPO_ROOT / "checkpoints"


def field_npz_path() -> Path:
    env = os.environ.get("CPENG_FIELD_NPZ")
    if env:
        return Path(env)
    return REPO_ROOT / "data" / "field" / "transfer_dataset_v1.npz"


def ensure_models_on_path() -> Path:
    """Put code/models on sys.path so `import attention_module` works."""
    import sys

    models = Path(__file__).resolve().parent / "models"
    s = str(models)
    if s not in sys.path:
        sys.path.insert(0, s)
    return models
