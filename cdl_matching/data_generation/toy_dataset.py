# cdl_matching/data_generation/toy_dataset.py
from __future__ import annotations
from typing import List, Tuple, Dict, Optional
import random
import csv
import os

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


def load_fit_from_csv(csv_path: str) -> Optional[Dict[tuple[str, str], float]]:
    """
    Load fit matrix from CSV.
    Expected format:
        ,S1,S2,S3
    M001,0.9,0.1,0.1
    ...
    """
    if not os.path.exists(csv_path):
        return None
        
    fit_data = {}
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        headers = next(reader) # [, S1, S2, S3]
        startup_ids = headers[1:]
        
        for row in reader:
            if not row: continue
            mentor_id = row[0]
            scores = row[1:]
            for i, score_str in enumerate(scores):
                if i < len(startup_ids):
                    sid = startup_ids[i]
                    try:
                        val = float(score_str)
                        fit_data[(sid, mentor_id)] = val
                    except ValueError:
                        pass
    return fit_data


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
    fit_matrix: Optional[Dict[tuple[str, str], float]] = None,
) -> Tuple[List[Mentor], List[Startup], Dict[tuple[str, str], float]]:
    """
    Return mentors, startups, and a random mentor_fit matrix.
    If fit_matrix is provided, use it instead of random generation.
    """

    # If fit_matrix is provided, derive mentors and startups from it
    if fit_matrix:
        unique_mentors = sorted(list({k[1] for k in fit_matrix.keys()}))
        unique_startups = sorted(list({k[0] for k in fit_matrix.keys()}))
        
        # Create mentors from the matrix keys
        mentors = []
        # Assign tables round-robin style initially? Or just create them.
        # We need to assign them to tables for the 'pool'.
        # Let's just create them with dummy tables for now, 
        # or use the factory but force IDs.
        
        # Better: Create mentors using factory but with specific count
        # But factory creates random IDs? No, factory usually creates M001...
        # Let's just create Mentor objects directly to match the CSV IDs.
        
        # We need to assign table_id. Let's distribute them evenly across num_tables.
        import math
        mentors_per_t = math.ceil(len(unique_mentors) / num_tables)
        
        for i, mid in enumerate(unique_mentors):
            tid = (i // mentors_per_t) + 1
            if tid > num_tables: tid = num_tables
            mentors.append(Mentor(
                id=mid,
                name=f"Mentor {mid}",
                table_id=tid,
                domains={"General"}, # Dummy domain
            ))
            
        num_startups = len(unique_startups)
        mentor_fit = fit_matrix
        
    else:
        mentors = create_mentors_for_tables(
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
