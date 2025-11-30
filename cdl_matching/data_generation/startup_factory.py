# cdl_matching/data_generation/startup_factory.py
from __future__ import annotations

import random
from typing import List, Dict, Optional, Tuple, Set

from ..models import Mentor, Startup
from ..config import (
    MAX_OS_PER_MENTOR,
    MAX_OC_PER_MENTOR,
    NUM_STARTUPS_DEFAULT,
)
from .domains import get_default_domains


def _get_fit(
    startup_id: str,
    mentor: Mentor,
    mentor_fit: Optional[Dict[Tuple[str, str], float]],
    rng: random.Random,
) -> float:
    """
    Return fit score for (startup, mentor).
    If mentor_fit is None, fall back to random so the function still works.
    """
    if mentor_fit is not None:
        return mentor_fit[(startup_id, mentor.id)]
    return rng.random()


def _candidate_mentors(
    mentors: List[Mentor],
    role: str,
    domain: str,
    load: Dict[str, int],
    max_load: int,
    forbid_ids: Set[str] | None = None,
    forbid_tables: Set[int] | None = None,
) -> List[Mentor]:
    """
    Filter mentors that are allowed for OS/OC, under capacity, and not in forbidden sets.
    Prefer domain-matching mentors if available.
    """
    forbid_ids = forbid_ids or set()
    forbid_tables = forbid_tables or set()

    base = [m for m in mentors if load[m.id] < max_load]

    if role == "os":
        base = [m for m in base if m.can_be_os]
    elif role == "oc":
        base = [m for m in base if m.can_be_oc]
    else:
        raise ValueError(f"Unknown role: {role}")

    if forbid_ids:
        base = [m for m in base if m.id not in forbid_ids]
    if forbid_tables:
        base = [m for m in base if m.table_id not in forbid_tables]

    # Prefer mentors whose domains contain the startup's domain
    domain_matches = [m for m in base if domain in m.domains]
    if domain_matches:
        return domain_matches

    return base


def _pick_best_mentor_for_role(
    startup_id: str,
    mentors: List[Mentor],
    role: str,
    domain: str,
    load: Dict[str, int],
    max_load: int,
    mentor_fit: Optional[Dict[Tuple[str, str], float]],
    rng: random.Random,
    forbid_ids: Set[str] | None = None,
    forbid_tables: Set[int] | None = None,
) -> Mentor:
    candidates = _candidate_mentors(
        mentors=mentors,
        role=role,
        domain=domain,
        load=load,
        max_load=max_load,
        forbid_ids=forbid_ids,
        forbid_tables=forbid_tables,
    )

    if not candidates:
        raise RuntimeError(
            f"No available {role.upper()} mentor for startup {startup_id} under cap {max_load}."
        )

    # Choose mentor with highest fit for this startup
    best = max(
        candidates,
        key=lambda m: _get_fit(startup_id, m, mentor_fit, rng),
    )
    return best


def create_startups_with_os_oc(
    mentors: List[Mentor],
    num_startups: int = NUM_STARTUPS_DEFAULT,
    seed: Optional[int] = None,
    mentor_fit: Optional[Dict[Tuple[str, str], float]] = None,
    max_os_per_mentor: int = MAX_OS_PER_MENTOR,
    max_oc_per_mentor: int = MAX_OC_PER_MENTOR,
) -> List[Startup]:
    """
    Create startups; assign:
      - a random domain
      - OS mentor = best-fit mentor under OS cap
      - OC mentor = best-fit mentor (≠ OS) under OC cap, on a different table
    """

    rng = random.Random(seed)
    all_domains = get_default_domains()

    # Track how many OS/OC each mentor already has
    os_load: Dict[str, int] = {m.id: 0 for m in mentors}
    oc_load: Dict[str, int] = {m.id: 0 for m in mentors}

    startups: List[Startup] = []

    for s_idx in range(1, num_startups + 1):
        sid = f"S{s_idx}"
        domain = rng.choice(all_domains)

        # ---- OS mentor ----
        os_mentor = _pick_best_mentor_for_role(
            startup_id=sid,
            mentors=mentors,
            role="os",
            domain=domain,
            load=os_load,
            max_load=max_os_per_mentor,
            mentor_fit=mentor_fit,
            rng=rng,
        )
        os_load[os_mentor.id] += 1

        # ---- OC mentor ----
        oc_mentor = _pick_best_mentor_for_role(
            startup_id=sid,
            mentors=mentors,
            role="oc",
            domain=domain,
            load=oc_load,
            max_load=max_oc_per_mentor,
            mentor_fit=mentor_fit,
            rng=rng,
            forbid_ids={os_mentor.id},
            forbid_tables={os_mentor.table_id},  # OC must be on a different table
        )
        oc_load[oc_mentor.id] += 1

        startup = Startup(
            id=sid,
            name=f"Startup {s_idx}",
            domain=domain,
            os_id=os_mentor.id,
            oc_id=oc_mentor.id,
        )
        startups.append(startup)

    return startups
