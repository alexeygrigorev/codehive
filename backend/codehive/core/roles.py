"""Role system: load, validate, merge role definitions for agent behavior."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class RoleNotFoundError(Exception):
    """Raised when a role name cannot be resolved."""


class RoleNotAllowedError(Exception):
    """Raised when a session's role is not allowed to perform a pipeline transition."""


# ---------------------------------------------------------------------------
# Built-in pipeline roles (PM, SWE, QA, OnCall)
# ---------------------------------------------------------------------------

BUILTIN_ROLES: dict[str, dict[str, Any]] = {
    "pm": {
        "display_name": "Product Manager",
        "system_prompt": "You are a Product Manager agent. You groom tasks, write acceptance criteria, and accept or reject deliverables.",
        "allowed_transitions": {
            "backlog": {"grooming"},
            "grooming": {"groomed"},
            "accepting": {"done", "implementing"},
        },
        "color": "blue",
    },
    "swe": {
        "display_name": "Software Engineer",
        "system_prompt": "You are a Software Engineer agent. You implement features, write code, and create tests.",
        "allowed_transitions": {
            "groomed": {"implementing"},
            "implementing": {"testing"},
        },
        "color": "green",
    },
    "qa": {
        "display_name": "QA Tester",
        "system_prompt": "You are a QA Tester agent. You verify implementations, run tests, and report results.",
        "allowed_transitions": {
            "testing": {"accepting", "implementing"},
        },
        "color": "orange",
    },
    "oncall": {
        "display_name": "On-Call Engineer",
        "system_prompt": "You are an On-Call Engineer agent. You can perform SWE and QA tasks as an emergency responder.",
        "allowed_transitions": {
            "groomed": {"implementing"},
            "implementing": {"testing"},
            "testing": {"accepting", "implementing"},
        },
        "color": "red",
    },
}


def is_valid_role(role_name: str) -> bool:
    """Check if a role name is a known built-in pipeline role."""
    return role_name in BUILTIN_ROLES


def check_role_transition(
    role_name: str,
    from_status: str,
    to_status: str,
) -> None:
    """Validate that a role is allowed to perform a pipeline transition.

    Raises RoleNotAllowedError if the transition is not in the role's allowed_transitions.
    Does nothing if role_name is not a known built-in role (custom roles are not enforced).
    """
    if role_name not in BUILTIN_ROLES:
        return
    role_def = BUILTIN_ROLES[role_name]
    allowed = role_def["allowed_transitions"]
    targets = allowed.get(from_status, set())
    if to_status not in targets:
        raise RoleNotAllowedError(
            f"Role '{role_name}' is not allowed to perform transition "
            f"'{from_status}' -> '{to_status}'"
        )


async def seed_builtin_roles(db: Any) -> int:
    """Seed built-in pipeline roles into the custom_roles table (idempotent).

    Only inserts roles that do not already exist -- never overwrites user edits.
    Returns the number of roles inserted.
    """
    from codehive.db.models import CustomRole

    count = 0
    for name, definition in BUILTIN_ROLES.items():
        existing = await db.get(CustomRole, name)
        if existing is None:
            # Convert sets to sorted lists for JSON serialization
            serializable_def = {**definition, "is_builtin": True}
            if "allowed_transitions" in serializable_def:
                serializable_def["allowed_transitions"] = {
                    k: sorted(v) for k, v in serializable_def["allowed_transitions"].items()
                }
            row = CustomRole(name=name, definition=serializable_def)
            db.add(row)
            count += 1
            logger.info("Seeded built-in role: %s", name)

    if count:
        await db.commit()
    return count


class RoleDefinition(BaseModel):
    """Pydantic model for an agent role definition."""

    name: str
    display_name: str = ""
    description: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    coding_rules: list[str] = Field(default_factory=list)
    system_prompt_extra: str = ""

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name must not be empty")
        return v


# ---------------------------------------------------------------------------
# Built-in roles directory
# ---------------------------------------------------------------------------

_BUILTIN_ROLES_DIR: Path | None = None


def _get_builtin_dir() -> Path:
    """Return the path to the built-in roles YAML directory."""
    global _BUILTIN_ROLES_DIR
    if _BUILTIN_ROLES_DIR is not None:
        return _BUILTIN_ROLES_DIR
    # roles/ is a sibling package of core/
    pkg_root = Path(__file__).resolve().parent.parent / "roles"
    _BUILTIN_ROLES_DIR = pkg_root
    return _BUILTIN_ROLES_DIR


def set_builtin_dir(path: Path) -> None:
    """Override the built-in roles directory (useful for testing)."""
    global _BUILTIN_ROLES_DIR
    _BUILTIN_ROLES_DIR = path


def reset_builtin_dir() -> None:
    """Reset the built-in roles directory to the default."""
    global _BUILTIN_ROLES_DIR
    _BUILTIN_ROLES_DIR = None


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def list_builtin_roles() -> list[str]:
    """Return the names of all built-in YAML role files (without extension)."""
    d = _get_builtin_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def _load_yaml_role(role_name: str) -> RoleDefinition:
    """Load and validate a role from the built-in YAML directory.

    Raises RoleNotFoundError if the file does not exist.
    Raises pydantic.ValidationError if the YAML is malformed.
    """
    path = _get_builtin_dir() / f"{role_name}.yaml"
    if not path.is_file():
        raise RoleNotFoundError(f"Built-in role '{role_name}' not found")
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid role YAML: expected a mapping, got {type(data).__name__}")
    return RoleDefinition(**data)


def load_role(
    role_name: str,
    *,
    custom_roles: dict[str, dict[str, Any]] | None = None,
) -> RoleDefinition:
    """Load a role by name.

    Resolution order:
    1. Built-in YAML file
    2. Custom roles dict (e.g. from DB)

    Raises RoleNotFoundError if not found in either source.
    """
    # Try built-in first
    builtin_dir = _get_builtin_dir()
    path = builtin_dir / f"{role_name}.yaml"
    if path.is_file():
        return _load_yaml_role(role_name)

    # Try custom roles
    if custom_roles and role_name in custom_roles:
        return RoleDefinition(**custom_roles[role_name])

    raise RoleNotFoundError(f"Role '{role_name}' not found")


# ---------------------------------------------------------------------------
# Merging (global + project overrides)
# ---------------------------------------------------------------------------


def merge_role(
    global_role: RoleDefinition,
    project_overrides: dict[str, Any],
) -> RoleDefinition:
    """Merge project-level overrides onto a global role definition.

    List fields (allowed_tools, denied_tools, coding_rules, responsibilities)
    are *replaced*, not appended. Scalar fields are overridden if present.
    Returns a new RoleDefinition instance.
    """
    if not project_overrides:
        return global_role.model_copy()

    base = global_role.model_dump()
    for key, value in project_overrides.items():
        if key in base:
            base[key] = value
    return RoleDefinition(**base)


# ---------------------------------------------------------------------------
# Tool filtering helpers
# ---------------------------------------------------------------------------


def filter_tools_for_role(
    tool_definitions: list[dict[str, Any]],
    role: RoleDefinition,
) -> list[dict[str, Any]]:
    """Filter tool definitions based on a role's allowed_tools and denied_tools.

    - If allowed_tools is non-empty, only those tools are kept.
    - denied_tools are always removed (takes priority over allowed_tools).
    - If both are empty/unset, all tools are returned.
    """
    tools = tool_definitions

    if role.allowed_tools:
        allowed = set(role.allowed_tools)
        tools = [t for t in tools if t.get("name") in allowed]

    if role.denied_tools:
        denied = set(role.denied_tools)
        tools = [t for t in tools if t.get("name") not in denied]

    return tools


def build_role_system_prompt(role: RoleDefinition) -> str:
    """Build a system prompt fragment from a role's system_prompt_extra and coding_rules.

    Returns an empty string if neither is set.
    """
    parts: list[str] = []

    if role.system_prompt_extra:
        parts.append(role.system_prompt_extra.strip())

    if role.coding_rules:
        rules_text = "Coding rules:\n"
        for i, rule in enumerate(role.coding_rules, 1):
            rules_text += f"  {i}. {rule}\n"
        parts.append(rules_text.strip())

    return "\n\n".join(parts)
