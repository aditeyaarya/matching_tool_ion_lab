# cdl_matching/data_generation/toy_dataset.py
from __future__ import annotations
from typing import List, Tuple, Dict
import random

from ..models import Mentor, Startup
from ..config import (
    NUM_TABLES_DEFAULT,
    NUM_STARTUPS_DEFAULT,
    MENTORS_PER_TABLE_DEFAULT,
    DEFAULT_SEED,
    MIN_MENTORS_PER_TABLE,
    MAX_MENTORS_PER_TABLE,
    NUM_MENTORS_POOL_DEFAULT,
)
from .mentor_factory import create_mentors_for_tables
from .startup_factory import create_startups_with_os_oc


def build_random_mentor_fit(
    mentors: List[Mentor],
    num_startups: int,
    seed: int | None = None,
) -> Dict[tuple[str, str], float]:
    """
    Random fit in [0,1] between each startup and each mentor.

    Key: (startup_id, mentor_id)
    """
    rng = random.Random(seed)
    fit: Dict[tuple[str, str], float] = {}

    for s_idx in range(1, num_startups + 1):
        sid = f"S{s_idx}"
        for m in mentors:
            fit[(sid, m.id)] = rng.random()

    return fit


def make_toy_dataset(
    num_tables: int = NUM_TABLES_DEFAULT,
    num_startups: int = NUM_STARTUPS_DEFAULT,
    mentors_per_table: int = MENTORS_PER_TABLE_DEFAULT,
    seed: int = DEFAULT_SEED,
    min_per_table: int = MIN_MENTORS_PER_TABLE,
    max_per_table: int = MAX_MENTORS_PER_TABLE,
    num_mentors_pool: int = NUM_MENTORS_POOL_DEFAULT,
) -> Tuple[List[Mentor], List[Startup], Dict[tuple[str, str], float]]:
    """
    Return mentors, startups, and a random mentor_fit matrix.
    """

    mentors: List[Mentor] = create_mentors_for_tables(
        num_tables=num_tables,
        seed=seed,
        mentors_per_table=mentors_per_table,
        num_mentors_pool=num_mentors_pool,
        min_per_table=min_per_table,
        max_per_table=max_per_table,
    )

    # 1) random fit scores
    mentor_fit = build_random_mentor_fit(
        mentors=mentors,
        num_startups=num_startups,
        seed=seed,
    )

    # 2) startups with OS/OC chosen using those fit scores
    startups: List[Startup] = create_startups_with_os_oc(
        mentors=mentors,
        num_startups=num_startups,
        seed=seed,
        mentor_fit=mentor_fit,
    )

    return mentors, startups, mentor_fit
