import pandas as pd

from cdl_matching.models import Mentor, Startup
from cdl_matching.scheduling.joint_milp import solve_joint_schedule
from cdl_matching.scheduling.post_solve_export import export_post_solve_csvs

FIT_PATH = "cdl_matching/data/final_fit_scores_session_2.csv"  # put this file in repo root OR update path


def load_fit_matrix(path: str):
    df = pd.read_csv(path)

    startup_ids = df["startup_id"].tolist()
    mentor_ids = [c for c in df.columns if c != "startup_id"]

    # Build mentors/startups
    mentors = [Mentor(id=m_id, name=m_id, can_be_os=True, can_be_oc=True) for m_id in mentor_ids]
    startups = [Startup(id=s_id, name=s_id) for s_id in startup_ids]

    # Build mentor_fit dict
    mentor_fit = {}
    for _, row in df.iterrows():
        s_id = row["startup_id"]
        for m_id in mentor_ids:
            mentor_fit[(s_id, m_id)] = float(row[m_id])

    return mentors, startups, mentor_fit


def main():
    mentors, startups, mentor_fit = load_fit_matrix(FIT_PATH)

    # IMPORTANT:
    # num_tables must be >= number of startups per SGM (since 1 startup per table per SGM)
    num_tables = len(startups)

    status, schedule, os_assign, oc_assign, mentor_table_assign, os_sgm, oc_sgm = solve_joint_schedule(
        mentors=mentors,
        startups=startups,
        mentor_fit=mentor_fit,
        num_tables=num_tables,
        num_sgms=3,
        min_mentors_per_table=2,
        max_mentors_per_table=5,
        soft_max_preferred=3,
        soft_max_usual=4,
        penalty_over_3=10.0,
        penalty_over_4=50.0,
    )

    print("Solver status:", status)

    # IMPORTANT FIX:
    # CBC can stop on time limit without finding ANY feasible integer solution.
    # That is NOT "Infeasible" — it's just "Not Solved".
    if status == "Infeasible":
        raise RuntimeError("Infeasible: constraints truly conflict for this data.")
    if status in ("Not Solved", "Undefined"):
        raise RuntimeError(
            "Not Solved: solver hit time limit (or stopped) before finding ANY feasible solution. "
            "Increase time / simplify model."
        )
    if status == "Unbounded":
        raise RuntimeError("Unbounded: objective can increase without limit (likely missing constraints).")

    paths = export_post_solve_csvs(
        mentors=mentors,
        startups=startups,
        schedule=schedule,
        os_assign=os_assign,
        oc_assign=oc_assign,
        mentor_table_assign=mentor_table_assign,
        os_sgm=os_sgm,
        oc_sgm=oc_sgm,
        out_dir="data/outputs",
        prefix="joint_milp",
    )

    print("Wrote CSVs:")
    for k, v in paths.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
