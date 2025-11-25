# cdl_matching/data_generation/toy_dataset.py
from __future__ import annotations
from typing import List, Tuple

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


def make_toy_dataset(
    num_tables: int = NUM_TABLES_DEFAULT,
    num_startups: int = NUM_STARTUPS_DEFAULT,
    mentors_per_table: int = MENTORS_PER_TABLE_DEFAULT,
    seed: int = DEFAULT_SEED,
    num_mentors_pool: int | None = NUM_MENTORS_POOL_DEFAULT,
    min_per_table: int = MIN_MENTORS_PER_TABLE,
    max_per_table: int = MAX_MENTORS_PER_TABLE,
) -> Tuple[List[Mentor], List[Startup]]:
    """
    High-level helper to generate a complete toy dataset:
      - mentors (assigned to tables, fixed for all SGMs)
      - startups (each with OS and OC mentor IDs)
    """

    mentors: List[Mentor] = create_mentors_for_tables(
        num_tables=num_tables,
        seed=seed,
        mentors_per_table=mentors_per_table,
        num_mentors_pool=num_mentors_pool,
        min_per_table=min_per_table,
        max_per_table=max_per_table,
    )

    startups: List[Startup] = create_startups_with_os_oc(
        mentors=mentors,
        num_startups=num_startups,
        seed=seed,
    )

    return mentors, startups
