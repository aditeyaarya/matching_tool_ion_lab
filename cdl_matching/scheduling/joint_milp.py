# file: cdl_matching/scheduling/joint_milp.py

from __future__ import annotations

from typing import List, Dict, Tuple
import pulp

from cdl_matching.models import Mentor, Startup
from cdl_matching.config import MAX_OS_PER_MENTOR, MAX_OC_PER_MENTOR


def solve_joint_schedule(
    mentors: List[Mentor],
    startups: List[Startup],
    mentor_fit: Dict[Tuple[str, str], float],
    num_sgms: int = 3,
):
    """
    Joint MILP:
      - chooses OS and OC mentors for each startup
      - chooses in which SGM (time slot) those meetings happen
      - schedules ALL SGM table occupancy
      - maximizes total OS+OC fit.

    Rules implemented:
      - OS can be in SGM 1 OR 2.
      - OC can be in SGM 2 OR 3.
      - OS must be BEFORE OC:
            allowed combos: (OS1,OC2), (OS1,OC3), (OS2,OC3)
            forbidden:       (OS2,OC2)
      - Each startup has exactly:
            * 1 OS meeting (mentor + SGM)
            * 1 OC meeting (mentor + SGM)
      - OS and OC must be with DIFFERENT mentors AND on DIFFERENT tables.
      - Each startup sits at exactly ONE table per SGM.
      - Each table hosts at most ONE startup per SGM.
      - Each startup visits any given table at most once in the whole day.
      - Mentor caps: MAX_OS_PER_MENTOR / MAX_OC_PER_MENTOR.
      - No hard domain filters; compatibility is encoded in fit scores.
    """

    assert num_sgms == 3, "This formulation assumes exactly 3 SGMs (1,2,3)."

    S_ids = [st.id for st in startups]
    M_ids = [m.id for m in mentors]
    T_ids = sorted({m.table_id for m in mentors})
    K = [1, 2, 3]

    # Helper: table of each mentor
    mentor_by_id: Dict[str, Mentor] = {m.id: m for m in mentors}
    mentor_table: Dict[str, int] = {m.id: m.table_id for m in mentors}

    # OS/OC allowed SGMs
    OS_SGMS = [1, 2]
    OC_SGMS = [2, 3]

    # ---------- Problem ----------
    prob = pulp.LpProblem("CDL_Joint_OS_OC_Scheduling", pulp.LpMaximize)

    # ---------- Decision variables ----------

    # x[s, t, k] = 1 if startup s is at table t in SGM k
    x: Dict[Tuple[str, int, int], pulp.LpVariable] = {}
    for s_id in S_ids:
        for t in T_ids:
            for k in K:
                x[(s_id, t, k)] = pulp.LpVariable(
                    f"x_{s_id}_{t}_{k}", lowBound=0, upBound=1, cat="Binary"
                )

    # w_os[s, m, k] = 1 if startup s meets mentor m AS OS in SGM k (k in {1,2})
    w_os: Dict[Tuple[str, str, int], pulp.LpVariable] = {}
    for s_id in S_ids:
        for m_id in M_ids:
            for k in OS_SGMS:
                w_os[(s_id, m_id, k)] = pulp.LpVariable(
                    f"wOS_{s_id}_{m_id}_{k}", lowBound=0, upBound=1, cat="Binary"
                )

    # w_oc[s, m, k] = 1 if startup s meets mentor m AS OC in SGM k (k in {2,3})
    w_oc: Dict[Tuple[str, str, int], pulp.LpVariable] = {}
    for s_id in S_ids:
        for m_id in M_ids:
            for k in OC_SGMS:
                w_oc[(s_id, m_id, k)] = pulp.LpVariable(
                    f"wOC_{s_id}_{m_id}_{k}", lowBound=0, upBound=1, cat="Binary"
                )

    # ---------- Objective: maximize OS+OC fit ----------
    prob += pulp.lpSum(
        mentor_fit.get((s_id, m_id), 0.0)
        * (
            pulp.lpSum(w_os[(s_id, m_id, k)] for k in OS_SGMS)
            + pulp.lpSum(w_oc[(s_id, m_id, k)] for k in OC_SGMS)
        )
        for s_id in S_ids
        for m_id in M_ids
    ), "Maximize_OS_OC_Fit"

    # ---------- Constraints ----------

    # 1) Seating: one table per SGM per startup
    for s_id in S_ids:
        for k in K:
            prob += (
                pulp.lpSum(x[(s_id, t, k)] for t in T_ids) == 1,
                f"One_table_per_SGM_{s_id}_k{k}",
            )

    # 2) Table capacity: at most one startup per table per SGM
    for t in T_ids:
        for k in K:
            prob += (
                pulp.lpSum(x[(s_id, t, k)] for s_id in S_ids) <= 1,
                f"Table_capacity_t{t}_k{k}",
            )

    # 3) Each startup visits each table at most once in the day
    for s_id in S_ids:
        for t in T_ids:
            prob += (
                pulp.lpSum(x[(s_id, t, k)] for k in K) <= 1,
                f"At_most_one_visit_{s_id}_t{t}",
            )

    # 4) Link OS meetings to seating:
    #    If w_os[s,m,k] = 1 then s must be at mentor m's table in SGM k.
    for s_id in S_ids:
        for m_id in M_ids:
            t_m = mentor_table[m_id]
            m = mentor_by_id[m_id]

            for k in OS_SGMS:
                # If mentor cannot be OS, disable all w_os for them
                if not m.can_be_os:
                    prob += (
                        w_os[(s_id, m_id, k)] == 0,
                        f"OS_ineligible_{s_id}_{m_id}_{k}",
                    )
                else:
                    prob += (
                        w_os[(s_id, m_id, k)] <= x[(s_id, t_m, k)],
                        f"Link_OS_{s_id}_{m_id}_{k}",
                    )

    # 5) Link OC meetings to seating:
    for s_id in S_ids:
        for m_id in M_ids:
            t_m = mentor_table[m_id]
            m = mentor_by_id[m_id]

            for k in OC_SGMS:
                if not m.can_be_oc:
                    prob += (
                        w_oc[(s_id, m_id, k)] == 0,
                        f"OC_ineligible_{s_id}_{m_id}_{k}",
                    )
                else:
                    prob += (
                        w_oc[(s_id, m_id, k)] <= x[(s_id, t_m, k)],
                        f"Link_OC_{s_id}_{m_id}_{k}",
                    )

    # 6) Exactly one OS and one OC meeting per startup
    for s_id in S_ids:
        prob += (
            pulp.lpSum(w_os[(s_id, m_id, k)] for m_id in M_ids for k in OS_SGMS) == 1,
            f"One_OS_meeting_{s_id}",
        )
        prob += (
            pulp.lpSum(w_oc[(s_id, m_id, k)] for m_id in M_ids for k in OC_SGMS) == 1,
            f"One_OC_meeting_{s_id}",
        )

    # 7) Same mentor cannot be both OS and OC for a startup
    for s_id in S_ids:
        for m_id in M_ids:
            prob += (
                pulp.lpSum(w_os[(s_id, m_id, k)] for k in OS_SGMS)
                + pulp.lpSum(w_oc[(s_id, m_id, k)] for k in OC_SGMS)
                <= 1,
                f"OS_OC_not_same_mentor_{s_id}_{m_id}",
            )

    # 8) Mentor OS/OC caps
    for m_id in M_ids:
        prob += (
            pulp.lpSum(w_os[(s_id, m_id, k)] for s_id in S_ids for k in OS_SGMS)
            <= MAX_OS_PER_MENTOR,
            f"Mentor_OS_cap_{m_id}",
        )
        prob += (
            pulp.lpSum(w_oc[(s_id, m_id, k)] for s_id in S_ids for k in OC_SGMS)
            <= MAX_OC_PER_MENTOR,
            f"Mentor_OC_cap_{m_id}",
        )

    # 9) OS-before-OC constraint:
    #    If OC happens in SGM2, OS MUST be in SGM1.
    #    sum_m w_oc[s,m,2] <= sum_m w_os[s,m,1]
    for s_id in S_ids:
        prob += (
            pulp.lpSum(w_oc[(s_id, m_id, 2)] for m_id in M_ids)
            <= pulp.lpSum(w_os[(s_id, m_id, 1)] for m_id in M_ids),
            f"OS_before_OC_for_{s_id}",
        )

    # 10) OS and OC on different TABLES
    for s_id in S_ids:
        for t in T_ids:
            # OS on table t: any mentor on t, any OS SGM
            os_on_t = pulp.lpSum(
                w_os[(s_id, m_id, k)]
                for m_id in M_ids
                if mentor_table[m_id] == t
                for k in OS_SGMS
            )
            # OC on table t: any mentor on t, any OC SGM
            oc_on_t = pulp.lpSum(
                w_oc[(s_id, m_id, k)]
                for m_id in M_ids
                if mentor_table[m_id] == t
                for k in OC_SGMS
            )

            prob += (
                os_on_t + oc_on_t <= 1,
                f"OS_OC_different_tables_{s_id}_t{t}",
            )

    # ---------- Solve ----------
    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    status = pulp.LpStatus[prob.status]

    os_assign: Dict[str, str] = {}
    oc_assign: Dict[str, str] = {}
    schedule: Dict[Tuple[str, int, int], int] = {}

    if status in ("Optimal", "Feasible"):
        # Extract full schedule x
        for s_id in S_ids:
            for t in T_ids:
                for k in K:
                    val = x[(s_id, t, k)].varValue
                    if val is not None and val > 0.5:
                        schedule[(s_id, t, k)] = 1

        # Extract OS/OC mentor choices (ignore SGM in this mapping)
        for s_id in S_ids:
            # OS mentor
            for m_id in M_ids:
                if any(
                    w_os[(s_id, m_id, k)].varValue
                    and w_os[(s_id, m_id, k)].varValue > 0.5
                    for k in OS_SGMS
                ):
                    os_assign[s_id] = m_id
                    break

            # OC mentor
            for m_id in M_ids:
                if any(
                    w_oc[(s_id, m_id, k)].varValue
                    and w_oc[(s_id, m_id, k)].varValue > 0.5
                    for k in OC_SGMS
                ):
                    oc_assign[s_id] = m_id
                    break

        # Write OS/OC back into Startup objects
        for st in startups:
            if st.id in os_assign:
                st.os_id = os_assign[st.id]
            if st.id in oc_assign:
                st.oc_id = oc_assign[st.id]

    return status, schedule, os_assign, oc_assign
