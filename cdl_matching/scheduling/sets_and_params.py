# cdl_matching/scheduling/sets_and_params.py
from __future__ import annotations
from typing import List, Dict, Set, Tuple
from ..models import Mentor, Startup


def build_sets_and_params(
    mentors: List[Mentor],
    startups: List[Startup],
) -> Tuple[Set[str], Set[int], Dict[str, int], Dict[str, int]]:
    """
    Build:
      S: set of startup IDs
      T: set of table IDs
      table_os: startup -> OS table
      table_oc: startup -> OC table
    """
    S = {st.id for st in startups}
    T = {m.table_id for m in mentors}

    # Map mentor -> table
    mentor_table: Dict[str, int] = {m.id: m.table_id for m in mentors}

    table_os: Dict[str, int] = {}
    table_oc: Dict[str, int] = {}

    for st in startups:
        if st.os_id is None or st.oc_id is None:
            raise ValueError(
                f"Startup {st.id} is missing OS or OC mentor id. "
                "Toy generator should always assign both."
            )

        if st.os_id not in mentor_table:
            raise ValueError(f"OS mentor {st.os_id} not found for startup {st.id}.")
        if st.oc_id not in mentor_table:
            raise ValueError(f"OC mentor {st.oc_id} not found for startup {st.id}.")

        table_os[st.id] = mentor_table[st.os_id]
        table_oc[st.id] = mentor_table[st.oc_id]

    return S, T, table_os, table_oc
