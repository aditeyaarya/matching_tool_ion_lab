# file: cdl_matching/scheduling/joint_milp.py

from __future__ import annotations

from typing import Dict, List, Tuple
import pulp

from cdl_matching.models import Mentor, Startup
from cdl_matching.config import MAX_OS_PER_MENTOR, MAX_OC_PER_MENTOR


def solve_joint_schedule(
    mentors: List[Mentor],
    startups: List[Startup],
    mentor_fit: Dict[Tuple[str, str], float],
    num_tables: int,
    num_sgms: int = 3,
    min_mentors_per_table: int = 2,
    max_mentors_per_table: int = 5,
    soft_max_preferred: int = 3,
    soft_max_usual: int = 4,
    penalty_over_3: float = 10.0,
    penalty_over_4: float = 50.0,
):
    """
    Joint MILP (dynamic tables):
      - assigns mentors to tables (NO pre-given mentor.table_id needed)
      - assigns startups to tables each SGM
      - chooses OS and OC mentors for each startup, and in which SGM those meetings occur
      - maximizes total OS+OC fit, while discouraging large mentor groups at tables

    NOTE: OS and OC being on different tables for the same startup is already enforced by:
      - F) startup visits each table at most once across the day
      - OS_SGMS = {1,2}, OC_SGMS = {2,3} and you require exactly 1 OS and 1 OC meeting
    So we do NOT introduce explicit os_table/oc_table variables (they blow up constraints).

    Returns:
      status: str
      schedule: Dict[(startup_id, table_id, sgm), 1]
      os_assign: Dict[startup_id, mentor_id]
      oc_assign: Dict[startup_id, mentor_id]
      mentor_table_assign: Dict[mentor_id, table_id]
      os_sgm: Dict[startup_id, sgm]
      oc_sgm: Dict[startup_id, sgm]
    """

    if num_sgms != 3:
        raise ValueError("This formulation assumes exactly 3 SGMs (1,2,3).")

    if min_mentors_per_table < 2:
        raise ValueError("Minimum number of mentors per table must be at least 2.")
    if max_mentors_per_table > 5:
        raise ValueError("Maximum number of mentors per table must be at most 5.")
    if min_mentors_per_table > max_mentors_per_table:
        raise ValueError("min_mentors_per_table cannot exceed max_mentors_per_table.")
    if num_tables <= 0:
        raise ValueError("num_tables must be positive.")

    S_ids = [st.id for st in startups]
    M_ids = [m.id for m in mentors]
    T_ids = list(range(1, num_tables + 1))
    K = [1, 2, 3]

    mentor_by_id: Dict[str, Mentor] = {m.id: m for m in mentors}

    OS_SGMS = [1, 2]
    OC_SGMS = [2, 3]

    # If you have exactly as many tables as startups, the capacity constraints force
    # all tables to be used each SGM anyway. In that case, allowing "inactive tables"
    # just bloats the search.
    force_all_active = (num_tables == len(startups))

    # ---------- Problem ----------
    prob = pulp.LpProblem("CDL_Joint_OS_OC_Scheduling_DynamicTables", pulp.LpMaximize)

    # ---------- Decision variables ----------

    # a[t] = 1 if table t is active
    a: Dict[int, pulp.LpVariable] = {
        t: pulp.LpVariable(
            f"a_{t}",
            lowBound=1 if force_all_active else 0,
            upBound=1,
            cat="Binary",
        )
        for t in T_ids
    }

    # y[m,t] = 1 if mentor m sits at table t (whole day)
    y: Dict[Tuple[str, int], pulp.LpVariable] = {
        (m_id, t): pulp.LpVariable(f"y_{m_id}_{t}", lowBound=0, upBound=1, cat="Binary")
        for m_id in M_ids
        for t in T_ids
    }

    # x[s,t,k] = 1 if startup s is at table t in SGM k
    x: Dict[Tuple[str, int, int], pulp.LpVariable] = {
        (s_id, t, k): pulp.LpVariable(f"x_{s_id}_{t}_{k}", lowBound=0, upBound=1, cat="Binary")
        for s_id in S_ids
        for t in T_ids
        for k in K
    }

    # z[s,m,t,k] = 1 if startup s is at table t in SGM k AND mentor m is at table t
    z: Dict[Tuple[str, str, int, int], pulp.LpVariable] = {
        (s_id, m_id, t, k): pulp.LpVariable(
            f"z_{s_id}_{m_id}_{t}_{k}", lowBound=0, upBound=1, cat="Binary"
        )
        for s_id in S_ids
        for m_id in M_ids
        for t in T_ids
        for k in K
    }

    # w_os[s,m,k] = 1 if s meets mentor m as OS in SGM k
    w_os: Dict[Tuple[str, str, int], pulp.LpVariable] = {
        (s_id, m_id, k): pulp.LpVariable(
            f"wOS_{s_id}_{m_id}_{k}", lowBound=0, upBound=1, cat="Binary"
        )
        for s_id in S_ids
        for m_id in M_ids
        for k in OS_SGMS
    }

    # w_oc[s,m,k] = 1 if s meets mentor m as OC in SGM k
    w_oc: Dict[Tuple[str, str, int], pulp.LpVariable] = {
        (s_id, m_id, k): pulp.LpVariable(
            f"wOC_{s_id}_{m_id}_{k}", lowBound=0, upBound=1, cat="Binary"
        )
        for s_id in S_ids
        for m_id in M_ids
        for k in OC_SGMS
    }

    # mentors_at_table[t]
    mentors_at_table: Dict[int, pulp.LpVariable] = {
        t: pulp.LpVariable(f"mentorsAt_{t}", lowBound=0, upBound=len(M_ids), cat="Integer")
        for t in T_ids
    }

    # Soft penalty variables
    e3: Dict[int, pulp.LpVariable] = {
        t: pulp.LpVariable(f"excessOver3_{t}", lowBound=0, upBound=len(M_ids), cat="Integer")
        for t in T_ids
    }
    e4: Dict[int, pulp.LpVariable] = {
        t: pulp.LpVariable(f"excessOver4_{t}", lowBound=0, upBound=len(M_ids), cat="Integer")
        for t in T_ids
    }

    # ---------- Objective ----------
    fit_term = pulp.lpSum(
        mentor_fit.get((s_id, m_id), 0.0)
        * (
            pulp.lpSum(w_os[(s_id, m_id, k)] for k in OS_SGMS)
            + pulp.lpSum(w_oc[(s_id, m_id, k)] for k in OC_SGMS)
        )
        for s_id in S_ids
        for m_id in M_ids
    )
    penalty_term = pulp.lpSum(penalty_over_3 * e3[t] + penalty_over_4 * e4[t] for t in T_ids)
    prob += fit_term - penalty_term, "Maximize_Fit_With_TableSize_Penalty"

    # ---------- Constraints ----------

    # A) Each mentor assigned to exactly one table
    for m_id in M_ids:
        prob += pulp.lpSum(y[(m_id, t)] for t in T_ids) == 1, f"Mentor_one_table_{m_id}"

    # B) Define mentors_at_table
    for t in T_ids:
        prob += mentors_at_table[t] == pulp.lpSum(y[(m_id, t)] for m_id in M_ids), f"MentorsAt_def_{t}"

    # C) Table activation and min/max mentors per active table
    for t in T_ids:
        if force_all_active:
            # a[t] fixed to 1, so avoid multiplying by it (cleaner presolve)
            prob += mentors_at_table[t] <= max_mentors_per_table, f"MaxMentors_{t}"
            prob += mentors_at_table[t] >= min_mentors_per_table, f"MinMentors_{t}"
        else:
            prob += mentors_at_table[t] <= max_mentors_per_table * a[t], f"MaxMentors_ifActive_{t}"
            prob += mentors_at_table[t] >= min_mentors_per_table * a[t], f"MinMentors_ifActive_{t}"

    # Symmetry breaking only matters if tables can be inactive
    if not force_all_active:
        T_sorted = sorted(T_ids)
        for i in range(len(T_sorted) - 1):
            prob += a[T_sorted[i]] >= a[T_sorted[i + 1]], f"sym_break_active_{T_sorted[i]}_{T_sorted[i+1]}"

    # D) Seating: one table per SGM per startup
    for s_id in S_ids:
        for k in K:
            prob += pulp.lpSum(x[(s_id, t, k)] for t in T_ids) == 1, f"One_table_per_SGM_{s_id}_k{k}"

    # E) Table capacity per SGM: at most one startup per table per SGM
    for t in T_ids:
        for k in K:
            prob += pulp.lpSum(x[(s_id, t, k)] for s_id in S_ids) <= 1, f"Table_capacity_t{t}_k{k}"

    # F) Startup visits each table at most once across the day
    #    => implies OS-table != OC-table for each startup
    for s_id in S_ids:
        for t in T_ids:
            prob += pulp.lpSum(x[(s_id, t, k)] for k in K) <= 1, f"At_most_one_visit_{s_id}_t{t}"

    # G) Startups cannot sit at inactive tables
    if not force_all_active:
        for s_id in S_ids:
            for t in T_ids:
                for k in K:
                    prob += x[(s_id, t, k)] <= a[t], f"No_seat_in_inactive_{s_id}_{t}_{k}"

    # H) z linearization: z = x AND y
    for s_id in S_ids:
        for m_id in M_ids:
            for t in T_ids:
                for k in K:
                    prob += z[(s_id, m_id, t, k)] <= x[(s_id, t, k)], f"z_le_x_{s_id}_{m_id}_{t}_{k}"
                    prob += z[(s_id, m_id, t, k)] <= y[(m_id, t)], f"z_le_y_{s_id}_{m_id}_{t}_{k}"
                    prob += (
                        z[(s_id, m_id, t, k)] >= x[(s_id, t, k)] + y[(m_id, t)] - 1,
                        f"z_ge_xplusyminus1_{s_id}_{m_id}_{t}_{k}",
                    )

    # I) Eligibility + link OS/OC meetings to being seated at table where mentor is present
    for s_id in S_ids:
        for m_id in M_ids:
            m = mentor_by_id[m_id]

            for k in OS_SGMS:
                if not m.can_be_os:
                    prob += w_os[(s_id, m_id, k)] == 0, f"OS_ineligible_{s_id}_{m_id}_{k}"
                else:
                    prob += (
                        w_os[(s_id, m_id, k)]
                        <= pulp.lpSum(z[(s_id, m_id, t, k)] for t in T_ids),
                        f"Link_OS_{s_id}_{m_id}_{k}",
                    )

            for k in OC_SGMS:
                if not m.can_be_oc:
                    prob += w_oc[(s_id, m_id, k)] == 0, f"OC_ineligible_{s_id}_{m_id}_{k}"
                else:
                    prob += (
                        w_oc[(s_id, m_id, k)]
                        <= pulp.lpSum(z[(s_id, m_id, t, k)] for t in T_ids),
                        f"Link_OC_{s_id}_{m_id}_{k}",
                    )

    # J) Exactly one OS and one OC meeting per startup
    for s_id in S_ids:
        prob += pulp.lpSum(w_os[(s_id, m_id, k)] for m_id in M_ids for k in OS_SGMS) == 1, f"One_OS_{s_id}"
        prob += pulp.lpSum(w_oc[(s_id, m_id, k)] for m_id in M_ids for k in OC_SGMS) == 1, f"One_OC_{s_id}"

    # K) Same mentor cannot be both OS and OC
    for s_id in S_ids:
        for m_id in M_ids:
            prob += (
                pulp.lpSum(w_os[(s_id, m_id, k)] for k in OS_SGMS)
                + pulp.lpSum(w_oc[(s_id, m_id, k)] for k in OC_SGMS)
                <= 1,
                f"OS_OC_not_same_{s_id}_{m_id}",
            )

    # L) Mentor OS/OC caps
    for m_id in M_ids:
        prob += (
            pulp.lpSum(w_os[(s_id, m_id, k)] for s_id in S_ids for k in OS_SGMS)
            <= MAX_OS_PER_MENTOR,
            f"OS_cap_{m_id}",
        )
        prob += (
            pulp.lpSum(w_oc[(s_id, m_id, k)] for s_id in S_ids for k in OC_SGMS)
            <= MAX_OC_PER_MENTOR,
            f"OC_cap_{m_id}",
        )

    # M) OS-before-OC
    for s_id in S_ids:
        prob += (
            pulp.lpSum(w_oc[(s_id, m_id, 2)] for m_id in M_ids)
            <= pulp.lpSum(w_os[(s_id, m_id, 1)] for m_id in M_ids),
            f"OS_before_OC_{s_id}",
        )

    # O) Soft penalty constraints
    for t in T_ids:
        prob += e3[t] >= mentors_at_table[t] - soft_max_preferred, f"Excess3_{t}"
        prob += e4[t] >= mentors_at_table[t] - soft_max_usual, f"Excess4_{t}"

    # ---------- Solve ----------
    solver = pulp.PULP_CBC_CMD(
        msg=True,
        timeLimit=600,  # was 120
        threads=0,
        gapRel=0.05,    # was 0.01
    )

    print("Vars:", len(prob.variables()), "Constraints:", len(prob.constraints))
    print("M_ids:", len(M_ids), "S_ids:", len(S_ids), "T_ids:", len(T_ids), "K:", num_sgms)

    prob.solve(solver)

    status = pulp.LpStatus[prob.status]
    print("Status:", status)

    schedule: Dict[Tuple[str, int, int], int] = {}
    os_assign: Dict[str, str] = {}
    oc_assign: Dict[str, str] = {}
    mentor_table_assign: Dict[str, int] = {}
    os_sgm: Dict[str, int] = {}
    oc_sgm: Dict[str, int] = {}

    if status in ("Optimal", "Feasible"):
        # Mentor -> table
        for m_id in M_ids:
            for t in T_ids:
                val = y[(m_id, t)].varValue
                if val is not None and val > 0.5:
                    mentor_table_assign[m_id] = t
                    break

        # Seating schedule x
        for s_id in S_ids:
            for t in T_ids:
                for k in K:
                    val = x[(s_id, t, k)].varValue
                    if val is not None and val > 0.5:
                        schedule[(s_id, t, k)] = 1

        # OS / OC mentor + SGM
        for s_id in S_ids:
            # OS
            for m_id in M_ids:
                for k in OS_SGMS:
                    v = w_os[(s_id, m_id, k)].varValue
                    if v is not None and v > 0.5:
                        os_assign[s_id] = m_id
                        os_sgm[s_id] = k
                        break
                if s_id in os_assign:
                    break

            # OC
            for m_id in M_ids:
                for k in OC_SGMS:
                    v = w_oc[(s_id, m_id, k)].varValue
                    if v is not None and v > 0.5:
                        oc_assign[s_id] = m_id
                        oc_sgm[s_id] = k
                        break
                if s_id in oc_assign:
                    break

        # Write OS/OC back into Startup objects
        for st in startups:
            if st.id in os_assign:
                st.os_id = os_assign[st.id]
            if st.id in oc_assign:
                st.oc_id = oc_assign[st.id]

        # ---- Derived OS/OC tables per startup + sanity check ----
        os_table_assign: Dict[str, int] = {}
        oc_table_assign: Dict[str, int] = {}
        for s_id in S_ids:
            if s_id in os_assign:
                os_table_assign[s_id] = mentor_table_assign[os_assign[s_id]]
            if s_id in oc_assign:
                oc_table_assign[s_id] = mentor_table_assign[oc_assign[s_id]]

        # Hard sanity: OS and OC tables must differ for each startup
        for s_id in S_ids:
            if s_id in os_table_assign and s_id in oc_table_assign:
                if os_table_assign[s_id] == oc_table_assign[s_id]:
                    raise RuntimeError(
                        f"Sanity fail: startup {s_id} has OS and OC on same table {os_table_assign[s_id]} "
                        f"(this should be impossible with 'visit table at most once')."
                    )

        # ---- Print a clean objective decomposition ----
        fit_val = 0.0
        for s_id in S_ids:
            if s_id in os_assign:
                fit_val += mentor_fit.get((s_id, os_assign[s_id]), 0.0)
            if s_id in oc_assign:
                fit_val += mentor_fit.get((s_id, oc_assign[s_id]), 0.0)

        penalty_val = 0.0
        for t in T_ids:
            v3 = e3[t].varValue or 0.0
            v4 = e4[t].varValue or 0.0
            penalty_val += penalty_over_3 * v3 + penalty_over_4 * v4

        print(
            f"Objective (computed): fit={fit_val:.6f}  penalty={penalty_val:.6f}  "
            f"net={fit_val - penalty_val:.6f}"
        )

    return status, schedule, os_assign, oc_assign, mentor_table_assign, os_sgm, oc_sgm
