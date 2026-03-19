import pandas as pd

from cdl_matching.models import Mentor, Startup
from cdl_matching.scheduling.joint_milp import solve_joint_schedule
from cdl_matching.scheduling.post_solve_export import export_post_solve_csvs

FIT_PATH = "cdl_matching/input_data/S3_final_fit_shift2.csv"  # put this file in repo root OR update path

# Exclude mentors from being considered for OS/OC roles.
# - Use mentor IDs exactly as they appear in the FIT CSV columns.
# - If None or [] -> no exclusions (everyone eligible).
EXCLUDE_FROM_OS_OC = ["MENTOR_015","MENTOR_016","MENTOR_017","MENTOR_018","MENTOR_019"]
# Example:
# EXCLUDE_FROM_OS_OC = ["mentor_12", "mentor_99"]

# Exclude mentors from the algorithm entirely:
# - They will NOT be considered for OS/OC
# - They will NOT be assigned to ANY table
# - They are fully removed from the optimization instance
EXCLUDE_FROM_ALGO = ["MENTOR_013"]
# Example:
# EXCLUDE_FROM_ALGO = ["mentor_12", "mentor_99"]
# ============================================================


def load_fit_matrix(path: str, exclude_from_os_oc=None, exclude_from_algo=None):
    df = pd.read_csv(path)

    startup_ids = df["startup_id"].tolist()
    mentor_ids = [c for c in df.columns if c != "startup_id"]

    excluded_osoc = set(exclude_from_os_oc or [])
    excluded_algo = set(exclude_from_algo or [])

    # Remove excluded mentors entirely from the instance
    mentor_ids_kept = [m_id for m_id in mentor_ids if m_id not in excluded_algo]

    # Build mentors/startups (only kept mentors exist)
    mentors = [
        Mentor(
            id=m_id,
            name=m_id,
            can_be_os=(m_id not in excluded_osoc),
            can_be_oc=(m_id not in excluded_osoc),
        )
        for m_id in mentor_ids_kept
    ]
    startups = [Startup(id=s_id, name=s_id) for s_id in startup_ids]

    # Build mentor_fit dict (only for kept mentors)
    mentor_fit = {}
    for _, row in df.iterrows():
        s_id = row["startup_id"]
        for m_id in mentor_ids_kept:
            mentor_fit[(s_id, m_id)] = float(row[m_id])

    return mentors, startups, mentor_fit


def main():
    mentors, startups, mentor_fit = load_fit_matrix(
        FIT_PATH,
        exclude_from_os_oc=EXCLUDE_FROM_OS_OC,
        exclude_from_algo=EXCLUDE_FROM_ALGO,
    )

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
        mentor_fit=mentor_fit,
        out_dir="data/outputs",
        prefix="S3-s2_joint_milp",
    )

    print("Wrote CSVs:")
    for k, v in paths.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
