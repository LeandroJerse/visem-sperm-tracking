"""Load, override and fingerprint versioned experiment configurations."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


class ConfigError(ValueError):
    """Raised when an experiment configuration cannot be resolved safely."""


def _yaml_module():
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise ConfigError(
            "Configurações YAML requerem PyYAML. Instale requirements.txt no ambiente do projeto."
        ) from exc
    return yaml


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping without mutating the source object."""
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(f"Configuração não encontrada: {config_path}")
    yaml = _yaml_module()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"A raiz de {config_path} deve ser um mapping YAML.")
    return data


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge mappings; lists and scalar values are replaced."""
    merged: dict[str, Any] = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _parse_value(raw: str) -> Any:
    # YAML parsing gives useful CLI values (null, booleans, numbers, lists)
    # while preserving ordinary strings.
    return _yaml_module().safe_load(raw)


def apply_dotted_override(config: dict[str, Any], expression: str) -> None:
    """Apply ``a.b=value`` to ``config`` in place."""
    if "=" not in expression:
        raise ConfigError(f"Override deve usar chave=valor: {expression!r}")
    raw_key, raw_value = expression.split("=", 1)
    keys = [part.strip() for part in raw_key.split(".") if part.strip()]
    if not keys:
        raise ConfigError(f"Chave vazia no override: {expression!r}")
    node: dict[str, Any] = config
    for key in keys[:-1]:
        existing = node.get(key)
        if existing is None:
            existing = {}
            node[key] = existing
        if not isinstance(existing, dict):
            raise ConfigError(f"Não é possível entrar em {key!r}: valor não é mapping.")
        node = existing
    node[keys[-1]] = _parse_value(raw_value.strip())


def resolve_config(
    path: str | Path | None = None,
    *,
    defaults: Mapping[str, Any] | None = None,
    overrides: Iterable[str] = (),
) -> dict[str, Any]:
    """Resolve defaults, an optional YAML file and dotted CLI overrides."""
    result = copy.deepcopy(dict(defaults or {}))
    if path is not None:
        result = deep_merge(result, load_config(path))
    for expression in overrides:
        apply_dotted_override(result, expression)
    return result


def canonical_json(config: Mapping[str, Any]) -> str:
    return json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def config_hash(config: Mapping[str, Any], length: int = 12) -> str:
    """Stable short SHA-256 for resolved configuration identity."""
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()[:length]
