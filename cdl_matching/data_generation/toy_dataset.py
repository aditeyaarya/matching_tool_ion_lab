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
    FIT_SCORES_CSV_PATH,
)
from .mentor_factory import create_mentors_for_tables
from .startup_factory import create_startups_with_os_oc
from .fit_loader import load_fit_scores
import os


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

    # If CSV exists -> use it to define mentors + startups
    if FIT_SCORES_CSV_PATH and os.path.exists(FIT_SCORES_CSV_PATH):
        csv_mentor_ids, fit_scores = load_fit_scores(FIT_SCORES_CSV_PATH)
    else:
        csv_mentor_ids = None
        fit_scores = None

    mentors: List[Mentor] = create_mentors_for_tables(
        num_tables=num_tables,
        seed=seed,
        mentors_per_table=mentors_per_table,
        num_mentors_pool=num_mentors_pool,
        min_per_table=min_per_table,
        max_per_table=max_per_table,
        csv_mentor_ids=csv_mentor_ids,
    )

    startups: List[Startup] = create_startups_with_os_oc(
        mentors=mentors,
        num_startups=num_startups,
        seed=seed,
        fit_scores=fit_scores,
    )

    return mentors, startups
