# cdl_matching/scheduling/interactive_repair.py
from __future__ import annotations

from typing import List, Dict, Tuple

from ..models import Mentor, Startup
from ..config import (
    NUM_STARTUPS_DEFAULT,
    MENTORS_PER_TABLE_DEFAULT,
    MAX_OS_PER_MENTOR,
    MAX_OC_PER_MENTOR,
)
from ..data_generation.toy_dataset import make_toy_dataset
from .diagnostics import analyze_session_feasibility
from .sets_and_params import build_sets_and_params


def _index_mentors_by_id(mentors: List[Mentor]) -> Dict[str, Mentor]:
    return {m.id: m for m in mentors}


def _recompute_loads(
    mentors: List[Mentor],
    startups: List[Startup],
) -> Tuple[Dict[str, int], Dict[str, int], Dict[int, int], Dict[int, int]]:
    """
    Recompute per-mentor and per-table OS/OC loads from current startups.
    """
    mentor_by_id = _index_mentors_by_id(mentors)
    os_load = {m.id: 0 for m in mentors}
    oc_load = {m.id: 0 for m in mentors}
    table_os_load: Dict[int, int] = {m.table_id: 0 for m in mentors}
    table_oc_load: Dict[int, int] = {m.table_id: 0 for m in mentors}

    for st in startups:
        os_m = mentor_by_id[st.os_id]
        oc_m = mentor_by_id[st.oc_id]
        os_load[os_m.id] += 1
        oc_load[oc_m.id] += 1
        table_os_load[os_m.table_id] += 1
        table_oc_load[oc_m.table_id] += 1

    return os_load, oc_load, table_os_load, table_oc_load


def _score_startup(
    st: Startup,
    table_os: Dict[str, int],
    table_oc: Dict[str, int],
    os_overload: Dict[int, int],
    oc_overload: Dict[int, int],
    total_overload: Dict[int, int],
) -> int:
    """
    Score for a startup = overload(OS_table) + overload(OC_table),
    where overload includes both per-role and total overload.
    """
    os_t = table_os[st.id]
    oc_t = table_oc[st.id]

    score = 0
    score += os_overload.get(os_t, 0)
    score += oc_overload.get(oc_t, 0)
    score += total_overload.get(os_t, 0)
    score += total_overload.get(oc_t, 0)
    return score


def _choose_startup_for_overloaded_table_with_score(
    startups: List[Startup],
    bad_table: int,
    role: str,
    table_os: Dict[str, int],
    table_oc: Dict[str, int],
    os_overload: Dict[int, int],
    oc_overload: Dict[int, int],
    total_overload: Dict[int, int],
) -> Tuple[Startup, int, List[Tuple[str, int]]]:
    """
    Among startups that have OS/OC on the overloaded table, choose the
    one with the highest score.

    Returns:
      - chosen startup
      - its score
      - list of (startup_id, score) for all candidates on that table/role
    """
    if role == "OS":
        candidates = [st for st in startups if table_os[st.id] == bad_table]
    else:
        candidates = [st for st in startups if table_oc[st.id] == bad_table]

    if not candidates:
        raise RuntimeError(f"No startup found on table {bad_table} for role {role}.")

    scored: List[Tuple[str, int]] = []
    best_st = candidates[0]
    best_score = _score_startup(
        best_st, table_os, table_oc, os_overload, oc_overload, total_overload
    )
    scored.append((best_st.id, best_score))

    for st in candidates[1:]:
        sc = _score_startup(st, table_os, table_oc, os_overload, oc_overload, total_overload)
        scored.append((st.id, sc))
        if sc > best_score:
            best_score = sc
            best_st = st

    return best_st, best_score, scored


def _find_candidate_mentors_for_role(
    mentors: List[Mentor],
    startups: List[Startup],
    role: str,
    bad_table: int,
    max_os_per_table: int,
    max_oc_per_table: int,
    num_sgms: int,
) -> List[Mentor]:
    """
    Return mentors that could be used to *move* a startup away from an overloaded table,
    based on current loads and table caps.

    We ensure:
      - mentor is eligible for the role
      - mentor is not already at the overloaded table
      - mentor has remaining per-mentor capacity
      - mentor's table has remaining per-table capacity (using the same
        caps as the diagnostics: number of allowed SGMs for that role)
      - mentor's table does NOT exceed total OS+OC capacity (<= num_sgms).
    """
    os_load, oc_load, table_os_load, table_oc_load = _recompute_loads(
        mentors, startups
    )

    candidates: List[Mentor] = []
    for m in mentors:
        if m.table_id == bad_table:
            # we explicitly want to move OFF this table
            continue

        # total OS+OC meetings already attached to this table
        total_here = table_os_load[m.table_id] + table_oc_load[m.table_id]
        if total_here >= num_sgms:
            # cannot add any more mandatory meetings to this table
            continue

        if role == "OS":
            if not m.can_be_os:
                continue
            if os_load[m.id] >= MAX_OS_PER_MENTOR:
                continue
            if table_os_load[m.table_id] >= max_os_per_table:
                continue
        else:
            if not m.can_be_oc:
                continue
            if oc_load[m.id] >= MAX_OC_PER_MENTOR:
                continue
            if table_oc_load[m.table_id] >= max_oc_per_table:
                continue

        candidates.append(m)

    # Sort by current total load so we try to balance things
    candidates.sort(
        key=lambda mm: table_os_load[mm.table_id] + table_oc_load[mm.table_id]
    )
    return candidates


def _auto_fix_one_overload(
    mentors: List[Mentor],
    startups: List[Startup],
    os_overloaded_tables: List[int],
    oc_overloaded_tables: List[int],
    total_overloaded_tables: List[int],
    os_overload: Dict[int, int],
    oc_overload: Dict[int, int],
    total_overload: Dict[int, int],
    max_os_per_table: int,
    max_oc_per_table: int,
    num_sgms: int,
) -> bool:
    """
    Try to fix one overload by changing OS or OC mentor for a single startup.

    Strategy:
      - Prefer fixing OS overload first, then OC overload, then total overload.
      - Among startups on that table (for that role), choose the one with
        highest score = overload(OS_table) + overload(OC_table) + total_overload.
      - Move that startup to a different mentor/table for that role,
        but ONLY to tables with spare per-table *and* total OS+OC capacity.
    """
    S, T, table_os, table_oc = build_sets_and_params(mentors, startups)

    # Priority: OS overload → OC overload → total overload
    if os_overloaded_tables:
        bad_table = os_overloaded_tables[0]
        role = "OS"
    elif oc_overloaded_tables:
        bad_table = oc_overloaded_tables[0]
        role = "OC"
    elif total_overloaded_tables:
        bad_table = total_overloaded_tables[0]
        # Decide whether to move OS or OC based on which side is heavier
        os_count = sum(1 for s in S if table_os[s] == bad_table)
        oc_count = sum(1 for s in S if table_oc[s] == bad_table)
        role = "OS" if os_count >= oc_count else "OC"
    else:
        return False

    # Pick startup to modify using score
    st, score, scored_list = _choose_startup_for_overloaded_table_with_score(
        startups,
        bad_table,
        role,
        table_os,
        table_oc,
        os_overload,
        oc_overload,
        total_overload,
    )

    print(f"[AUTO-FIX] Considering {role} overload on table {bad_table}")
    print("[AUTO-FIX] Candidate startups on that table and their scores:")
    for sid, sc in scored_list:
        print(f"  - {sid}: score={sc}")
    print(
        f"[AUTO-FIX] Choosing startup {st.id} with highest score={score} "
        f"to move its {role}."
    )

    # Find candidate mentors on other tables with free capacity for this role
    candidates = _find_candidate_mentors_for_role(
        mentors,
        startups,
        role,
        bad_table,
        max_os_per_table,
        max_oc_per_table,
        num_sgms,
    )
    if not candidates:
        print(
            "[AUTO-FIX] No valid new mentors found for this role "
            "with spare per-table and total capacity. Cannot fix structurally."
        )
        return False

    new_mentor = candidates[0]

    if role == "OS":
        print(
            f"[AUTO-FIX] Moving OS of {st.id} from table {bad_table} "
            f"to mentor {new_mentor.id} at table {new_mentor.table_id}"
        )
        st.os_id = new_mentor.id
    else:
        print(
            f"[AUTO-FIX] Moving OC of {st.id} from table {bad_table} "
            f"to mentor {new_mentor.id} at table {new_mentor.table_id}"
        )
        st.oc_id = new_mentor.id

    return True


def interactive_build_session(
    num_tables: int = 10,
    num_startups: int = NUM_STARTUPS_DEFAULT,
    mentors_per_table: int = MENTORS_PER_TABLE_DEFAULT,
    num_sgms: int = 3,
    max_rounds: int = 10,
) -> Tuple[List[Mentor], List[Startup]]:
    """
    High-level loop:
      - generate mentors + startups
      - run diagnostics
      - if infeasible, ask user whether to:
          * auto-fix OS/OC assignments (guided by scores)
          * increase tables
          * decrease startups
          * regenerate from scratch
      - repeat until structurally feasible or max_rounds hit

    IMPORTANT:
      - We now KEEP the same mentors/startups across rounds unless the
        user explicitly chooses to regenerate/change tables/startups.
        This way, auto-fixes actually accumulate instead of being
        thrown away every loop.
    """
    round_idx = 0

    # Initial generation
    mentors, startups = make_toy_dataset(
        num_tables=num_tables,
        num_startups=num_startups,
        mentors_per_table=mentors_per_table,
    )

    while True:
        round_idx += 1
        print(f"\n========== ROUND {round_idx} ==========")
        print(f"Current settings: tables={num_tables}, startups={num_startups}")

        diag = analyze_session_feasibility(
            mentors,
            startups,
            num_sgms=num_sgms,
            os_sgms_allowed=(1, 2),
            oc_sgms_allowed=(2, 3),
        )

        print("=== DIAGNOSTICS ===")
        if diag["messages"]:
            for msg in diag["messages"]:
                print("-", msg)
        else:
            print("- No structural capacity issues detected.")
        print("Suggestion:", diag["suggestion"])

        if diag["ok"]:
            print("\n✅ Session is structurally feasible.")
            return mentors, startups

        if round_idx >= max_rounds:
            print("\n❌ Reached maximum rounds without feasibility.")
            return mentors, startups

        # Compute overload magnitudes per table
        os_counts = diag["os_table_counts"]
        oc_counts = diag["oc_table_counts"]
        total_counts = diag["total_table_meetings"]

        # OS allowed in SGM1 & SGM2 → at most 2 OS per table
        max_os_per_table = len((1, 2))
        # OC allowed in SGM2 & SGM3 → at most 2 OC per table
        max_oc_per_table = len((2, 3))

        os_overload: Dict[int, int] = {
            t: max(0, c - max_os_per_table) for t, c in os_counts.items()
        }
        oc_overload: Dict[int, int] = {
            t: max(0, c - max_oc_per_table) for t, c in oc_counts.items()
        }
        total_overload: Dict[int, int] = {
            t: max(0, c - num_sgms) for t, c in total_counts.items()
        }

        os_over = [t for t, extra in os_overload.items() if extra > 0]
        oc_over = [t for t, extra in oc_overload.items() if extra > 0]
        total_over = [t for t, extra in total_overload.items() if extra > 0]

        print("\nOverloaded OS tables:", os_over)
        print("Overloaded OC tables:", oc_over)
        print("Overloaded TOTAL tables (OS+OC > SGMs):", total_over)

        print(
            "\nChoose an action:\n"
            "  1) Try automatic OS/OC reassignment (guided by scores)\n"
            "  2) Increase number of tables by 1 (regenerate)\n"
            "  3) Decrease number of startups by 1 (regenerate)\n"
            "  4) Regenerate from scratch with same settings\n"
            "  5) Abort\n"
        )
        choice = input("Your choice [1-5]: ").strip()

        if choice == "1":
            fixed = _auto_fix_one_overload(
                mentors,
                startups,
                os_over,
                oc_over,
                total_over,
                os_overload,
                oc_overload,
                total_overload,
                max_os_per_table,
                max_oc_per_table,
                num_sgms,
            )
            if not fixed:
                print(
                    "Could not find a valid OS/OC reassignment that respects "
                    "per-mentor, per-table, and total capacity. Try another action."
                )
            else:
                # After in-place fix, re-run diagnostics on SAME mentors/startups
                diag2 = analyze_session_feasibility(
                    mentors,
                    startups,
                    num_sgms=num_sgms,
                    os_sgms_allowed=(1, 2),
                    oc_sgms_allowed=(2, 3),
                )
                print("\n=== DIAGNOSTICS AFTER AUTO-FIX ===")
                if diag2["messages"]:
                    for msg in diag2["messages"]:
                        print("-", msg)
                else:
                    print("- No structural capacity issues detected.")
                print("Suggestion:", diag2["suggestion"])

                if diag2["ok"]:
                    print("\n✅ After auto-fix, session is structurally feasible.")
                    return mentors, startups
                else:
                    print("\nStill infeasible after auto-fix, continuing loop...")
                    # IMPORTANT: we do NOT regenerate here; we keep the modified
                    # mentors/startups and go to the next round.
                    continue

        elif choice == "2":
            num_tables += 1
            print(f"➡ Increasing tables to {num_tables} and regenerating...\n")
            mentors, startups = make_toy_dataset(
                num_tables=num_tables,
                num_startups=num_startups,
                mentors_per_table=mentors_per_table,
            )
            continue

        elif choice == "3":
            if num_startups <= 1:
                print("Cannot reduce startups below 1.")
            else:
                num_startups -= 1
                print(f"➡ Decreasing startups to {num_startups} and regenerating...\n")
                mentors, startups = make_toy_dataset(
                    num_tables=num_tables,
                    num_startups=num_startups,
                    mentors_per_table=mentors_per_table,
                )
            continue

        elif choice == "4":
            print("➡ Regenerating from scratch with same settings...\n")
            mentors, startups = make_toy_dataset(
                num_tables=num_tables,
                num_startups=num_startups,
                mentors_per_table=mentors_per_table,
            )
            continue

        elif choice == "5":
            print("Aborting interactive build.")
            return mentors, startups

        else:
            print("Invalid choice, please select 1–5.")
