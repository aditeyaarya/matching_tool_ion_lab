# cdl_matching/scheduling/solve.py
from __future__ import annotations

from typing import List, Tuple, Dict

import pulp

from ..models import Mentor, Startup
from .sets_and_params import build_sets_and_params
from .milp_model import build_milp_schedule_model


def solve_schedule(
    mentors: List[Mentor],
    startups: List[Startup],
    num_sgms: int = 3,
) -> Tuple[str, Dict[Tuple[str, int, int], int]]:
    """
    Build sets from mentors/startups, create MILP, solve it, and return:

        status, sol

    where:
      - status is one of "Optimal", "Feasible", "Infeasible", etc.
      - sol is a dict mapping (s, t, k) -> 1 for all assigned meetings.
        (Entries with 0 are omitted.)
    """
    # 1) Translate mentors/startups → sets and OS/OC mappings
    S, T, table_os, table_oc = build_sets_and_params(mentors, startups)

    # 2) Build MILP
    prob, x = build_milp_schedule_model(S, T, table_os, table_oc, num_sgms=num_sgms)

    # 3) Solve
    # You can set msg=True to see solver output if you want
    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)

    status = pulp.LpStatus[prob.status]

    sol: Dict[Tuple[str, int, int], int] = {}
    if status in ("Optimal", "Feasible"):
        for key, var in x.items():
            val = var.varValue
            if val is not None and val > 0.5:
                sol[key] = 1

    return status, sol
