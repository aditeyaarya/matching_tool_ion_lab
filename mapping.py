"""
What it does
------------
- Reads the post-solve CSVs produced by export_post_solve_csvs for TWO runs (e.g., S3-s1 and S3-s2)
- Converts pseudo IDs (MENTOR_### / STARTUP_###) to original names using your JSON files:
    mentors_available.json
    startups_available.json
- Appends s1 + s2 into ONE combined CSV per output type
- Also writes a speaker mapping CSV (pseudo_id -> name, type)

IMPORTANT CHANGE (per your request)
-----------------------------------
- mentor_id / os_mentor_id / oc_mentor_id columns will KEEP displaying the pseudo IDs
- New columns mentor_name / os_mentor_name / oc_mentor_name are added alongside (if relevant)

How to run
----------
python -m mapping

You only need to edit the CONFIG section at the top.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd


# =========================
# CONFIG (EDIT THESE ONLY)
# =========================

# Folder that contains the CSVs exported by export_post_solve_csvs(...)
IN_DIR = Path("data/outputs")

# Prefixes for the two runs you want to merge
PREFIX_RUN_A = "S3-s1_joint_milp"
PREFIX_RUN_B = "S3-s2_joint_milp"

# Your mapping JSONs (uploaded / or stored in repo)
MENTORS_JSON = Path("cdl_matching/input_data/S3_mentors_available.json")
STARTUPS_JSON = Path("cdl_matching/input_data/S3_startups_available.json")

# Output directory for the merged + denormalized CSVs
OUT_DIR = Path("data/final_results")

# Output prefix for combined files
OUT_PREFIX = "S3_final_results"

# Separator used when lists of mentors are joined in CSV fields
SEP = " | "

# Which exported CSVs to merge (these are the ones export_post_solve_csvs writes)
EXPORTED_FILES = [
    "_startup_os_oc.csv",
    "_tables_mentors.csv",
    "_full_schedule.csv",
]

# If True, add a column "run" with values "S3-s1" / "S3-s2" to keep provenance
ADD_RUN_COLUMN = True


# =========================
# MAPPING LOADERS
# =========================

def load_mentor_map(path: Path) -> Dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, str] = {}
    for row in data:
        mid = str(row.get("mentor_id", "")).strip()
        name = str(row.get("mentor_name", "")).strip()
        if mid:
            out[mid] = name or mid
    return out


def load_startup_map(path: Path) -> Dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, str] = {}
    for row in data:
        sid = str(row.get("startup_id", "")).strip()
        name = str(row.get("startup_name", "")).strip()
        if sid:
            out[sid] = name or sid
    return out


def write_speaker_mapping_csv(
    out_path: Path,
    mentor_map: Dict[str, str],
    startup_map: Dict[str, str],
) -> None:
    rows = []
    for k, v in mentor_map.items():
        rows.append({"pseudo_id": k, "name": v, "type": "mentor"})
    for k, v in startup_map.items():
        rows.append({"pseudo_id": k, "name": v, "type": "startup"})
    df = pd.DataFrame(rows).sort_values(["type", "pseudo_id"]).reset_index(drop=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8")


# =========================
# DENORMALIZATION HELPERS
# =========================

def _map_scalar(x: object, mapping: Dict[str, str]) -> object:
    if pd.isna(x):
        return x
    s = str(x).strip()
    if not s:
        return x
    return mapping.get(s, s)


def _map_joined_list(x: object, mapping: Dict[str, str], sep: str = SEP) -> object:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return x
    s = str(x).strip()
    if not s:
        return s
    parts = [p.strip() for p in s.split(sep)]
    mapped = [mapping.get(p, p) for p in parts if p]
    return sep.join(mapped)


def denormalize_df(df: pd.DataFrame, mentor_map: Dict[str, str], startup_map: Dict[str, str]) -> pd.DataFrame:
    """
    Best-effort conversion:
    - startup_id / venture / startup columns: STARTUP_### -> startup_name
    - mentor_id / os/oc id columns: KEEP as IDs, add *_name columns
    - joined lists: "MENTOR_001 | MENTOR_002" -> mapped names
    - generic fallback for object columns: map pure IDs and mentor lists (but never in *_id columns)
    """
    out = df.copy()

    for col in list(out.columns):
        lc = col.lower()

        # --- startup scalar ids ---
        if lc == "startup_id":
            # Keep startup_id as-is, but you may optionally add startup_name if you want.
            # Uncomment if you want startup_name added always:
            # if "startup_name" not in out.columns:
            #     out["startup_name"] = out[col].apply(lambda v: _map_scalar(v, startup_map))
            pass

        # common places where startup ids appear (non-id label columns)
        if lc in {"startup", "venture", "venture_id"}:
            out[col] = out[col].apply(
                lambda v: _map_scalar(v, startup_map)
                if (isinstance(v, str) and v.strip().startswith("STARTUP_"))
                else v
            )

        # enforce startup_name from mapping if startup_id exists (only if startup_name already present)
        if lc == "startup_name" and "startup_id" in out.columns:
            out[col] = out["startup_id"].apply(lambda v: _map_scalar(v, startup_map))

        # --- mentor scalar ids ---
        # KEEP IDs as-is, but add name columns alongside
        if lc == "mentor_id":
            if "mentor_name" not in out.columns:
                out["mentor_name"] = out[col].apply(lambda v: _map_scalar(v, mentor_map))

        if lc == "os_mentor_id":
            if "os_mentor_name" not in out.columns:
                out["os_mentor_name"] = out[col].apply(lambda v: _map_scalar(v, mentor_map))

        if lc == "oc_mentor_id":
            if "oc_mentor_name" not in out.columns:
                out["oc_mentor_name"] = out[col].apply(lambda v: _map_scalar(v, mentor_map))

        # If name columns already exist, enforce them from the id columns (but DO NOT overwrite ids)
        if lc == "os_mentor_name" and "os_mentor_id" in out.columns:
            out[col] = out["os_mentor_id"].apply(lambda v: _map_scalar(v, mentor_map))
        if lc == "oc_mentor_name" and "oc_mentor_id" in out.columns:
            out[col] = out["oc_mentor_id"].apply(lambda v: _map_scalar(v, mentor_map))

        # --- typical joined mentor list columns ---
        if lc in {"mentor_ids", "mentor_ids_at_table", "mentor_group", "sgm1", "sgm2", "sgm3", "mentors"}:
            out[col] = out[col].apply(lambda v: _map_joined_list(v, mentor_map))

        # --- generic fallback ---
        protected = {
            "startup_id", "startup_name", "startup", "venture", "venture_id",
            "mentor_id", "mentor_name",
            "os_mentor_id", "oc_mentor_id", "os_mentor_name", "oc_mentor_name",
            "mentor_ids", "mentor_ids_at_table", "mentor_group", "sgm1", "sgm2", "sgm3", "mentors",
        }

        if out[col].dtype == "object" and lc not in protected:
            def smart(v: object) -> object:
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    return v
                if not isinstance(v, str):
                    return v
                t = v.strip()
                if not t:
                    return v

                # If this is an ID-ish column, never denormalize pure IDs.
                if lc.endswith("_id") or lc in {"mentor_id", "startup_id"}:
                    return v

                # joined mentor list
                if SEP in t and "MENTOR_" in t:
                    return _map_joined_list(t, mentor_map, SEP)

                # pure ids (non-id columns)
                if t.startswith("MENTOR_"):
                    return mentor_map.get(t, t)
                if t.startswith("STARTUP_"):
                    return startup_map.get(t, t)

                return v

            out[col] = out[col].apply(smart)

    return out


# =========================
# MERGE LOGIC
# =========================

def read_one_run_csvs(prefix: str) -> Dict[str, pd.DataFrame]:
    """
    Returns dict: suffix -> DataFrame
    for each suffix in EXPORTED_FILES.
    """
    out: Dict[str, pd.DataFrame] = {}
    for suffix in EXPORTED_FILES:
        path = IN_DIR / f"{prefix}{suffix}"
        if not path.exists():
            raise FileNotFoundError(f"Missing expected file: {path}")
        out[suffix] = pd.read_csv(path)
    return out


def add_run_label(df: pd.DataFrame, run_label: str) -> pd.DataFrame:
    if not ADD_RUN_COLUMN:
        return df
    df2 = df.copy()
    df2.insert(0, "run", run_label)
    return df2


def align_columns(dfs: List[pd.DataFrame]) -> List[pd.DataFrame]:
    """
    Make sure all dfs have the same columns in the same order (union of all columns).
    Missing columns are filled with NA.
    """
    all_cols: List[str] = []
    seen = set()
    for df in dfs:
        for c in df.columns:
            if c not in seen:
                seen.add(c)
                all_cols.append(c)
    aligned: List[pd.DataFrame] = []
    for df in dfs:
        df2 = df.copy()
        for c in all_cols:
            if c not in df2.columns:
                df2[c] = pd.NA
        df2 = df2[all_cols]
        aligned.append(df2)
    return aligned


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    mentor_map = load_mentor_map(MENTORS_JSON)
    startup_map = load_startup_map(STARTUPS_JSON)

    # Write speaker mapping once (covers both runs)
    mapping_out = OUT_DIR / f"{OUT_PREFIX}_speaker_mapping.csv"
    write_speaker_mapping_csv(mapping_out, mentor_map, startup_map)

    # Read both runs
    run_a = read_one_run_csvs(PREFIX_RUN_A)
    run_b = read_one_run_csvs(PREFIX_RUN_B)

    # Merge per suffix
    for suffix in EXPORTED_FILES:
        df_a = add_run_label(run_a[suffix], run_label="S3-s1")
        df_b = add_run_label(run_b[suffix], run_label="S3-s2")

        # Denormalize names for each run
        df_a = denormalize_df(df_a, mentor_map, startup_map)
        df_b = denormalize_df(df_b, mentor_map, startup_map)

        # Align columns and append
        df_a, df_b = align_columns([df_a, df_b])
        combined = pd.concat([df_a, df_b], ignore_index=True)

        out_path = OUT_DIR / f"{OUT_PREFIX}{suffix}"
        combined.to_csv(out_path, index=False, encoding="utf-8")

    print("✅ Done.")
    print("Output folder:", OUT_DIR.resolve())
    print("Speaker mapping:", mapping_out.resolve())
    for suffix in EXPORTED_FILES:
        print("Combined:", (OUT_DIR / f"{OUT_PREFIX}{suffix}").resolve())


if __name__ == "__main__":
    main()
