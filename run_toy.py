# run_toy.py

import pandas as pd

from cdl_matching.config import NUM_STARTUPS_DEFAULT
from cdl_matching.data_generation.toy_dataset import make_toy_dataset
from cdl_matching.scheduling.solve import solve_schedule, _build_table_fit
from cdl_matching.scheduling.diagnostics import analyze_session_feasibility
from cdl_matching.scheduling.sets_and_params import build_sets_and_params


def optimize_mentor_selection(
    mentors: list,
    startups: list,
    mentor_fit: dict,
    target_count: int = 9,
    target_tables: int = 3
) -> list:
    """
    Select the best `target_count` mentors based on fit scores and
    redistribute them across `target_tables` tables.
    """
    print(f"\n[OPTIMIZATION] Selecting top {target_count} mentors for {len(startups)} startups...")

    # 1. Score each mentor
    # Heuristic: Sum of top 3 fit scores (since each mentor can meet at most 3 startups)
    # Or simply: Is this mentor in the Top N for any startup?
    
    mentor_scores = {m.id: 0.0 for m in mentors}
    
    # For each startup, find their favorite mentors
    for s in startups:
        # Get all fits for this startup
        fits = []
        for m in mentors:
            score = mentor_fit.get((s.id, m.id), 0.0)
            fits.append((score, m.id))
        
        # Sort descending
        fits.sort(key=lambda x: x[0], reverse=True)
        
        # Give points to the top candidates
        # Top 1 gets 3 pts, Top 2 gets 2 pts, Top 3 gets 1 pt
        for i in range(min(len(fits), 5)):  # Look at top 5 to be safe
            score, mid = fits[i]
            # Add the raw fit score to the mentor's utility
            mentor_scores[mid] += score

    # 2. Select top N mentors
    sorted_mentors = sorted(mentors, key=lambda m: mentor_scores[m.id], reverse=True)
    selected_mentors = sorted_mentors[:target_count]
    
    selected_ids = {m.id for m in selected_mentors}
    print(f"[OPTIMIZATION] Selected Mentors: {sorted(list(selected_ids))}")
    
    # 3. Redistribute across tables (Round Robin)
    # We want to mix them up so one table doesn't get all the best ones
    # (though with 3 tables and 3 slots, it matters less, but good practice)
    
    # Sort by ID for deterministic seating
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
            if num_tables < 1: num_tables = 1

    # ---- OPTIMIZE: Select best 9 mentors / 3 tables ----
    # Only if we have enough mentors to optimize
    target_mentors = 9
    target_tables = 3
    # ---- Generate toy mentors + startups + fit scores ----
    mentors, startups, mentor_fit = make_toy_dataset(
        num_tables=num_tables,
        num_startups=num_startups,
        mentors_per_table=3,
        num_mentors_pool=num_mentors_pool,
        fit_matrix=fit_data if 'fit_data' in locals() else None
    )

    if len(mentors) > target_mentors:
        mentors = optimize_mentor_selection(
            mentors, 
            startups, 
            mentor_fit, 
            target_count=target_mentors, 
            target_tables=target_tables
        )
        
        # Re-assign OS/OC based on the new subset
        from cdl_matching.data_generation.startup_factory import create_startups_with_os_oc
        print("[OPTIMIZATION] Re-assigning OS/OC mentors from the selected subset...")
        startups = create_startups_with_os_oc(
            mentors=mentors,
            num_startups=num_startups,
            seed=42,
            mentor_fit=mentor_fit
        )

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

    # Table–Startup fit matrix (what the MILP actually uses)
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

    # ---- Optional: inspect OS/OC table mapping ----
    S, T, table_os, table_oc = build_sets_and_params(mentors, startups)
    print("=== OS / OC TABLES PER STARTUP (VERIFICATION) ===")
    mentor_map = {m.id: m for m in mentors}
    for s in sorted(startups, key=lambda x: x.id):
        os_m = mentor_map.get(s.os_id)
        oc_m = mentor_map.get(s.oc_id)
        
        print(f"{s.id}:")
        print(f"  - OS: {s.os_id} (Table {os_m.table_id if os_m else 'None'}) ")
        print(f"  - OC: {s.oc_id} (Table {oc_m.table_id if oc_m else 'None'}) ")

    print("\n=== MENTOR GROUPING ANALYSIS ===")
    # Check if the "Best" mentors for each startup are actually selected/present
    for s in sorted(startups, key=lambda x: x.id):
        # Find top 3 mentors for this startup in the ENTIRE pool (if we had access) 
        # or just check if the current high-scorers are grouped well.
        # Let's list the top 3 mentors available in the 'mentors' list for this startup
        
        my_fits = []
        for m in mentors:
            my_fits.append((mentor_fit.get((s.id, m.id), 0.0), m))
        my_fits.sort(key=lambda x: x[0], reverse=True)
        
        top_3 = my_fits[:3]
        print(f"\n{s.id} Top 3 Available Mentors:")
        for score, m in top_3:
            print(f"  - {m.id} (Score {score:.2f}) @ Table {m.table_id}")
    print()

    # ---- Run structural diagnostics BEFORE solving ----
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
    print()

    if not diag["ok"]:
        print("Skipping MILP solve because the session is structurally infeasible.")
        return

    # ---- Run MILP solve (fit-aware) ----
    status, sol = solve_schedule(
        mentors,
        startups,
        mentor_fit,
        num_sgms=num_sgms,
    )
    print("Solver status:", status)
    print()

    if status not in ("Optimal", "Feasible"):
        print("No valid schedule – model is", status)
        return

    # ---- Pretty print schedule: SGM × Table ----
    tables = sorted({m.table_id for m in mentors})
    sgms = list(range(1, num_sgms + 1))

    for k in sgms:
        print(f"=== SGM {k} ===")
        for t in tables:
            startup_here = [
                s for (s, tt, kk), v in sol.items()
                if v == 1 and tt == t and kk == k
            ]
            label = startup_here[0] if startup_here else "-"
            print(f"Table {t}: {label}")
        print()

    print("=== VERIFICATION: OS BEFORE OC ===")
    # Extract meeting times for each startup
    startup_schedule = {s.id: {} for s in startups}
    for (s_id, t_id, k), v in sol.items():
        if v == 1:
            # Find what role this table plays for this startup
            # We need to know if t_id is the OS table or OC table for s_id
            role = "Other"
            if t_id == table_os.get(s_id):
                role = "OS"
            elif t_id == table_oc.get(s_id):
                role = "OC"
            
            startup_schedule[s_id][role] = k

    for s in startups:
        sched = startup_schedule[s.id]
        os_sgm = sched.get("OS")
        oc_sgm = sched.get("OC")
        
        if os_sgm is not None and oc_sgm is not None:
            status = "PASS" if os_sgm < oc_sgm else "FAIL"
            print(f"{s.id}: OS at SGM {os_sgm}, OC at SGM {oc_sgm} -> {status}")
        else:
            print(f"{s.id}: Missing OS or OC meeting (OS={os_sgm}, OC={oc_sgm})")
    print()


if __name__ == "__main__":
    main()

