# cdl_matching/data_generation/startup_factory.py
from __future__ import annotations

import random
from typing import List, Dict, Optional

from ..models import Mentor, Startup
from ..config import (
    MAX_OS_PER_MENTOR,
    MAX_OC_PER_MENTOR,
    NUM_STARTUPS_DEFAULT,
)
from .domains import get_default_domains


def _pick_os_by_fit(startup_id, mentors, fit_scores, os_load, max_os):
    candidates = [
        m for m in mentors if m.can_be_os and os_load[m.id] < max_os
    ]
    return max(candidates, key=lambda m: fit_scores[m.id][startup_id])


def _pick_oc_by_fit(startup_id, mentors, fit_scores, os_mentor, oc_load, max_oc):
    candidates = [
        m for m in mentors
        if m.can_be_oc
        and m.id != os_mentor.id
        and m.table_id != os_mentor.table_id
        and oc_load[m.id] < max_oc
    ]
    return max(candidates, key=lambda m: fit_scores[m.id][startup_id])


def _pick_os_mentor(
    mentors: List[Mentor],
    domain: str,
    os_load: Dict[str, int],
    max_os_per_mentor: int,
) -> Mentor:
    """
    Choose an OS mentor for a startup with the given domain,
    respecting the per-mentor OS load cap.
    """
    # Prefer domain-matching first
    candidates = [
        m
        for m in mentors
        if m.can_be_os
        and domain in m.domains
        and os_load[m.id] < max_os_per_mentor
    ]

    # Relax domain constraint if needed (still respect load)
    if not candidates:
        candidates = [
            m
            for m in mentors
            if m.can_be_os and os_load[m.id] < max_os_per_mentor
        ]

    if not candidates:
        raise RuntimeError(
            f"No available OS mentor left under cap {max_os_per_mentor}. "
            "Decrease num_startups or increase MAX_OS_PER_MENTOR."
        )

    return random.choice(candidates)

def _pick_oc_mentor(
    mentors: List[Mentor],
    domain: str,
    os_mentor: Mentor,
    oc_load: Dict[str, int],
    max_oc_per_mentor: int,
    fit_scores: Optional[Dict[str, Dict[str, float]]] = None,
    startup_id: Optional[str] = None,
) -> Mentor:
    """
    Choose an OC mentor for a startup with the given domain,
    distinct from the OS mentor AND on a different table,
    respecting the OC load cap.
    """
    # Prefer: same domain, different mentor, different table
    candidates = [
        m
        for m in mentors
        if m.can_be_oc
        and m.id != os_mentor.id
        and m.table_id != os_mentor.table_id      # 🔒 must be a different table
        and domain in m.domains
        and oc_load[m.id] < max_oc_per_mentor
    ]

    # Relax domain constraint if needed, but still:
    # - not the OS mentor
    # - not on the same table as OS
    # - respect load cap
    if not candidates:
        candidates = [
            m
            for m in mentors
            if m.can_be_oc
            and m.id != os_mentor.id
            and m.table_id != os_mentor.table_id  # 🔒 keep different table
            and oc_load[m.id] < max_oc_per_mentor
        ]

    if not candidates:
        raise RuntimeError(
            f"No available OC mentor left under cap {max_oc_per_mentor} "
            "on a different table than the OS mentor. "
            "Try reducing num_startups or relaxing caps."
        )

    return random.choice(candidates)

def create_startups_with_os_oc(
    mentors: List[Mentor],
    num_startups: int = NUM_STARTUPS_DEFAULT,
    max_os_per_mentor: int = MAX_OS_PER_MENTOR,
    max_oc_per_mentor: int = MAX_OC_PER_MENTOR,
    seed: Optional[int] = None,
    fit_scores: Optional[Dict] = None,
) -> List[Startup]:
    """
    Create `num_startups` startups with OS and OC mentors assigned such that:
      - no mentor is OS for more than `max_os_per_mentor` startups
      - no mentor is OC for more than `max_oc_per_mentor` startups
    """
    if seed is not None:
        random.seed(seed)

    if fit_scores:
        csv_startup_ids = list(next(iter(fit_scores.values())).keys())
        startup_ids = csv_startup_ids  # use EXACT CSV columns
    else:
        startup_ids = [f"S{i}" for i in range(1, num_startups + 1)]
        
    domains = get_default_domains()

    # Track per-mentor OS / OC loads
    os_load: Dict[str, int] = {m.id: 0 for m in mentors}
    oc_load: Dict[str, int] = {m.id: 0 for m in mentors}

    startups: List[Startup] = []

    for sid in startup_ids:
        domain = random.choice(domains)

        if fit_scores:
            os_mentor = _pick_os_by_fit(sid, mentors, fit_scores, os_load, max_os_per_mentor)
            oc_mentor = _pick_oc_by_fit(sid, mentors, fit_scores, os_mentor, oc_load, max_oc_per_mentor)
        else:
            os_mentor = _pick_os_mentor(mentors, domain, os_load, max_os_per_mentor)
            oc_mentor = _pick_oc_mentor(mentors, domain, os_mentor, oc_load, max_oc_per_mentor)

        os_load[os_mentor.id] += 1
        oc_load[oc_mentor.id] += 1

        startup = Startup(
            id=sid,
            name=f"Startup {sid}",
            domain=domain,
            os_id=os_mentor.id,
            oc_id=oc_mentor.id,
        )
        startups.append(startup)

    return startups
