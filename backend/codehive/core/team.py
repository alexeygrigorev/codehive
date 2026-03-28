"""Team generation: create default agent profiles for a project."""

from __future__ import annotations

import hashlib
import random
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.models import AgentProfile

# Pool of names -- diverse, short, easy to read
NAME_POOL: list[str] = [
    "Alice",
    "Marcus",
    "Priya",
    "Kenji",
    "Sofia",
    "Omar",
    "Lena",
    "Diego",
    "Nia",
    "Ravi",
    "Yuki",
    "Amara",
    "Felix",
    "Zara",
    "Leon",
    "Mila",
    "Kai",
    "Isla",
    "Theo",
    "Luna",
    "Amir",
    "Elena",
    "Soren",
    "Ava",
]

# Default team composition: (role, count)
DEFAULT_TEAM: list[tuple[str, int]] = [
    ("pm", 1),
    ("swe", 2),
    ("qa", 2),
    ("oncall", 1),
]

DICEBEAR_BASE_URL = "https://api.dicebear.com/9.x/bottts-neutral/svg"


def avatar_url_for_seed(seed: str) -> str:
    """Construct a DiceBear avatar URL from a seed string."""
    return f"{DICEBEAR_BASE_URL}?seed={seed}"


def _pick_names(count: int, project_id: uuid.UUID) -> list[str]:
    """Pick `count` unique names deterministically based on project_id."""
    # Use project_id as seed for deterministic but varied selection
    seed = int(hashlib.md5(str(project_id).encode()).hexdigest(), 16)
    rng = random.Random(seed)
    pool = list(NAME_POOL)
    rng.shuffle(pool)
    return pool[:count]


async def generate_default_team(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> list[AgentProfile]:
    """Generate the default team of 6 agent profiles for a project.

    Creates: 1 PM, 2 SWEs, 2 QAs, 1 OnCall.
    Names are drawn from NAME_POOL deterministically based on project_id.
    """
    total_needed = sum(count for _, count in DEFAULT_TEAM)
    names = _pick_names(total_needed, project_id)

    profiles: list[AgentProfile] = []
    name_idx = 0

    for role, count in DEFAULT_TEAM:
        for _ in range(count):
            name = names[name_idx]
            avatar_seed = f"{name}-{project_id}"
            profile = AgentProfile(
                project_id=project_id,
                name=name,
                role=role,
                avatar_seed=avatar_seed,
            )
            db.add(profile)
            profiles.append(profile)
            name_idx += 1

    await db.flush()
    for p in profiles:
        await db.refresh(p)
    return profiles
