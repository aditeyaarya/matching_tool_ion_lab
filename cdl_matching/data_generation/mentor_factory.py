# cdl_matching/data_generation/mentor_factory.py
from __future__ import annotations

import random
from typing import List, Set, Optional

from ..models import Mentor
from ..config import (
    DEFAULT_SEED,
    MENTORS_PER_TABLE_DEFAULT,
    MIN_MENTORS_PER_TABLE,
    MAX_MENTORS_PER_TABLE,
)
from .domains import get_default_domains
from .fit_loader import load_fit_scores


def _distribute_mentors_across_tables(
    num_tables: int,
    total_mentors: int,
    min_per_table: int,
    max_per_table: int,
) -> List[int]:
    """
    Distribute `total_mentors` across `num_tables` such that:
      - each table has between min_per_table and max_per_table mentors
      - sum(counts) == total_mentors
    """
    counts = [min_per_table] * num_tables
    remaining = total_mentors - num_tables * min_per_table

    if remaining < 0:
        raise ValueError(
            f"Impossible distribution: total_mentors={total_mentors} "
            f"is less than num_tables * min_per_table = {num_tables * min_per_table}."
        )

    idx = 0
    while remaining > 0:
        if counts[idx] < max_per_table:
            counts[idx] += 1
            remaining -= 1
        idx = (idx + 1) % num_tables

        if idx == 0 and all(c == max_per_table for c in counts) and remaining > 0:
            # Should not happen if we respected the max capacity when choosing total_mentors
            raise RuntimeError(
                "Internal error in _distribute_mentors_across_tables: "
                "no room left but remaining > 0."
            )

    return counts


def create_mentors_for_tables(
    num_tables: int,
    seed: int = DEFAULT_SEED,
    mentors_per_table: int = MENTORS_PER_TABLE_DEFAULT,
    num_mentors_pool: int | None = None,
    min_per_table: int = MIN_MENTORS_PER_TABLE,
    max_per_table: int = MAX_MENTORS_PER_TABLE,
    csv_mentor_ids: Optional[List[str]] = None,
) -> List[Mentor]:
    """
    Create mentors and assign them to tables.

    - Enforces: min_per_table <= mentors_at_table <= max_per_table
    - If num_mentors_pool is given:
        * uses that as the total pool, but caps at num_tables * max_per_table
        * excess mentors are conceptually "unused" (low-fit) upstream
    """
    if min_per_table < 0 or max_per_table < min_per_table:
        raise ValueError(
            f"Invalid min/max per table: min={min_per_table}, max={max_per_table}."
        )

    rng = random.Random(seed)

    max_capacity = num_tables * max_per_table
    min_needed = num_tables * min_per_table

    if num_mentors_pool is not None:
        if num_mentors_pool < min_needed:
            raise ValueError(
                "Infeasible mentor pool size:\n"
                f"  num_tables = {num_tables}\n"
                f"  min_per_table = {min_per_table}\n"
                f"  => need at least {min_needed} mentors\n"
                f"  but num_mentors_pool = {num_mentors_pool}.\n"
                "Either increase the pool or reduce the number of tables."
            )
        total_mentors = min(num_mentors_pool, max_capacity)
    else:
        if not (min_per_table <= mentors_per_table <= max_per_table):
            raise ValueError(
                f"mentors_per_table={mentors_per_table} must be between "
                f"{min_per_table} and {max_per_table}."
            )
        total_mentors = num_tables * mentors_per_table
        if total_mentors < min_needed:
            raise ValueError(
                f"With num_tables={num_tables} and mentors_per_table={mentors_per_table}, "
                f"you get total_mentors={total_mentors}, which is below the minimum "
                f"{min_needed} required for {min_per_table} per table."
            )
        if total_mentors > max_capacity:
            total_mentors = max_capacity

    counts_per_table = _distribute_mentors_across_tables(
        num_tables=num_tables,
        total_mentors=total_mentors,
        min_per_table=min_per_table,
        max_per_table=max_per_table,
    )

    # ---- domains: give each mentor 2 random domains from DEFAULT_DOMAINS ----
    all_domains: List[str] = get_default_domains()

    mentors: List[Mentor] = []
    mentor_id_counter = 1

    if csv_mentor_ids:
        table_ids = list(range(1, num_tables + 1))
        t_idx = 0

        for mid in csv_mentor_ids:
            mentors.append(
                Mentor(
                    id=mid,
                    name=f"Mentor {mid}",
                    table_id=table_ids[t_idx],
                    domains=["A", "B"],
                    can_be_os=True,
                    can_be_oc=True,
                )
            )
            t_idx = (t_idx + 1) % len(table_ids)

        return mentors


    for table_idx, count in enumerate(counts_per_table, start=1):
        for _ in range(count):
            mentor_id = f"M{mentor_id_counter:03d}"
            name = f"Mentor {mentor_id_counter}"

            # 2 random domains per mentor (toy behaviour)
            k = 2 if len(all_domains) >= 2 else 1
            mentor_domains: Set[str] = set(rng.sample(all_domains, k=k))

            mentor = Mentor(
                id=mentor_id,
                name=name,
                table_id=table_idx,
                domains=mentor_domains,
                # can_be_os / can_be_oc / conflicts use dataclass defaults
            )

            mentors.append(mentor)
            mentor_id_counter += 1

    return mentors
