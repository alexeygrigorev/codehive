"""Codebase analyzer: auto-detect tech stack, frameworks, architecture, conventions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.knowledge import update_knowledge
from codehive.core.project import ProjectNotFoundError, get_project

# ---------------------------------------------------------------------------
# File-content parsers (lightweight, no external deps)
# ---------------------------------------------------------------------------

# Mapping of dependency names to framework identifiers
_PYTHON_FRAMEWORKS: dict[str, str] = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "starlette": "Starlette",
    "tornado": "Tornado",
    "sanic": "Sanic",
}

_JS_FRAMEWORKS: dict[str, str] = {
    "react": "React",
    "vue": "Vue",
    "angular": "Angular",
    "next": "Next.js",
    "nuxt": "Nuxt",
    "svelte": "Svelte",
    "@angular/core": "Angular",
}

# Linter / formatter config files
_LINTER_FILES: dict[str, str] = {
    ".eslintrc": "ESLint",
    ".eslintrc.js": "ESLint",
    ".eslintrc.json": "ESLint",
    ".eslintrc.yml": "ESLint",
    "eslint.config.js": "ESLint",
    "eslint.config.mjs": "ESLint",
    ".flake8": "flake8",
    "ruff.toml": "Ruff",
    ".pylintrc": "Pylint",
    "rustfmt.toml": "rustfmt",
}

_FORMATTER_FILES: dict[str, str] = {
    ".prettierrc": "Prettier",
    ".prettierrc.js": "Prettier",
    ".prettierrc.json": "Prettier",
    "prettier.config.js": "Prettier",
}

# Framework-specific config files
_FRAMEWORK_CONFIG_FILES: dict[str, str] = {
    "next.config.js": "Next.js",
    "next.config.mjs": "Next.js",
    "next.config.ts": "Next.js",
    "nuxt.config.ts": "Nuxt",
    "nuxt.config.js": "Nuxt",
    "vite.config.ts": "Vite",
    "vite.config.js": "Vite",
    "angular.json": "Angular",
    "svelte.config.js": "Svelte",
}

# AI-assistant instruction files
_AI_INSTRUCTION_FILES = {"CLAUDE.md", "AGENTS.md", ".cursorrules"}


def _parse_pyproject_toml(content: str) -> dict[str, Any]:
    """Extract dependencies from pyproject.toml content (basic parsing, no toml lib)."""
    deps: list[str] = []
    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        # Detect [project.dependencies] or [tool.poetry.dependencies]
        if stripped.startswith("["):
            in_deps = stripped in (
                "[project.dependencies]",
                "[tool.poetry.dependencies]",
                "[project]",
            )
            continue
        if in_deps:
            if stripped.startswith("["):
                in_deps = False
                continue
            if stripped.startswith("dependencies") and "=" in stripped:
                # inline: dependencies = ["fastapi>=0.100", ...]
                bracket_content = stripped.split("=", 1)[1].strip()
                deps.extend(_extract_bracket_list(bracket_content))
                continue
            # Array continuation lines like "  fastapi>=0.100",
            if stripped.startswith('"') or stripped.startswith("'"):
                name = stripped.strip("\"', ")
                pkg = name.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip()
                if pkg:
                    deps.append(pkg)
    return (
        {"language": "Python", "dependencies": sorted(set(deps))}
        if deps
        else {"language": "Python"}
    )


def _extract_bracket_list(text: str) -> list[str]:
    """Extract package names from a bracketed list like '["fastapi>=0.1", "uvicorn"]'."""
    results: list[str] = []
    # Remove brackets
    inner = text.strip("[] \n")
    for part in inner.split(","):
        part = part.strip().strip("\"'")
        pkg = part.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip()
        if pkg:
            results.append(pkg)
    return results


def _parse_requirements_txt(content: str) -> dict[str, Any]:
    """Extract dependencies from requirements.txt."""
    deps: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        pkg = stripped.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip()
        if pkg:
            deps.append(pkg)
    return {"language": "Python", "dependencies": sorted(set(deps))}


def _parse_package_json(content: str) -> dict[str, Any]:
    """Extract dependencies from package.json (basic JSON-like parsing)."""
    import json

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return {"language": "JavaScript"}

    deps: list[str] = []
    for key in ("dependencies", "devDependencies"):
        if key in data:
            deps.extend(data[key].keys())
    return {"language": "JavaScript/TypeScript", "dependencies": sorted(set(deps))}


def _parse_cargo_toml(content: str) -> dict[str, Any]:
    """Detect Rust from Cargo.toml."""
    deps: list[str] = []
    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "[dependencies]" or stripped == "[dev-dependencies]":
            in_deps = True
            continue
        if stripped.startswith("["):
            in_deps = False
            continue
        if in_deps and "=" in stripped:
            pkg = stripped.split("=")[0].strip()
            if pkg:
                deps.append(pkg)
    result: dict[str, Any] = {"language": "Rust"}
    if deps:
        result["dependencies"] = sorted(set(deps))
    return result


def _parse_go_mod(content: str) -> dict[str, Any]:
    """Detect Go from go.mod."""
    deps: list[str] = []
    in_require = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_require = True
            continue
        if in_require:
            if stripped == ")":
                in_require = False
                continue
            parts = stripped.split()
            if parts:
                deps.append(parts[0])
        elif stripped.startswith("require "):
            parts = stripped.split()
            if len(parts) >= 2:
                deps.append(parts[1])
    result: dict[str, Any] = {"language": "Go"}
    if deps:
        result["dependencies"] = sorted(set(deps))
    return result


def _parse_gemfile(content: str) -> dict[str, Any]:
    """Detect Ruby from Gemfile."""
    deps: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("gem "):
            parts = stripped.split(",")
            gem_name = parts[0].replace("gem ", "").strip().strip("\"'")
            if gem_name:
                deps.append(gem_name)
    result: dict[str, Any] = {"language": "Ruby"}
    if deps:
        result["dependencies"] = sorted(set(deps))
    return result


# ---------------------------------------------------------------------------
# Detection strategies
# ---------------------------------------------------------------------------


def _detect_tech_stack(project_path: Path) -> dict[str, Any]:
    """Detect languages and dependencies from manifest files."""
    tech: dict[str, Any] = {}
    languages: list[str] = []
    all_deps: list[str] = []

    manifest_parsers: list[tuple[str, Any]] = [
        ("pyproject.toml", _parse_pyproject_toml),
        ("requirements.txt", _parse_requirements_txt),
        ("package.json", _parse_package_json),
        ("Cargo.toml", _parse_cargo_toml),
        ("go.mod", _parse_go_mod),
        ("Gemfile", _parse_gemfile),
    ]

    for filename, parser in manifest_parsers:
        filepath = project_path / filename
        if filepath.is_file():
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                result = parser(content)
                lang = result.get("language", "")
                if lang and lang not in languages:
                    languages.append(lang)
                deps = result.get("dependencies", [])
                all_deps.extend(deps)
            except OSError:
                continue

    # Also check for pom.xml / build.gradle (just language detection)
    if (project_path / "pom.xml").is_file():
        if "Java" not in languages:
            languages.append("Java")
    if (project_path / "build.gradle").is_file() or (project_path / "build.gradle.kts").is_file():
        if "Java/Kotlin" not in languages:
            languages.append("Java/Kotlin")

    if languages:
        tech["languages"] = languages
    if all_deps:
        tech["dependencies"] = sorted(set(all_deps))

    return tech


def _detect_frameworks(project_path: Path, tech_stack: dict[str, Any]) -> list[str]:
    """Detect frameworks from dependencies and config files."""
    frameworks: list[str] = []
    deps = set(tech_stack.get("dependencies", []))

    # Check Python frameworks
    for dep, framework in _PYTHON_FRAMEWORKS.items():
        if dep in deps:
            frameworks.append(framework)

    # Check JS frameworks
    for dep, framework in _JS_FRAMEWORKS.items():
        if dep in deps:
            frameworks.append(framework)

    # Check framework-specific config files
    for filename, framework in _FRAMEWORK_CONFIG_FILES.items():
        if (project_path / filename).is_file() and framework not in frameworks:
            frameworks.append(framework)

    return sorted(set(frameworks))


def _detect_architecture(project_path: Path) -> dict[str, Any]:
    """Detect architectural patterns from directory structure."""
    arch: dict[str, Any] = {}

    # Standard directory layout
    known_dirs = ["src", "tests", "test", "docs", "api", "core", "models", "lib"]
    found_dirs = [d for d in known_dirs if (project_path / d).is_dir()]
    if found_dirs:
        arch["directory_layout"] = found_dirs

    # Monorepo detection: multiple manifest files in subdirectories
    pyproject_count = len(list(project_path.glob("*/pyproject.toml")))
    pkg_json_count = len(list(project_path.glob("*/package.json")))
    if pyproject_count > 1 or pkg_json_count > 1 or (pyproject_count >= 1 and pkg_json_count >= 1):
        arch["monorepo"] = True

    # Docker
    has_dockerfile = (project_path / "Dockerfile").is_file()
    has_compose = (project_path / "docker-compose.yml").is_file() or (
        project_path / "docker-compose.yaml"
    ).is_file()
    if has_dockerfile or has_compose:
        docker_info: dict[str, bool] = {}
        if has_dockerfile:
            docker_info["dockerfile"] = True
        if has_compose:
            docker_info["compose"] = True
        arch["docker"] = docker_info

    # CI/CD
    ci_systems: list[str] = []
    if (project_path / ".github" / "workflows").is_dir():
        ci_systems.append("GitHub Actions")
    if (project_path / ".gitlab-ci.yml").is_file():
        ci_systems.append("GitLab CI")
    if (project_path / "Jenkinsfile").is_file():
        ci_systems.append("Jenkins")
    if (project_path / ".circleci").is_dir():
        ci_systems.append("CircleCI")
    if ci_systems:
        arch["ci_cd"] = ci_systems

    return arch


def _detect_conventions(project_path: Path) -> dict[str, Any]:
    """Detect linter/formatter configs and AI instruction files."""
    conventions: dict[str, Any] = {}

    # Linters
    linters: list[str] = []
    for filename, linter in _LINTER_FILES.items():
        if (project_path / filename).is_file() and linter not in linters:
            linters.append(linter)
    # Also check pyproject.toml for [tool.ruff] or [tool.black]
    pyproject = project_path / "pyproject.toml"
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            if "[tool.ruff" in content and "Ruff" not in linters:
                linters.append("Ruff")
            if "[tool.pylint" in content and "Pylint" not in linters:
                linters.append("Pylint")
        except OSError:
            pass
    if linters:
        conventions["linters"] = sorted(linters)

    # Formatters
    formatters: list[str] = []
    for filename, formatter in _FORMATTER_FILES.items():
        if (project_path / filename).is_file() and formatter not in formatters:
            formatters.append(formatter)
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            if "[tool.black" in content and "Black" not in formatters:
                formatters.append("Black")
        except OSError:
            pass
    if formatters:
        conventions["formatters"] = sorted(formatters)

    # AI instruction files
    ai_files: list[str] = []
    for filename in _AI_INSTRUCTION_FILES:
        if (project_path / filename).is_file():
            ai_files.append(filename)
    # Also check .claude/CLAUDE.md
    if (project_path / ".claude" / "CLAUDE.md").is_file():
        ai_files.append(".claude/CLAUDE.md")
    if ai_files:
        conventions["ai_instructions"] = sorted(ai_files)

    # README
    for readme_name in ("README.md", "README.rst", "README.txt", "README"):
        readme = project_path / readme_name
        if readme.is_file():
            conventions["has_readme"] = True
            break

    return conventions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def analyze_codebase(project_path: str) -> dict[str, Any]:
    """Scan a project directory and return structured knowledge.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Dict with keys: tech_stack, frameworks, architecture, conventions, detected_at.
    """
    path = Path(project_path)
    if not path.is_dir():
        return {}

    result: dict[str, Any] = {}

    tech_stack = _detect_tech_stack(path)
    if tech_stack:
        result["tech_stack"] = tech_stack

    frameworks = _detect_frameworks(path, tech_stack)
    if frameworks:
        result["frameworks"] = frameworks

    architecture = _detect_architecture(path)
    if architecture:
        result["architecture"] = architecture

    conventions = _detect_conventions(path)
    if conventions:
        result["conventions"] = conventions

    result["detected_at"] = datetime.now(timezone.utc).isoformat()

    return result


async def populate_knowledge(
    db: AsyncSession,
    project_id: uuid.UUID,
    analysis_result: dict[str, Any],
) -> dict[str, Any]:
    """Write analysis results into a project's knowledge, preserving existing entries.

    Uses merge semantics: auto-detected keys are updated, but manually-set
    knowledge entries that are not part of the analysis are preserved.

    Args:
        db: Async database session.
        project_id: UUID of the project.
        analysis_result: Output from ``analyze_codebase()``.

    Returns:
        The full updated knowledge dict.

    Raises:
        ProjectNotFoundError: If the project does not exist.
    """
    if not analysis_result:
        # Nothing to merge -- just return current knowledge
        project = await get_project(db, project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project {project_id} not found")
        return dict(project.knowledge) if project.knowledge else {}

    return await update_knowledge(db, project_id, analysis_result)
