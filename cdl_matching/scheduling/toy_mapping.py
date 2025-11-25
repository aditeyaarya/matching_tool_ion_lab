# cdl_matching/scheduling/toy_mapping.py
from __future__ import annotations

from typing import List, Dict, Tuple
from collections import defaultdict
import random


def build_safe_os_oc_mapping(
    startup_ids: List[str],
    tables: List[int],
    num_sgms: int = 3,
    os_sgms_allowed: Tuple[int, ...] = (1, 2),
    oc_sgms_allowed: Tuple[int, ...] = (2, 3),
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    Construct OS/OC table mappings for a toy instance such that:

      - For every table t:
            OS_count[t] <= len(os_sgms_allowed)
            OC_count[t] <= len(oc_sgms_allowed)
            OS_count[t] + OC_count[t] <= num_sgms

      - For every startup s:
            OS_table[s] != OC_table[s]

    This guarantees that the structural checks and MILP won't fail due to
    pure capacity reasons on the toy instance (10 startups, 10 tables, etc.).
    """
    max_os_per_table = len(os_sgms_allowed)   # 2
    max_oc_per_table = len(oc_sgms_allowed)   # 2
    max_total_per_table = num_sgms            # 3

    os_count = defaultdict(int)
    oc_count = defaultdict(int)

    table_os: Dict[str, int] = {}
    table_oc: Dict[str, int] = {}

    # Shuffle startups to avoid always hitting the same pattern
    shuffled_startups = list(startup_ids)
    random.shuffle(shuffled_startups)

    # ---------- 1) Assign OS tables ----------
    for s in shuffled_startups:
        # candidate tables with spare OS capacity and total capacity
        candidates = [
            t for t in tables
            if os_count[t] < max_os_per_table
            and (os_count[t] + oc_count[t]) < max_total_per_table
        ]
        if not candidates:
            raise RuntimeError(
                "Unable to assign OS table without exceeding per-table capacity. "
                "Try more tables or fewer startups in the toy generator."
            )

        # choose table with smallest current load to balance
        candidates.sort(key=lambda t: os_count[t] + oc_count[t])
        chosen = candidates[0]
        table_os[s] = chosen
        os_count[chosen] += 1

    # ---------- 2) Assign OC tables (different from OS) ----------
    for s in shuffled_startups:
        os_table = table_os[s]

        candidates = [
            t for t in tables
            if t != os_table
            and oc_count[t] < max_oc_per_table
            and (os_count[t] + oc_count[t]) < max_total_per_table
        ]
        if not candidates:
            raise RuntimeError(
                f"Unable to assign OC table for startup {s} without exceeding "
                "per-table capacity. Try more tables or fewer startups."
            )

        candidates.sort(key=lambda t: os_count[t] + oc_count[t])
        chosen = candidates[0]
        table_oc[s] = chosen
        oc_count[chosen] += 1

    # Final sanity check (paranoid but useful)
    for t in tables:
        os_c = os_count[t]
        oc_c = oc_count[t]
        if os_c > max_os_per_table or oc_c > max_oc_per_table or (os_c + oc_c) > max_total_per_table:
            raise RuntimeError(
                f"Post-check failed for table {t}: OS={os_c}, OC={oc_c}, "
                f"total={os_c+oc_c}, with limits "
                f"OS<={max_os_per_table}, OC<={max_oc_per_table}, "
                f"total<={max_total_per_table}"
            )

    return table_os, table_oc
