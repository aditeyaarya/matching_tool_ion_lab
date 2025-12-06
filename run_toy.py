# run_toy.py

import pandas as pd

from cdl_matching.scheduling.joint_milp import solve_joint_schedule
from cdl_matching.config import NUM_STARTUPS_DEFAULT
from cdl_matching.data_generation.toy_dataset import make_toy_dataset
from cdl_matching.scheduling.solve import _build_table_fit


def optimize_mentor_selection(
    mentors: list,
    startups: list,
    mentor_fit: dict,
    target_count: int = 30,
    target_tables: int = 10
) -> list:
    """
    Select the best `target_count` mentors based on fit scores and
    redistribute them across `target_tables` tables.
    """
    print(f"\n[OPTIMIZATION] Selecting top {target_count} mentors for {len(startups)} startups...")

    # 1. Score each mentor (sum of top fit scores per startup)
    mentor_scores = {m.id: 0.0 for m in mentors}
    
    for s in startups:
        fits = []
        for m in mentors:
            score = mentor_fit.get((s.id, m.id), 0.0)
            fits.append((score, m.id))
        
        fits.sort(key=lambda x: x[0], reverse=True)
        
        # Give more weight to higher-ranked mentors
        for i in range(min(len(fits), 5)):
            score, mid = fits[i]
            mentor_scores[mid] += score

    # 2. Select top N mentors
    sorted_mentors = sorted(mentors, key=lambda m: mentor_scores[m.id], reverse=True)
    selected_mentors = sorted_mentors[:target_count]
    
    selected_ids = {m.id for m in selected_mentors}
    print(f"[OPTIMIZATION] Selected Mentors: {sorted(list(selected_ids))}")
    
    # 3. Redistribute across tables (round-robin across target_tables)
    selected_mentors.sort(key=lambda m: m.id)
    
    for i, m in enumerate(selected_mentors):
        new_table = (i % target_tables) + 1
        m.table_id = new_table
        
    print(f"[OPTIMIZATION] Redistributed {len(selected_mentors)} mentors across {target_tables} tables.")
    return selected_mentors


def main():
    # ---- Session settings ----
    import os
    import math
    from cdl_matching.config import FIT_SCORES_CSV_PATH, MENTORS_PER_TABLE_DEFAULT
    from cdl_matching.data_generation.toy_dataset import load_fit_from_csv

    num_tables = 10
    num_sgms = 3

    # If CSV exists, override settings to match the data
    num_startups = NUM_STARTUPS_DEFAULT
    num_mentors_pool = 35
    fit_data = None
    
    if os.path.exists(FIT_SCORES_CSV_PATH):
        print(f"Found CSV at {FIT_SCORES_CSV_PATH}. Loading full dataset...")
        fit_data = load_fit_from_csv(FIT_SCORES_CSV_PATH)
        
        if fit_data:
            unique_startups = {k[0] for k in fit_data.keys()}
            unique_mentors = {k[1] for k in fit_data.keys()}
            
            num_startups = len(unique_startups)
            num_mentors_pool = len(unique_mentors)
            
            # Initial tables - enough to hold everyone
            num_tables = math.ceil(num_mentors_pool / MENTORS_PER_TABLE_DEFAULT)
            if num_tables < 1:
                num_tables = 1

    # ---- Generate toy mentors + startups + fit scores ----
    target_mentors = 30
    target_tables = 10

    mentors, startups, mentor_fit = make_toy_dataset(
        num_tables=num_tables,
        num_startups=num_startups,
        mentors_per_table=3,
        num_mentors_pool=num_mentors_pool,
        fit_matrix=fit_data if fit_data is not None else None,
    )

    # Optional: shrink mentor pool via heuristic pre-selection
    if len(mentors) > target_mentors:
        mentors = optimize_mentor_selection(
            mentors,
            startups,
            mentor_fit,
            target_count=target_mentors,
            target_tables=target_tables,
        )
        # Note: startups keep their domains and IDs; OS/OC will be overwritten
        # later by the joint MILP, so no need to re-run create_startups_with_os_oc.

    # ============================
    #  PRINT FIT MATRICES (PANDAS)
    # ============================

    # Mentor–Startup fit matrix
    mentor_ids = [m.id for m in mentors]
    startup_ids = sorted(s.id for s in startups)

    mentor_startup_matrix = [
        [mentor_fit[(sid, mid)] for mid in mentor_ids]
        for sid in startup_ids
    ]
    df_ms = pd.DataFrame(
        mentor_startup_matrix,
        index=startup_ids,
        columns=mentor_ids,
    )

    print("=== MENTOR–STARTUP FIT MATRIX (0–1) ===")
    print(df_ms.round(2))
    print()

    print("=== MENTOR GROUPS (TABLE ASSIGNMENTS) ===")
    mentors_by_table = {}
    for m in mentors:
        mentors_by_table.setdefault(m.table_id, []).append(m.id)
    
    for t in sorted(mentors_by_table.keys()):
        m_ids = sorted(mentors_by_table[t])
        print(f"Table {t}: {', '.join(m_ids)}")
    print()

    # Table–Startup fit matrix (for inspection only)
    table_fit = _build_table_fit(mentors, startups, mentor_fit)
    tables = sorted({m.table_id for m in mentors})

    table_startup_matrix = [
        [table_fit[(sid, t)] for t in tables]
        for sid in startup_ids
    ]
    df_ts = pd.DataFrame(
        table_startup_matrix,
        index=startup_ids,
        columns=[f"Table {t}" for t in tables],
    )

    print("=== TABLE–STARTUP FIT MATRIX (max mentor fit per table) ===")
    print(df_ts.round(2))
    print()

    print("\n=== MENTOR GROUPING ANALYSIS (Top-3 per startup from CURRENT mentor pool) ===")
    for s in sorted(startups, key=lambda x: x.id):
        my_fits = []
        for m in mentors:
            my_fits.append((mentor_fit.get((s.id, m.id), 0.0), m))
        my_fits.sort(key=lambda x: x[0], reverse=True)
        
        top_3 = my_fits[:3]
        print(f"\n{s.id} Top 3 Available Mentors:")
        for score, m in top_3:
            print(f"  - {m.id} (Score {score:.2f}) @ Table {m.table_id}")
    print()

    # =====================================
    #  JOINT MILP: mentor selection + SGMs
    # =====================================
    print("=== JOINT MILP: OS/OC SELECTION + SCHEDULING ===")
    status, sol, os_assign, oc_assign = solve_joint_schedule(
        mentors,
        startups,
        mentor_fit,
        num_sgms=num_sgms,
    )
    print("Solver status:", status)
    print()

    if status not in ("Optimal", "Feasible"):
        print("No valid joint schedule – model is", status)
        return

    # ---- Print chosen OS/OC per startup ----
    print("=== OS / OC MENTORS PER STARTUP (from joint MILP) ===")
    mentor_map = {m.id: m for m in mentors}
    for s in sorted(startups, key=lambda x: x.id):
        os_id = os_assign.get(s.id, None)
        oc_id = oc_assign.get(s.id, None)

        os_m = mentor_map.get(os_id) if os_id else None
        oc_m = mentor_map.get(oc_id) if oc_id else None

        print(f"{s.id}:")
        print(f"  - OS: {os_id} (Table {os_m.table_id if os_m else 'None'})")
        print(f"  - OC: {oc_id} (Table {oc_m.table_id if oc_m else 'None'})")
    print()

    # ---- Pretty print schedule: SGM × Table ----
    tables = sorted({m.table_id for m in mentors})
    sgms = list(range(1, num_sgms + 1))

    for k in sgms:
        print(f"=== SGM {k} ===")
        for t in tables:
            startup_here = [
                s_id for (s_id, tt, kk), v in sol.items()
                if v == 1 and tt == t and kk == k
            ]
            label = startup_here[0] if startup_here else "-"
            mentors_here = ", ".join(
                sorted(m.id for m in mentors if m.table_id == t)
            ) or "–"
            print(f"Table {t} [{mentors_here}]: {label}")
        print()

    # ---- Verification: OS in {1,2}, OC in {2,3}, and OS < OC ----
    print("=== VERIFICATION: OS IN {1,2}, OC IN {2,3}, OS < OC ===")
    startup_schedule = {s.id: [] for s in startups}
    for (s_id, t_id, k), v in sol.items():
        if v == 1:
            startup_schedule[s_id].append((t_id, k))

    for s in sorted(startups, key=lambda x: x.id):
        os_id = os_assign.get(s.id)
        oc_id = oc_assign.get(s.id)
        os_table = mentor_map[os_id].table_id if os_id else None
        oc_table = mentor_map[oc_id].table_id if oc_id else None

        os_sgm = None
        oc_sgm = None
        for t_id, k in startup_schedule[s.id]:
            if t_id == os_table and k in (1, 2):
                os_sgm = k
            if t_id == oc_table and k in (2, 3):
                oc_sgm = k

        status_flag = "PASS"
        if os_sgm is None or oc_sgm is None or not (os_sgm < oc_sgm):
            status_flag = "FAIL"

        print(f"{s.id}: OS at SGM {os_sgm}, OC at SGM {oc_sgm} -> {status_flag}")
    print()


if __name__ == "__main__":
    main()
