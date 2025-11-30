# run_toy.py

import pandas as pd

from cdl_matching.config import NUM_STARTUPS_DEFAULT
from cdl_matching.data_generation.toy_dataset import make_toy_dataset
from cdl_matching.scheduling.solve import solve_schedule, _build_table_fit
from cdl_matching.scheduling.diagnostics import analyze_session_feasibility
from cdl_matching.scheduling.sets_and_params import build_sets_and_params


def main():
    # ---- Session settings ----
    num_tables = 10
    num_sgms = 3

    # ---- Generate toy mentors + startups + fit scores ----
    mentors, startups, mentor_fit = make_toy_dataset(
        num_tables=num_tables,
        num_startups=NUM_STARTUPS_DEFAULT,
        mentors_per_table=3,
        num_mentors_pool=35,  # global pool; extra mentors conceptually unused
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
    print("=== OS / OC TABLES PER STARTUP ===")
    for s in sorted(S):
        print(f"{s}: OS table={table_os[s]}, OC table={table_oc[s]}")
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


if __name__ == "__main__":
    main()
