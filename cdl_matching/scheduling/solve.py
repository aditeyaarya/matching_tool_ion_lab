# cdl_matching/scheduling/solve.py
from __future__ import annotations

from typing import List, Tuple, Dict

import pulp

from ..models import Mentor, Startup
from .sets_and_params import build_sets_and_params
from .milp_model import build_milp_schedule_model


def _build_table_fit(
    mentors: List[Mentor],
    startups: List[Startup],
    mentor_fit: Dict[Tuple[str, str], float],
) -> Dict[Tuple[str, int], float]:
    """
    Aggregate mentor-level fit to table-level fit:
    table_fit[(startup_id, table_id)] = best mentor fit on that table.
    """
    mentors_by_table: Dict[int, List[Mentor]] = {}
    for m in mentors:
        mentors_by_table.setdefault(m.table_id, []).append(m)

    table_fit: Dict[Tuple[str, int], float] = {}

    for st in startups:
        for table_id, m_list in mentors_by_table.items():
            scores = [mentor_fit[(st.id, m.id)] for m in m_list]
            table_fit[(st.id, table_id)] = max(scores) if scores else 0.0

    return table_fit


def solve_schedule(
    mentors: List[Mentor],
    startups: List[Startup],
    mentor_fit: Dict[Tuple[str, str], float],
    num_sgms: int = 3,
) -> Tuple[str, Dict[Tuple[str, int, int], int]]:
    """
    Solve the schedule MILP and return (status, solution_dict).
    """

    # Sets and OS/OC tables from startups
    S, T, table_os, table_oc = build_sets_and_params(mentors, startups)

    # Table-level fit scores for MILP objective
    table_fit = _build_table_fit(mentors, startups, mentor_fit)

    prob, x = build_milp_schedule_model(
        S=S,
        T=T,
        table_os=table_os,
        table_oc=table_oc,
        table_fit=table_fit,
        num_sgms=num_sgms,
    )

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
