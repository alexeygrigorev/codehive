"""Archetype system: load, validate, and apply project archetypes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class ArchetypeNotFoundError(Exception):
    """Raised when an archetype name cannot be resolved."""


class ArchetypeDefinition(BaseModel):
    """Pydantic model for a project archetype definition."""

    name: str
    display_name: str = ""
    description: str = ""
    roles: list[str] = Field(default_factory=list)
    workflow: list[str] = Field(default_factory=list)
    default_settings: dict[str, Any] = Field(default_factory=dict)
    tech_stack: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name must not be empty")
        return v


# ---------------------------------------------------------------------------
# Built-in archetypes directory
# ---------------------------------------------------------------------------

_BUILTIN_ARCHETYPES_DIR: Path | None = None


def _get_builtin_dir() -> Path:
    """Return the path to the built-in archetypes YAML directory."""
    global _BUILTIN_ARCHETYPES_DIR
    if _BUILTIN_ARCHETYPES_DIR is not None:
        return _BUILTIN_ARCHETYPES_DIR
    # archetypes/ is a sibling package of core/
    pkg_root = Path(__file__).resolve().parent.parent / "archetypes"
    _BUILTIN_ARCHETYPES_DIR = pkg_root
    return _BUILTIN_ARCHETYPES_DIR


def set_builtin_dir(path: Path) -> None:
    """Override the built-in archetypes directory (useful for testing)."""
    global _BUILTIN_ARCHETYPES_DIR
    _BUILTIN_ARCHETYPES_DIR = path


def reset_builtin_dir() -> None:
    """Reset the built-in archetypes directory to the default."""
    global _BUILTIN_ARCHETYPES_DIR
    _BUILTIN_ARCHETYPES_DIR = None


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def list_builtin_archetypes() -> list[str]:
    """Return the names of all built-in YAML archetype files (without extension)."""
    d = _get_builtin_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def load_archetype(archetype_name: str) -> ArchetypeDefinition:
    """Load and validate an archetype from the built-in YAML directory.

    Raises ArchetypeNotFoundError if the file does not exist.
    Raises pydantic.ValidationError if the YAML is malformed.
    """
    path = _get_builtin_dir() / f"{archetype_name}.yaml"
    if not path.is_file():
        raise ArchetypeNotFoundError(f"Built-in archetype '{archetype_name}' not found")
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid archetype YAML: expected a mapping, got {type(data).__name__}")
    return ArchetypeDefinition(**data)


# ---------------------------------------------------------------------------
# Application to project knowledge
# ---------------------------------------------------------------------------


def apply_archetype_to_knowledge(
    knowledge: dict[str, Any],
    archetype_name: str | None,
) -> dict[str, Any]:
    """Apply an archetype's roles and settings to a project knowledge dict.

    If archetype_name is None, returns knowledge unchanged.
    Raises ArchetypeNotFoundError if the archetype does not exist.
    """
    if archetype_name is None:
        return knowledge

    archetype = load_archetype(archetype_name)
    result = dict(knowledge)
    result["archetype_roles"] = archetype.roles
    result["archetype_settings"] = archetype.default_settings
    return result
