# cdl_matching/scheduling/milp_model.py
from __future__ import annotations

from typing import Set, Dict, Tuple
import pulp


def build_milp_schedule_model(
    S: Set[str],
    T: Set[int],
    table_os: Dict[str, int],
    table_oc: Dict[str, int],
    num_sgms: int = 3,
) -> Tuple[pulp.LpProblem, Dict[Tuple[str, int, int], pulp.LpVariable]]:
    """
    MILP for scheduling startups over SGMs with OS-before-OC.

    Variables:
        x[s, t, k] = 1 if startup s is at table t in SGM k.

    Rules encoded:

      1) Each startup attends exactly 1 table in each SGM:
           ∀s, ∀k: sum_t x[s,t,k] = 1

      2) At most 1 startup per table per SGM:
           ∀t, ∀k: sum_s x[s,t,k] ≤ 1

      3) Exactly 1 OS meeting at its OS table:
           ∀s: sum_k x[s, table_os[s], k] = 1

      4) Exactly 1 OC meeting at its OC table:
           ∀s: sum_k x[s, table_oc[s], k] = 1

      5) OS allowed only in SGM1 or SGM2 (not SGM3):
           ∀s, k ∉ {1,2}: x[s, table_os[s], k] = 0

      6) OC allowed only in SGM2 or SGM3 (not SGM1):
           ∀s, k ∉ {2,3}: x[s, table_oc[s], k] = 0

      7) OS must be strictly before OC in SGM index.
         Given allowed SGMs, the only forbidden pattern is:
           OS in SGM2 AND OC in SGM2.
         So we enforce:
           ∀s: x[s, table_os[s], 2] + x[s, table_oc[s], 2] ≤ 1

      (Optional) You *could* add: no startup meets the same table twice:
           ∀s,t: sum_k x[s,t,k] ≤ 1
         but I'm NOT adding that now, because you didn't require it
         and it would make things stricter.
    """

    # ---------- Sets ----------
    sgms = list(range(1, num_sgms + 1))

    # ---------- Problem ----------
    prob = pulp.LpProblem("CDL_SGM_Scheduling", pulp.LpMinimize)

    # ---------- Decision variables ----------
    x: Dict[Tuple[str, int, int], pulp.LpVariable] = {}
    for s in S:
        for t in T:
            for k in sgms:
                x[(s, t, k)] = pulp.LpVariable(
                    f"x_{s}_{t}_{k}", lowBound=0, upBound=1, cat="Binary"
                )

    # ---------- Objective ----------
    # For now: pure feasibility model (no scores), so minimize 0.
    prob += 0, "DummyObjective"

    # ---------- Constraints ----------

    # (1) Exactly one table per SGM per startup
    for s in S:
        for k in sgms:
            prob += (
                pulp.lpSum(x[(s, t, k)] for t in T) == 1,
                f"OneTablePerSGM_s_{s}_k_{k}",
            )

    # (2) At most one startup per table per SGM
    for t in T:
        for k in sgms:
            prob += (
                pulp.lpSum(x[(s, t, k)] for s in S) <= 1,
                f"TableCapacity_t_{t}_k_{k}",
            )

    # (3) Exactly one OS meeting at OS table for each startup
    for s in S:
        os_table = table_os[s]
        prob += (
            pulp.lpSum(x[(s, os_table, k)] for k in sgms) == 1,
            f"OS_once_s_{s}",
        )

    # (4) Exactly one OC meeting at OC table for each startup
    for s in S:
        oc_table = table_oc[s]
        prob += (
            pulp.lpSum(x[(s, oc_table, k)] for k in sgms) == 1,
            f"OC_once_s_{s}",
        )

    # (5) OS allowed only in SGM1 or SGM2   (k != 1,2 → x=0 at OS table)
    for s in S:
        os_table = table_os[s]
        for k in sgms:
            if k not in (1, 2):
                prob += (
                    x[(s, os_table, k)] == 0,
                    f"OS_not_allowed_s_{s}_k_{k}",
                )

    # (6) OC allowed only in SGM2 or SGM3   (k != 2,3 → x=0 at OC table)
    for s in S:
        oc_table = table_oc[s]
        for k in sgms:
            if k not in (2, 3):
                prob += (
                    x[(s, oc_table, k)] == 0,
                    f"OC_not_allowed_s_{s}_k_{k}",
                )

    # (7) OS strictly before OC: forbid OS=2 & OC=2
    #     (given OS∈{1,2} and OC∈{2,3}, this is the only bad combo)
    if num_sgms >= 2:
        for s in S:
            os_table = table_os[s]
            oc_table = table_oc[s]
            prob += (
                x[(s, os_table, 2)] + x[(s, oc_table, 2)] <= 1,
                f"OS_before_OC_s_{s}",
            )

    return prob, x
