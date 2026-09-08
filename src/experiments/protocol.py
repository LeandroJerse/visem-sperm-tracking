"""Small, enforceable guards for the experimental protocol.

The functions in this module deliberately run before opening an input video.
They are not a substitute for scientific review, but make the most dangerous
split/configuration mistakes fail closed at the command-line boundary.
"""
from __future__ import annotations

from collections.abc import Iterable
import hashlib
from pathlib import Path

from src.core.paths import REPOSITORY_ROOT
from src.experiments.config import load_config
from src.experiments.dataset import load_split_spec


class ProtocolViolation(RuntimeError):
    """Raised before a run that would leak the blocked test set."""


SEARCH_STAGES = {"development", "smoke", "screen", "search", "refine", "validation"}
FOLD_SPLITS = frozenset({"a", "b", "c", "d", "e"})
FOLD_STAGES = frozenset({"five_fold", "oof", "cross_validation"})
FROZEN_STAGES = {
    "test",
    *FOLD_STAGES,
    "final",
    "application",
}

# Frozen scientific parameters come exclusively from the promoted YAML.  A
# caller may still select the sequence and presentation/provenance details.
FROZEN_OPERATIONAL_OVERRIDE_KEYS = frozenset(
    {
        "input.video",
        "input.gt_dir",
        "input.videos_csv",
        "run.stage",
        "run.split",
        "run.seed",
        "run.save_video",
        "run.draw_mode",
        "run.render",
        "run.frozen",
    }
)


def _normalize(value: object) -> str:
    return str(value).strip().lower().replace("-", "_")


def _override_key(expression: str) -> str:
    if "=" not in expression:
        raise ProtocolViolation(f"Override deve usar chave=valor: {expression!r}")
    key = expression.split("=", 1)[0].strip()
    if not key:
        raise ProtocolViolation(f"Chave vazia no override: {expression!r}")
    return key


def assert_frozen_config_source(
    config_path: str | Path | None,
    *,
    repo_root: str | Path | None = None,
) -> Path:
    """Require a real YAML located below ``configs/frozen``.

    ``Path.resolve`` also prevents ``..`` and symlink-based escapes from being
    mistaken for promoted configurations.  The resolved path is returned so
    callers can record the exact source in their manifest.
    """

    if config_path in (None, ""):
        raise ProtocolViolation(
            "Uma run congelada exige --config apontando para um YAML em configs/frozen/."
        )
    root = Path(repo_root) if repo_root is not None else REPOSITORY_ROOT
    frozen_root = (root / "configs" / "frozen").resolve()
    candidate = Path(config_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if candidate.suffix.lower() not in {".yaml", ".yml"} or not candidate.is_file():
        raise ProtocolViolation(
            f"Configuração congelada deve ser um YAML existente: {candidate}"
        )
    try:
        candidate.relative_to(frozen_root)
    except ValueError as exc:
        raise ProtocolViolation(
            "Runs congeladas aceitam somente YAML promovido em configs/frozen/."
        ) from exc
    return candidate


def assert_frozen_overrides(
    overrides: Iterable[str],
    *,
    allowed_keys: Iterable[str] = FROZEN_OPERATIONAL_OVERRIDE_KEYS,
) -> None:
    """Reject scientific CLI overrides for a frozen configuration.

    Bare keys are intentionally rejected: in the experiment CLIs they are
    aliases for ``params.<key>`` and therefore scientific parameters.
    """

    allowed = set(allowed_keys)
    forbidden = sorted(
        key for key in (_override_key(item) for item in overrides) if key not in allowed
    )
    if forbidden:
        raise ProtocolViolation(
            "Configuração congelada não permite alterar parâmetros científicos "
            f"via --set: {forbidden}. Crie/promova outro YAML."
        )


def assert_frozen_release(
    config_path: str | Path | None,
    *,
    stage: str,
    split: str,
    frozen: bool,
    splits_config: str | Path | None = None,
) -> None:
    """Enforce a scoped release from the original YAML before input access.

    A development baseline freezes parameters without authorizing test, OOF
    or application. Read the source rather than the merged configuration so
    CLI overrides cannot erase its scope or disable its frozen status. YAMLs
    without a ``freeze`` block retain the historical guard contract.
    """
    if config_path in (None, ""):
        return
    source = Path(config_path)
    if not source.is_absolute():
        source = REPOSITORY_ROOT / source
    raw = load_config(source)
    if "freeze" not in raw:
        return
    release = raw["freeze"]
    if (
        not isinstance(release, dict)
        or set(release) != {"scope", "allowed_splits", "confirmatory_plan"}
        or release.get("scope") != "development_only"
        or release.get("confirmatory_plan") is not None
    ):
        raise ProtocolViolation(
            "Bloco freeze inválido: somente development_only, allowed_splits e "
            "confirmatory_plan: null estão autorizados. Confirmação exige plano próprio."
        )
    allowed = release["allowed_splits"]
    if (
        not isinstance(allowed, list)
        or not allowed
        or any(not isinstance(value, str) or value not in {"train", "val"} for value in allowed)
        or len(set(allowed)) != len(allowed)
    ):
        raise ProtocolViolation("freeze.allowed_splits deve conter apenas train/val, sem repetição.")
    assert_frozen_config_source(source)
    raw_run = raw.get("run")
    if not isinstance(raw_run, dict) or raw_run.get("frozen") is not True or frozen is not True:
        raise ProtocolViolation(
            "Baseline development_only exige run.frozen=true na fonte e na execução; "
            "não é permitido desativar o congelamento via CLI."
        )
    pair = (_normalize(stage), _normalize(split))
    allowed_pairs = {("development", "train"), ("smoke", "train"), ("validation", "val")}
    if pair not in allowed_pairs or pair[1] not in allowed:
        raise ProtocolViolation(
            "Baseline development_only permite somente development/train, smoke/train "
            "ou validation/val. Teste, folds, all e aplicação continuam bloqueados."
        )
    protocol = raw.get("protocol") or {}
    if not isinstance(protocol, dict):
        raise ProtocolViolation("A seção protocol do baseline deve ser um mapping.")
    registered_split = protocol.get("splits_config", "configs/protocol/splits.yaml")
    if not isinstance(registered_split, str) or not registered_split:
        raise ProtocolViolation("protocol.splits_config do baseline deve identificar o YAML dos splits.")

    def resolved(value: str | Path) -> Path:
        path = Path(value)
        return (path if path.is_absolute() else REPOSITORY_ROOT / path).resolve()

    effective_split = splits_config if splits_config is not None else registered_split
    if resolved(effective_split) != resolved(registered_split):
        raise ProtocolViolation("Baseline development_only não permite trocar protocol.splits_config.")
    registered_hash = protocol.get("splits_sha256")
    if registered_hash is not None:
        split_path = resolved(registered_split)
        if (
            not isinstance(registered_hash, str)
            or not split_path.is_file()
            or hashlib.sha256(split_path.read_bytes()).hexdigest() != registered_hash
        ):
            raise ProtocolViolation("O hash dos splits diverge do baseline development_only.")


def assert_protocol_access(*, stage: str, split: str, frozen: bool) -> None:
    """Reject test/final execution before hyperparameters are frozen.

    This guard cannot decide whether a scientific decision was honest, but it
    makes accidental test-set use explicit and machine visible in the config.
    """
    normalized_stage = _normalize(stage)
    normalized_split = _normalize(split)

    if normalized_split == "all" and (
        normalized_stage != "final" or not frozen
    ):
        raise ProtocolViolation(
            "O split 'all' inclui o teste e só pode ser usado com "
            "stage='final' e configuração congelada."
        )

    if normalized_split == "application" and normalized_stage != "application":
        raise ProtocolViolation(
            "O split 'application' só pode ser usado com stage='application'."
        )
    if normalized_stage == "application" and normalized_split != "application":
        raise ProtocolViolation(
            "A etapa 'application' deve registrar split='application'."
        )

    # The held-out test has exactly one legal semantic label in both
    # directions; aliases such as final/test or test/final are rejected.
    if normalized_split == "test" and normalized_stage != "test":
        raise ProtocolViolation("O split 'test' só pode ser usado com stage='test'.")
    if normalized_stage == "test" and normalized_split != "test":
        raise ProtocolViolation("A etapa 'test' deve registrar split='test'.")

    # A-E are out-of-fold partitions, not development/validation aliases.
    if normalized_split in FOLD_SPLITS:
        if normalized_stage not in FOLD_STAGES:
            raise ProtocolViolation(
                f"O fold {normalized_split.upper()} só pode ser executado em "
                "stage five_fold, oof ou cross_validation."
            )
        if not frozen:
            raise ProtocolViolation(
                f"O fold {normalized_split.upper()} exige configuração congelada."
            )
    elif normalized_stage in FOLD_STAGES:
        raise ProtocolViolation(
            f"A etapa {normalized_stage!r} exige split igual a um fold A-E."
        )

    if normalized_split == "test" and not frozen:
        raise ProtocolViolation(
            "O split de teste está bloqueado. Congele a configuração e use "
            "run.frozen=true somente depois da seleção em treino/validação."
        )
    if normalized_stage in FROZEN_STAGES and not frozen:
        raise ProtocolViolation(
            f"A etapa {normalized_stage!r} exige uma configuração congelada "
            "(run.frozen=true)."
        )


def assert_video_ids_in_split(
    video_ids: Iterable[object],
    *,
    split: str,
    splits_config: str | Path | None = None,
) -> tuple[str, ...]:
    """Ensure the identities read from an artifact belong to its declared split.

    This complements :func:`assert_protocol_access`: the latter validates the
    *name* of the stage/split, while this guard verifies that the actual input
    videos are members of that split.  Application data are intentionally
    outside the 20-video annotated protocol and therefore bypass membership
    validation.
    """

    normalized_split = _normalize(split)
    actual = tuple(
        sorted(
            {str(value).strip() for value in video_ids if str(value).strip()},
            key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value),
        )
    )
    if normalized_split in {"", "unspecified", "application"}:
        return actual
    if not actual:
        raise ProtocolViolation(
            f"Não foi possível determinar o video_id real do artefato para o split {split!r}."
        )

    config_path = (
        Path(splits_config)
        if splits_config is not None
        else REPOSITORY_ROOT / "configs" / "protocol" / "splits.yaml"
    )
    try:
        expected = set(load_split_spec(config_path).ids_for(normalized_split))
    except KeyError as exc:
        raise ProtocolViolation(str(exc)) from exc
    outside = set(actual) - expected
    if outside:
        allowed = sorted(
            expected,
            key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value),
        )
        raise ProtocolViolation(
            f"Vídeo(s) {sorted(outside)} não pertencem ao split/fold {split!r}; "
            f"IDs permitidos: {allowed}."
        )
    return actual
