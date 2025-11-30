# run_interactive.py

from __future__ import annotations

import random

from cdl_matching.scheduling.interactive_repair import interactive_build_session
from cdl_matching.scheduling.solve import solve_schedule
from cdl_matching.scheduling.diagnostics import analyze_session_feasibility


def main():
    # 1) Build a session interactively (mentors + startups)
    mentors, startups = interactive_build_session()

    # Basic summary
    tables = sorted({m.table_id for m in mentors})
    num_tables = len(tables)
    num_startups = len(startups)

    # Precompute: table -> mentors at that table (by ID; change to .name if you prefer)
    table_to_mentors = {}
    for m in mentors:
        table_to_mentors.setdefault(m.table_id, []).append(m.name)
    # sort mentors per table for nicer output
    for t in table_to_mentors:
        table_to_mentors[t].sort()

    print("\n========== SESSION SUMMARY ==========")
    print(f"- Number of tables   : {num_tables}")
    print(f"- Number of startups : {num_startups}")

    # 1b) Build random mentor–startup fit scores in [0, 1]
    # Key: (startup_id, mentor_id) -> float
    rng = random.Random(42)  # fixed seed for reproducibility; change/remove if you want
    mentor_fit = {}
    for st in startups:
        for m in mentors:
            mentor_fit[(st.id, m.id)] = rng.random()

    # 2) Final structural check BEFORE running the MILP
    print("\n=== FINAL STRUCTURAL CHECK ===")
    diags = analyze_session_feasibility(
        mentors,
        startups,
        num_sgms=3,
        os_sgms_allowed=(1, 2),
        oc_sgms_allowed=(2, 3),
    )

    # Print detailed diagnostics if any
    if diags["messages"]:
        print("\n=== DIAGNOSTICS ===")
        for msg in diags["messages"]:
            print("-", msg)

    # Always show the implied minimum tables required from OS/OC capacity
    print(
        f"\n- Minimum tables required from OS capacity: "
        f"{diags['min_tables_from_os']}"
    )
    print(
        f"- Minimum tables required from OC capacity: "
        f"{diags['min_tables_from_oc']}"
    )

    print("\nSuggestion:", diags["suggestion"])

    # If structurally infeasible, do NOT run the MILP
    if not diags["ok"]:
        print(
            "\nResult: Session is structurally infeasible "
            "before even building the MILP."
        )
        print("Please adjust: add tables / reduce startups / change OS/OC assignments.")
        return

    # 3) If structurally OK, run the MILP solver (fit-aware)
    status, sol = solve_schedule(
        mentors,
        startups,
        mentor_fit,
        num_sgms=3,
    )
    print("\nSolver status:", status)

    if status not in ("Optimal", "Feasible"):
        print("No valid schedule – model is", status)
        return

    # 4) Pretty-print schedule per SGM/table, WITH mentors
    sgms = [1, 2, 3]

    for k in sgms:
        print(f"\n=== SGM {k} ===")
        for t in tables:
            startup_here = [
                s for (s, tt, kk), v in sol.items()
                if v == 1 and tt == t and kk == k
            ]
            label = startup_here[0] if startup_here else "-"
            mentors_here = ", ".join(table_to_mentors.get(t, [])) or "–"
            print(f"Table {t} [{mentors_here}]: {label}")


if __name__ == "__main__":
    main()
