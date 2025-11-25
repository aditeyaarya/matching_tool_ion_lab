# cdl_matching/scheduling/diagnostics.py
from __future__ import annotations

from typing import List, Dict, Tuple, Set, Iterable, Any
from collections import Counter
from copy import deepcopy

from ..models import Mentor, Startup
from .sets_and_params import build_sets_and_params


def analyze_session_feasibility(
    mentors: List[Mentor],
    startups: List[Startup],
    num_sgms: int = 3,
    os_sgms_allowed: Tuple[int, ...] = (1, 2),
    oc_sgms_allowed: Tuple[int, ...] = (2, 3),
) -> Dict[str, Any]:
    """
    Analyze if the current mentors/startups configuration can *possibly* be
    scheduled under the rules (before running MILP).

    Returns a dict with:
      - 'ok': bool
      - 'messages': list[str] (human-readable diagnostics)
      - 'suggestion': str (summary)

      - 'os_table_counts': Dict[int, int]
      - 'oc_table_counts': Dict[int, int]
      - 'total_table_meetings': Dict[int, int]     (OS + OC)

      - 'os_overloaded': List[Tuple[int, int]]
      - 'oc_overloaded': List[Tuple[int, int]]
      - 'total_overloaded': List[Tuple[int, int]]

      - 'max_os_per_table': int
      - 'max_oc_per_table': int
      - 'num_startups': int
      - 'num_tables': int
      - 'min_tables_from_os': int  (necessary lower bound from OS capacity)
      - 'min_tables_from_oc': int  (necessary lower bound from OC capacity)
    """
    messages: List[str] = []

    S, T, table_os, table_oc = build_sets_and_params(mentors, startups)

    num_startups = len(S)
    num_tables = len(T)

    # ---------- 1. Per-SGM capacity check ----------
    # Each SGM has `num_tables` slots. Each startup needs 1 slot in each SGM.
    # Necessary: num_startups <= num_tables.
    if num_startups > num_tables:
        messages.append(
            f"Per-SGM capacity violated: {num_startups} startups but only "
            f"{num_tables} tables. Must add tables or reduce startups."
        )

    # ---------- 2. Per-table OS/OC capacity implied by allowed SGMs ----------
    max_os_per_table = len(os_sgms_allowed)
    max_oc_per_table = len(oc_sgms_allowed)

    # Count OS/OC assignments per table
    os_table_counts: Dict[int, int] = {t: 0 for t in T}
    oc_table_counts: Dict[int, int] = {t: 0 for t in T}

    for s in S:
        os_table = table_os[s]
        oc_table = table_oc[s]
        os_table_counts[os_table] += 1
        oc_table_counts[oc_table] += 1

    # OS overload
    os_overloaded: List[Tuple[int, int]] = []
    for t, c in os_table_counts.items():
        if c > max_os_per_table:
            os_overloaded.append((t, c))

    if os_overloaded:
        for t, c in os_overloaded:
            messages.append(
                f"Table {t} has {c} startups needing OS there, "
                f"but with OS allowed in {os_sgms_allowed}, "
                f"it can host at most {max_os_per_table} OS meetings."
            )
        messages.append(
            "To fix OS overloads: either add more tables and move some OS mentors, "
            "or reduce startups whose OS is on overloaded tables."
        )

    # OC overload
    oc_overloaded: List[Tuple[int, int]] = []
    for t, c in oc_table_counts.items():
        if c > max_oc_per_table:
            oc_overloaded.append((t, c))

    if oc_overloaded:
        for t, c in oc_overloaded:
            messages.append(
                f"Table {t} has {c} startups needing OC there, "
                f"but with OC allowed in {oc_sgms_allowed}, "
                f"it can host at most {max_oc_per_table} OC meetings."
            )
        messages.append(
            "To fix OC overloads: either add more tables and move some OC mentors, "
            "or reduce startups whose OC is on overloaded tables."
        )

    # ---------- 3. NEW: Total OS+OC meetings per table vs #SGMs ----------
    # Each required OS/OC meeting at table t needs its own SGM slot at t.
    # So we need: os_table_counts[t] + oc_table_counts[t] <= num_sgms.
    total_table_meetings: Dict[int, int] = {
        t: os_table_counts[t] + oc_table_counts[t] for t in T
    }
    total_overloaded: List[Tuple[int, int]] = [
        (t, c) for t, c in total_table_meetings.items() if c > num_sgms
    ]

    if total_overloaded:
        for t, c in total_overloaded:
            messages.append(
                f"Table {t} has {c} mandatory OS/OC meetings in total, "
                f"but with {num_sgms} SGMs it can host at most {num_sgms} "
                f"mentor-specific meetings. Even before 'generic' meetings, "
                f"this is structurally impossible."
            )
        messages.append(
            "To fix total table overloads: move some OS/OC mentors to other tables "
            "or reduce startups attached to those mentors."
        )

    # ---------- 4. Global necessary lower bound on number of tables ----------
    # Given each table can host at most `max_os_per_table` OS,
    # we need at least ceil(num_startups / max_os_per_table) tables from OS side,
    # and similarly for OC.
    def ceil_div(a: int, b: int) -> int:
        return (a + b - 1) // b if b > 0 else 0

    min_tables_from_os = ceil_div(num_startups, max_os_per_table) if max_os_per_table else 0
    min_tables_from_oc = ceil_div(num_startups, max_oc_per_table) if max_oc_per_table else 0

    ok = len(messages) == 0

    if ok:
        suggestion = (
            "No obvious structural capacity issues detected. "
            "MILP infeasibility (if any) would come from finer constraints."
        )
    else:
        suggestion = "Session structurally infeasible. "
        if num_startups > num_tables:
            suggestion += "Consider increasing tables or decreasing startups. "
        if os_overloaded or oc_overloaded or total_overloaded:
            suggestion += (
                "Consider redistributing OS/OC mentors across more tables, "
                "or decreasing startups linked to overloaded tables."
            )

    return {
        "ok": ok,
        "messages": messages,
        "suggestion": suggestion,
        "os_table_counts": os_table_counts,
        "oc_table_counts": oc_table_counts,
        "total_table_meetings": total_table_meetings,
        "os_overloaded": os_overloaded,
        "oc_overloaded": oc_overloaded,
        "total_overloaded": total_overloaded,
        "max_os_per_table": max_os_per_table,
        "max_oc_per_table": max_oc_per_table,
        "num_startups": num_startups,
        "num_tables": num_tables,
        "min_tables_from_os": min_tables_from_os,
        "min_tables_from_oc": min_tables_from_oc,
    }


# ======================================================================
#  Auto-fix: reassign OS/OC tables for some startups to remove overloads
# ======================================================================

def auto_fix_overloaded_tables(
    S: Iterable[str],
    T: Iterable[int],
    table_os: Dict[str, int],
    table_oc: Dict[str, int],
    num_sgms: int = 3,
    os_sgms_allowed: Tuple[int, ...] = (1, 2),
    oc_sgms_allowed: Tuple[int, ...] = (2, 3),
) -> Tuple[Dict[str, int], Dict[str, int], bool, Dict[str, Any]]:
    """
    Try to repair structural OS/OC overloads by reassigning some startups'
    OS/OC tables to tables with spare capacity.

    Args:
        S: Iterable of startup IDs.
        T: Iterable of table IDs.
        table_os: mapping startup -> OS table.
        table_oc: mapping startup -> OC table.
        num_sgms: number of SGMs (used for total capacity per table).
        os_sgms_allowed: SGMs where OS can happen (length = OS capacity per table).
        oc_sgms_allowed: SGMs where OC can happen (length = OC capacity per table).

    Returns:
        new_table_os, new_table_oc, success_flag, info_dict

        - success_flag == True  => all OS/OC overloads (including total OS+OC) were resolved.
        - success_flag == False => some overloads remain (need more tables / fewer startups).
        - info_dict includes final counts and overloaded tables after the attempt.
    """
    S_set: Set[str] = set(S)
    T_list: List[int] = list(T)

    max_os_per_table = len(os_sgms_allowed)
    max_oc_per_table = len(oc_sgms_allowed)

    # Work on copies so we don't mutate caller's dicts
    new_table_os = deepcopy(table_os)
    new_table_oc = deepcopy(table_oc)

    # Current counts
    os_count = Counter(new_table_os.values())
    oc_count = Counter(new_table_oc.values())

    def find_new_table_for(startup: str, is_os: bool) -> int | None:
        """
        Find a table with spare OS/OC capacity for this startup,
        different from the other mentor table, and not exceeding
        the total (OS+OC) capacity implied by num_sgms.
        """
        other_table = new_table_oc[startup] if is_os else new_table_os[startup]

        candidates: List[int] = []
        if is_os:
            for t in T_list:
                if t == other_table:
                    continue
                # OS capacity + total (OS+OC) capacity
                if os_count[t] < max_os_per_table and (os_count[t] + oc_count[t]) < num_sgms:
                    candidates.append(t)
            candidates.sort(key=lambda tt: os_count[tt] + oc_count[tt])
        else:
            for t in T_list:
                if t == other_table:
                    continue
                if oc_count[t] < max_oc_per_table and (os_count[t] + oc_count[t]) < num_sgms:
                    candidates.append(t)
            candidates.sort(key=lambda tt: os_count[tt] + oc_count[tt])

        return candidates[0] if candidates else None

    changed = False

    # ---------- First: fix OC overloads ----------
    for t in list(T_list):
        while oc_count[t] > max_oc_per_table:
            offenders = [s for s in S_set if new_table_oc[s] == t]
            if not offenders:
                break  # safety

            s = offenders[0]
            new_t = find_new_table_for(s, is_os=False)
            if new_t is None:
                # cannot resolve this overload automatically
                info = _build_overload_info(
                    S_set,
                    T_list,
                    new_table_os,
                    new_table_oc,
                    max_os_per_table,
                    max_oc_per_table,
                    num_sgms,
                )
                return new_table_os, new_table_oc, False, info

            oc_count[t] -= 1
            oc_count[new_t] += 1
            new_table_oc[s] = new_t
            changed = True

    # ---------- Then: fix OS overloads ----------
    for t in list(T_list):
        while os_count[t] > max_os_per_table:
            offenders = [s for s in S_set if new_table_os[s] == t]
            if not offenders:
                break

            s = offenders[0]
            new_t = find_new_table_for(s, is_os=True)
            if new_t is None:
                info = _build_overload_info(
                    S_set,
                    T_list,
                    new_table_os,
                    new_table_oc,
                    max_os_per_table,
                    max_oc_per_table,
                    num_sgms,
                )
                return new_table_os, new_table_oc, False, info

            os_count[t] -= 1
            os_count[new_t] += 1
            new_table_os[s] = new_t
            changed = True

    # Final diagnostics after attempted fix
    info = _build_overload_info(
        S_set,
        T_list,
        new_table_os,
        new_table_oc,
        max_os_per_table,
        max_oc_per_table,
        num_sgms,
    )

    success_flag = (
        not info["os_overloaded"]
        and not info["oc_overloaded"]
        and not info["total_overloaded"]
    )
    return new_table_os, new_table_oc, success_flag, info


def _build_overload_info(
    S: Set[str],
    T: List[int],
    table_os: Dict[str, int],
    table_oc: Dict[str, int],
    max_os_per_table: int,
    max_oc_per_table: int,
    num_sgms: int,
) -> Dict[str, Any]:
    """
    Internal helper: recompute per-table counts and overloaded tables
    for a given OS/OC assignment, including combined OS+OC overload.
    """
    os_table_counts: Dict[int, int] = {t: 0 for t in T}
    oc_table_counts: Dict[int, int] = {t: 0 for t in T}

    for s in S:
        os_table_counts[table_os[s]] += 1
        oc_table_counts[table_oc[s]] += 1

    os_overloaded: List[Tuple[int, int]] = [
        (t, c) for t, c in os_table_counts.items() if c > max_os_per_table
    ]
    oc_overloaded: List[Tuple[int, int]] = [
        (t, c) for t, c in oc_table_counts.items() if c > max_oc_per_table
    ]

    total_table_meetings: Dict[int, int] = {
        t: os_table_counts[t] + oc_table_counts[t] for t in T
    }
    total_overloaded: List[Tuple[int, int]] = [
        (t, c) for t, c in total_table_meetings.items() if c > num_sgms
    ]

    return {
        "os_table_counts": os_table_counts,
        "oc_table_counts": oc_table_counts,
        "total_table_meetings": total_table_meetings,
        "os_overloaded": os_overloaded,
        "oc_overloaded": oc_overloaded,
        "total_overloaded": total_overloaded,
        "max_os_per_table": max_os_per_table,
        "max_oc_per_table": max_oc_per_table,
    }
