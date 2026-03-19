# file: cdl_matching/scheduling/post_solve_export.py

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple, Optional
import csv

from cdl_matching.models import Mentor, Startup


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def export_post_solve_csvs(
    *,
    mentors: List[Mentor],
    startups: List[Startup],
    # from solve_joint_schedule(...)
    schedule: Dict[Tuple[str, int, int], int],          # (startup_id, table_id, sgm) -> 1
    os_assign: Dict[str, str],                           # startup_id -> mentor_id
    oc_assign: Dict[str, str],                           # startup_id -> mentor_id
    mentor_table_assign: Dict[str, int],                 # mentor_id -> table_id
    os_sgm: Optional[Dict[str, int]] = None,             # startup_id -> sgm (optional but recommended)
    oc_sgm: Optional[Dict[str, int]] = None,             # startup_id -> sgm (optional but recommended)
    # NEW: fit scores (same structure as in joint_milp.py)
    mentor_fit: Optional[Dict[Tuple[str, str], float]] = None,  # (startup_id, mentor_id) -> score
    out_dir: str = "outputs",
    prefix: str = "results",
) -> Dict[str, str]:
    """
    Exports 3 CSVs:

    1) {prefix}_S3_S1-startup_os_oc.csv
       - OS/OC per startup, with mentor names, tables, SGMs (if provided),
         and OS/OC fit scores (if mentor_fit provided)

    2) {prefix}_S3_S1-tables_mentors.csv
       - Table -> mentors assigned to that table (one row per table, with a mentor list)

    3) {prefix}_S3_S1-full_schedule.csv
       - A combined, human-readable schedule:
           * For each SGM + table: which startup is seated there (if any),
             which mentors are at that table,
             whether OS/OC happens there (and with whom) for that startup.

    Returns a dict of file labels -> file paths.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    mentor_by_id: Dict[str, Mentor] = {m.id: m for m in mentors}
    startup_by_id: Dict[str, Startup] = {s.id: s for s in startups}

    # -----------------------------
    # Helpers
    # -----------------------------
    def mentor_name(m_id: Optional[str]) -> str:
        if not m_id:
            return ""
        m = mentor_by_id.get(m_id)
        return m.name if m and getattr(m, "name", None) else m_id

    def startup_name(s_id: Optional[str]) -> str:
        if not s_id:
            return ""
        s = startup_by_id.get(s_id)
        return s.name if s and getattr(s, "name", None) else s_id

    def table_of_mentor(m_id: Optional[str]) -> Optional[int]:
        if not m_id:
            return None
        t = mentor_table_assign.get(m_id)
        return int(t) if t is not None else None

    def fit_score(s_id: str, m_id: Optional[str]) -> str:
        """
        Returns score as string for CSV stability.
        Blank if mentor_fit not provided or missing key.
        """
        if not mentor_fit or not m_id:
            return ""
        v = mentor_fit.get((s_id, m_id))
        return "" if v is None else f"{float(v):.6f}"

    # Build table -> mentors list
    table_to_mentors: Dict[int, List[str]] = {}
    for m_id, t in mentor_table_assign.items():
        table_to_mentors.setdefault(int(t), []).append(m_id)
    for t in table_to_mentors:
        table_to_mentors[t] = sorted(table_to_mentors[t])

    # Infer table universe from assignments and schedule (robust)
    all_tables = set(table_to_mentors.keys())
    all_tables |= {int(t) for (_, t, _), v in schedule.items() if v == 1}

    # Infer SGM universe from schedule (fallback to {1,2,3} if empty)
    all_sgms = sorted({int(k) for (_, _, k), v in schedule.items() if v == 1} or [1, 2, 3])

    # Precompute seating map for O(1) lookup: (table_id, sgm) -> startup_id
    seat_map: Dict[Tuple[int, int], str] = {
        (int(t), int(k)): s_id
        for (s_id, t, k), v in schedule.items()
        if v == 1
    }

    def seated_startup_at(table_id: int, sgm: int) -> Optional[str]:
        return seat_map.get((int(table_id), int(sgm)))

    def os_mentor_for_startup(s_id: str) -> str:
        # Prefer dict outputs from solver; fallback to Startup object if present
        return (
            os_assign.get(s_id)
            or getattr(startup_by_id.get(s_id), "os_id", None)
            or ""
        )

    def oc_mentor_for_startup(s_id: str) -> str:
        return (
            oc_assign.get(s_id)
            or getattr(startup_by_id.get(s_id), "oc_id", None)
            or ""
        )

    # -----------------------------
    # 1) Startup OS/OC CSV (+ scores)
    # -----------------------------
    f1 = out_path / f"{prefix}_startup_os_oc.csv"
    _ensure_dir(f1)

    with f1.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(
            fp,
            fieldnames=[
                "startup_id",
                "startup_name",
                "os_mentor_id",
                "os_mentor_name",
                "os_table_id",
                "os_sgm",
                "os_fit_score",
                "oc_mentor_id",
                "oc_mentor_name",
                "oc_table_id",
                "oc_sgm",
                "oc_fit_score",
                "total_os_oc_fit_score",
            ],
        )
        w.writeheader()

        for st in startups:
            s_id = st.id
            os_m = os_mentor_for_startup(s_id)
            oc_m = oc_mentor_for_startup(s_id)

            os_score_str = fit_score(s_id, os_m)
            oc_score_str = fit_score(s_id, oc_m)

            total_score = ""
            if os_score_str != "" or oc_score_str != "":
                # treat missing as 0.0 if one side is missing but mentor_fit is present
                os_v = float(os_score_str) if os_score_str != "" else 0.0
                oc_v = float(oc_score_str) if oc_score_str != "" else 0.0
                total_score = f"{(os_v + oc_v):.6f}"

            w.writerow(
                {
                    "startup_id": s_id,
                    "startup_name": startup_name(s_id),
                    "os_mentor_id": os_m or "",
                    "os_mentor_name": mentor_name(os_m),
                    "os_table_id": table_of_mentor(os_m) if os_m else "",
                    "os_sgm": (os_sgm.get(s_id) if os_sgm else "") or "",
                    "os_fit_score": os_score_str,
                    "oc_mentor_id": oc_m or "",
                    "oc_mentor_name": mentor_name(oc_m),
                    "oc_table_id": table_of_mentor(oc_m) if oc_m else "",
                    "oc_sgm": (oc_sgm.get(s_id) if oc_sgm else "") or "",
                    "oc_fit_score": oc_score_str,
                    "total_os_oc_fit_score": total_score,
                }
            )

    # -----------------------------
    # 2) Table -> mentors CSV
    # -----------------------------
    f2 = out_path / f"{prefix}_tables_mentors.csv"
    _ensure_dir(f2)

    with f2.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(
            fp,
            fieldnames=[
                "table_id",
                "num_mentors",
                "mentor_ids",
                "mentor_names",
            ],
        )
        w.writeheader()

        for t in sorted(all_tables):
            m_ids = table_to_mentors.get(int(t), [])
            m_names = [mentor_name(mid) for mid in m_ids]
            w.writerow(
                {
                    "table_id": int(t),
                    "num_mentors": len(m_ids),
                    "mentor_ids": " | ".join(m_ids),
                    "mentor_names": " | ".join(m_names),
                }
            )

    # -----------------------------
    # 3) Full combined schedule CSV
    # -----------------------------
    # One row per (sgm, table)
    # Includes: seated startup, mentors at table, and whether OS/OC happens there for that startup.
    f3 = out_path / f"{prefix}_full_schedule.csv"
    _ensure_dir(f3)

    with f3.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(
            fp,
            fieldnames=[
                "sgm",
                "table_id",
                "startup_id",
                "startup_name",
                "mentor_ids_at_table",
                "mentor_names_at_table",
                "os_happens_here",
                "os_mentor_id",
                "os_mentor_name",
                "oc_happens_here",
                "oc_mentor_id",
                "oc_mentor_name",
            ],
        )
        w.writeheader()

        for k in all_sgms:
            for t in sorted(all_tables):
                s_id = seated_startup_at(int(t), int(k))

                m_ids = table_to_mentors.get(int(t), [])
                m_names = [mentor_name(mid) for mid in m_ids]

                os_here = False
                oc_here = False
                os_m = ""
                oc_m = ""

                if s_id:
                    os_m = os_mentor_for_startup(s_id)
                    oc_m = oc_mentor_for_startup(s_id)

                    if os_m and os_sgm:
                        os_t = table_of_mentor(os_m)
                        os_k = os_sgm.get(s_id)
                        os_here = (os_t == int(t)) and (os_k == int(k)) if (os_t is not None and os_k is not None) else False

                    if oc_m and oc_sgm:
                        oc_t = table_of_mentor(oc_m)
                        oc_k = oc_sgm.get(s_id)
                        oc_here = (oc_t == int(t)) and (oc_k == int(k)) if (oc_t is not None and oc_k is not None) else False

                w.writerow(
                    {
                        "sgm": int(k),
                        "table_id": int(t),
                        "startup_id": s_id or "",
                        "startup_name": startup_name(s_id) if s_id else "",
                        "mentor_ids_at_table": " | ".join(m_ids),
                        "mentor_names_at_table": " | ".join(m_names),
                        "os_happens_here": int(os_here),
                        "os_mentor_id": os_m if os_here else "",
                        "os_mentor_name": mentor_name(os_m) if os_here else "",
                        "oc_happens_here": int(oc_here),
                        "oc_mentor_id": oc_m if oc_here else "",
                        "oc_mentor_name": mentor_name(oc_m) if oc_here else "",
                    }
                )

    return {
        "startup_os_oc": str(f1),
        "tables_mentors": str(f2),
        "full_schedule": str(f3),
    }
