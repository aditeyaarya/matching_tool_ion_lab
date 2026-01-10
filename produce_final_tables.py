
import pandas as pd
import os
import glob

# Constants for file paths
# Constants for file paths
FIT_SCORES_PATH_S1 = "cdl_matching/data/final_fit_scores_session_1.csv"
FIT_SCORES_PATH_S2 = "cdl_matching/data/final_fit_scores_session_2.csv"
COMPARISON_REPORT_PATH = "data/outputs/comparision_os_oc/CDL_Binder_Comparison_Report.csv"
FULL_SCHEDULE_PATH = "data/outputs/joint_milp_full_schedule_session_2.csv"
STARTUP_MAPPING_PATH = "cdl_matching/data/comparision_os_oc/startup_mapping.csv"
MENTOR_MAPPING_PATH = "cdl_matching/data/comparision_os_oc/mentor_mapping.csv"
OUTPUT_DIR = "data/outputs/data_analysis_tables"

def load_mappings():
    print("Loading mappings...")
    # Load Startup Mapping: name -> id
    s_map_df = pd.read_csv(STARTUP_MAPPING_PATH)
    # Ensure columns are correct based on usage in calculate_fit_stats.py
    # "startup_name", "startup_id"
    s_map_df["startup_name"] = s_map_df["startup_name"].astype(str).str.strip()
    s_map_df["startup_id"] = s_map_df["startup_id"].astype(str).str.strip()
    # Normalize to lowercase for matching
    startup_name_to_id = dict(zip(s_map_df["startup_name"].str.lower(), s_map_df["startup_id"]))
    
    # Load Mentor Mapping: name -> id
    # From calculate_fit_stats: header=None, names=["id", "name"]
    try:
        m_map_df = pd.read_csv(MENTOR_MAPPING_PATH, header=None, names=["id", "name"])
    except pd.errors.ParserError:
        # Fallback if it has header
        m_map_df = pd.read_csv(MENTOR_MAPPING_PATH)
        
    m_map_df["name"] = m_map_df["name"].astype(str).str.strip()
    m_map_df["id"] = m_map_df["id"].astype(str).str.strip()
    # Normalize to lowercase
    mentor_name_to_id = dict(zip(m_map_df["name"].str.lower(), m_map_df["id"]))

    return startup_name_to_id, mentor_name_to_id

# Additional Constants
REASONING_PATH_1 = "cdl_matching/data/final_fit_scores_reasoning/fit1_scores_results.csv"
REASONING_PATH_2 = "cdl_matching/data/final_fit_scores_reasoning/fit2_scores_results.csv"
VENTURE_PREFS_PATH = "cdl_matching/data/final_fit_scores_reasoning/ventures_pref.csv"

def load_preferences(mentor_map, startup_map):
    print("Loading preferences from ventures_pref.csv...")
    if not os.path.exists(VENTURE_PREFS_PATH):
        print(f"Warning: Prefs file not found: {VENTURE_PREFS_PATH}")
        return {}

    pref_df = pd.read_csv(VENTURE_PREFS_PATH)
    
    # Map: startup_id -> [list of {'name': str, 'id': str|None}]
    prefs = {}
    
    # Manual overrides for mismatched names in preferences file
    overrides = {
        "er ocean research": "er ocean recherche",
        "co-reactive": "co-reactive" 
    }
    
    import re
    import unicodedata
    
    def strip_accents(s):
        return ''.join(c for c in unicodedata.normalize('NFD', s)
                  if unicodedata.category(c) != 'Mn')
    
    for _, row in pref_df.iterrows():
        v_name_raw = str(row['Ventures']).strip()
        if not v_name_raw or v_name_raw.lower() == 'nan': continue
        
        v_key = v_name_raw.lower()
        if v_key in overrides:
            v_key = overrides[v_key]
            
        # Resolve Startup ID
        s_id = startup_map.get(v_key)
        
        if not s_id:
             for sm_key, sm_id in startup_map.items():
                 if v_key in sm_key or sm_key in v_key:
                     s_id = sm_id
                     break
        
        if not s_id:
            # print(f"Warning: Could not map preference venture '{v_name_raw}'")
            continue
            
        # Get mentor columns
        mentor_list = []
        seen_names = set()
        
        for i in range(1, 10):
            col = f"Mentor_PREF_{i}"
            if col not in row: continue
            
            m_name_raw = row[col]
            if pd.isna(m_name_raw): continue
            
            m_name_str = str(m_name_raw).strip()
            # Basic cleanup for display
            display_name = m_name_str.replace('*', '').replace('.', ' ').strip()
            display_name = " ".join(display_name.split()) # normalize string
            
            if not display_name: continue
            if display_name.lower() in seen_names: continue
            seen_names.add(display_name.lower())
            
            # Matching logic for ID
            candidates = []
            
            clean_raw = m_name_str.replace('*', '').strip()
            candidates.append(clean_raw.lower())
            
            # Dots as spaces
            clean_dots = re.sub(r'[._]', ' ', clean_raw)
            candidates.append(" ".join(clean_dots.split()).lower())
            
            # Remove accents (Å -> A)
            clean_no_accents = strip_accents(clean_raw)
            candidates.append(clean_no_accents.lower())
            
            # "Jason Blackstock Mentor" -> "Jason Blackstock"
            if "mentor" in clean_raw.lower():
                candidates.append(clean_raw.lower().replace("mentor", "").strip())
                
            m_id = None
            for key in candidates:
                m_id = mentor_map.get(key)
                if m_id: break
            
            mentor_list.append({
                "name": display_name,
                "id": m_id
            })
                
        prefs[s_id] = mentor_list
        
    return prefs

def load_startup_objectives():
    print("Loading startup objectives from JSON...")
    obj_map = {}
    
    json_files = [
        "cdl_matching/data/final_fit_scores_reasoning/Climate_Ventures_Shift1.json",
        "cdl_matching/data/final_fit_scores_reasoning/Climate_Ventures_Shift2.json"
    ]
    
    import json
    for jf in json_files:
        if not os.path.exists(jf):
            print(f"Warning: JSON file not found: {jf}")
            continue
        try:
            with open(jf, 'r') as f:
                data = json.load(f)
                # Expecting a list of dicts
                if isinstance(data, list):
                    for item in data:
                        s_id = item.get("startup_id")
                        objectives = item.get("startup_objectives")
                        if s_id and objectives:
                            obj_map[str(s_id).strip()] = str(objectives).strip()
        except Exception as e:
            print(f"Error reading {jf}: {e}")
            
    return obj_map

def load_data():
    print("Loading data...")
    # Load fit scores from both sessions
    fit_df_1 = pd.read_csv(FIT_SCORES_PATH_S1)
    fit_df_2 = pd.read_csv(FIT_SCORES_PATH_S2)
    fit_df = pd.concat([fit_df_1, fit_df_2], ignore_index=True)
    
    # Load comparison report
    comp_df = pd.read_csv(COMPARISON_REPORT_PATH)
    
    # Load full schedule
    sched_df = pd.read_csv(FULL_SCHEDULE_PATH)
    
    # Load Reasoning Data
    # Columns usually: startup_id, mentor_id, FITx_explicability (or similar reasoning text)
    # We want to create a lookup: (startup_id, mentor_id) -> reasoning_text
    # We'll merge both files.
    
    # Helper to clean/standardize
    def load_reasoning(path):
        if not os.path.exists(path):
            print(f"Warning: Reasoning file not found: {path}")
            return pd.DataFrame()
        return pd.read_csv(path)

    r_df_1 = load_reasoning(REASONING_PATH_1)
    r_df_2 = load_reasoning(REASONING_PATH_2)
    
    # Normalize columns if needed. Expect 'FIT1_explicability' or 'FIT2_explicability'
    # Rename them to 'reasoning' for consistency
    # Normalize columns if needed.
    if 'FIT1_explicability' in r_df_1.columns:
        r_df_1 = r_df_1.rename(columns={'FIT1_explicability': 'reasoning'})
    
    # Create 'relevance' column for S1
    if 'FIT1_match_drivers' in r_df_1.columns:
        def parse_drivers(x):
            try:
                import ast
                val = ast.literal_eval(str(x))
                if isinstance(val, list):
                    return "; ".join(val)
                return str(x)
            except:
                return str(x)
        r_df_1['relevance'] = r_df_1['FIT1_match_drivers'].apply(parse_drivers)
    else:
        r_df_1['relevance'] = ""

    # Process Session 2
    if 'FIT2_explicability' in r_df_2.columns:
        r_df_2 = r_df_2.rename(columns={'FIT2_explicability': 'reasoning'})
        
    # Create 'relevance' column for S2
    if 'FIT2_objective_alignment' in r_df_2.columns:
        def parse_obj_align(x):
            try:
                import ast
                val = ast.literal_eval(str(x))
                if isinstance(val, list):
                    parts = []
                    for item in val:
                        obj_num = item.get('objective', '?')
                        why = item.get('why', '')
                        if why:
                            parts.append(f"Obj {obj_num}: {why}")
                    return " | ".join(parts)
                return str(x)
            except:
                return str(x)
        r_df_2['relevance'] = r_df_2['FIT2_objective_alignment'].apply(parse_obj_align)
    else:
        r_df_2['relevance'] = ""
        
    # Standardize columns
    desired_cols = ['startup_id', 'mentor_id', 'reasoning', 'relevance']
    
    # Ensure columns exist
    for df in [r_df_1, r_df_2]:
        for c in desired_cols:
            if c not in df.columns:
                df[c] = ""
                
    reasoning_df = pd.concat([r_df_1[desired_cols], r_df_2[desired_cols]], ignore_index=True)

    # Load Mappings
    startup_map, mentor_map = load_mappings()
    
    # Load Objectives
    obj_map = load_startup_objectives()
    
    return fit_df, comp_df, sched_df, startup_map, mentor_map, reasoning_df, obj_map

def generate_top_line_table(comp_df, fit_df, startup_map, mentor_map):
    print("Generating Table 1: Top-Line Performance...")
    
    # Pre-process fit scores for lookup
    scores = {}
    for _, row in fit_df.iterrows():
        s_id = row['startup_id']
        scores[s_id] = row.to_dict()

    results = []
    
    # We need to compute stats for N=18 ventures
    # We will Iterate over comp_df and re-calculate "Total Fit" for CDL and ION
    # to ensures we handle definitions consistently: Fit(OS) + Fit(CR)
    
    cdl_total_fits = []
    ion_total_fits = []
    
    cdl_all_scores = [] # for max tracking
    ion_all_scores = []
    
    better_count = 0
    equal_count = 0
    worse_count = 0
    
    valid_ventures_count = 0
    
    for _, row in comp_df.iterrows():
        # Normalize: strip and lower
        venture_name_raw = str(row['Venture']).strip()
        venture_name_key = venture_name_raw.lower()
        
        if venture_name_key not in startup_map:
            print(f"Skipping {venture_name_raw} (No ID map for key '{venture_name_key}')")
            continue
            
        s_id = startup_map[venture_name_key]
        valid_ventures_count += 1
        
        # --- CDL Scores ---
        cdl_os_name = str(row['Original_OS']).strip() if pd.notna(row['Original_OS']) else None
        cdl_oc_name = str(row['Original_OC']).strip() if pd.notna(row['Original_OC']) else None
        
        cdl_os_score = 0
        if cdl_os_name:
            cdl_os_key = cdl_os_name.lower()
            if cdl_os_key in mentor_map:
                m_id = mentor_map[cdl_os_key]
                if s_id in scores and m_id in scores[s_id]:
                    cdl_os_score = scores[s_id][m_id]
        
        cdl_oc_score = 0
        if cdl_oc_name:
            cdl_oc_key = cdl_oc_name.lower()
            if cdl_oc_key in mentor_map:
                m_id = mentor_map[cdl_oc_key]
                if s_id in scores and m_id in scores[s_id]:
                    cdl_oc_score = scores[s_id][m_id]

        cdl_total = cdl_os_score + cdl_oc_score
        cdl_total_fits.append(cdl_total)
        
        if cdl_os_score > 0: cdl_all_scores.append(cdl_os_score)
        if cdl_oc_score > 0: cdl_all_scores.append(cdl_oc_score)

        # --- ION Scores ---
        ion_os_name = str(row['Created_OS']).strip() if pd.notna(row['Created_OS']) else None
        ion_oc_name = str(row['Created_OC']).strip() if pd.notna(row['Created_OC']) else None
        
        ion_os_score = 0
        if ion_os_name:
            ion_os_key = ion_os_name.lower()
            if ion_os_key in mentor_map:
                m_id = mentor_map[ion_os_key]
                if s_id in scores and m_id in scores[s_id]:
                    ion_os_score = scores[s_id][m_id]
        
        ion_oc_score = 0
        if ion_oc_name:
            ion_oc_key = ion_oc_name.lower()
            if ion_oc_key in mentor_map:
                m_id = mentor_map[ion_oc_key]
                if s_id in scores and m_id in scores[s_id]:
                    ion_oc_score = scores[s_id][m_id]

        ion_total = ion_os_score + ion_oc_score
        ion_total_fits.append(ion_total)
        
        if ion_os_score > 0: ion_all_scores.append(ion_os_score)
        if ion_oc_score > 0: ion_all_scores.append(ion_oc_score)
        
        # Compare
        # Float tolerance
        diff = ion_total - cdl_total
        if diff > 1e-6:
            better_count += 1
        elif diff < -1e-6:
            worse_count += 1
        else:
            equal_count += 1

    # --- Metrics ---
    # Avg Total Fit Score
    avg_total_cdl = pd.Series(cdl_total_fits).mean()
    avg_total_ion = pd.Series(ion_total_fits).mean()
    
    # Avg Fit per Role (Total / 2)
    avg_role_cdl = avg_total_cdl / 2
    avg_role_ion = avg_total_ion / 2
    
    # Better Rate
    better_rate = (better_count / valid_ventures_count) * 100 if valid_ventures_count > 0 else 0
    
    # Highest Single Match Score
    max_cdl = max(cdl_all_scores) if cdl_all_scores else 0
    max_ion = max(ion_all_scores) if ion_all_scores else 0
    
    # --- Construct DataFrame ---
    # Structure: Metric | CDL Assignments | ION Matching (MILP) | Delta
    
    rows = []
    
    # 1. Avg Total Fit Score
    rows.append({
        "Metric": "Avg Total Fit Score (0–2)",
        "Definition": "For each venture v: Fit(OS_v)+Fit(CR_v). Report the average across ventures.",
        "CDL Assignments": f"{avg_total_cdl:.2f}",
        "ION Matching (MILP)": f"{avg_total_ion:.2f}",
        "Delta": f"{avg_total_ion - avg_total_cdl:+.2f}"
    })
    
    # 2. Avg Fit per Role
    rows.append({
        "Metric": "Avg Fit per Role (0–1)",
        "Definition": "Avg Total Fit Score ÷ 2 (interpretable as per-role fit).",
        "CDL Assignments": f"{avg_role_cdl:.2f}",
        "ION Matching (MILP)": f"{avg_role_ion:.2f}",
        "Delta": f"{avg_role_ion - avg_role_cdl:+.2f}"
    })
    
    # Spacer
    rows.append({"Metric": "Venture-level outcomes (N=18)", "Definition": "Count ventures where TotalFit_ION is > / = / < TotalFit_CDL.", "CDL Assignments": "-", "ION Matching (MILP)": "-", "Delta": "-"})
    
    # 3. Better
    rows.append({
        "Metric": "• Better",
        "Definition": "# ventures with higher total fit under ION",
        "CDL Assignments": "0",
        "ION Matching (MILP)": f"{better_count}",
        "Delta": "-"
    })
    
    # 4. Equal
    rows.append({
        "Metric": "• Equal",
        "Definition": "# ventures with identical total fit",
        "CDL Assignments": "-",
        "ION Matching (MILP)": f"{equal_count}",
        "Delta": "-"
    })
    
    # 5. Worse
    rows.append({
        "Metric": "• Worse",
        "Definition": "# ventures where CDL total fit is higher",
        "CDL Assignments": "-",
        "ION Matching (MILP)": f"{worse_count}",
        "Delta": "-"
    })
    
    # 6. Better Rate
    rows.append({
        "Metric": "Better rate (%)",
        "Definition": "Better ÷ N",
        "CDL Assignments": "-",
        "ION Matching (MILP)": f"{better_rate:.1f}%",
        "Delta": "-"
    })
    
    # 7. Highest single match score
    rows.append({
        "Metric": "Highest single match score (0–1)",
        "Definition": "Max fit among all assigned OS/CR mentor pairs",
        "CDL Assignments": f"{max_cdl:.2f}",
        "ION Matching (MILP)": f"{max_ion:.2f}",
        "Delta": f"{max_ion - max_cdl:+.2f}"
    })
    
    top_line_df = pd.DataFrame(rows)
    return top_line_df

def generate_audit_table(comp_df, fit_df, startup_map, mentor_map, reasoning_df, obj_map):
    print("Generating Table 2: Startup-by-Startup Audit...")
    
    # Pre-process fit scores
    scores = {}
    for _, row in fit_df.iterrows():
        s_id = row['startup_id']
        scores[s_id] = row.to_dict()
        
    # Pre-process reasoning: (s_id, m_id) -> {reasoning, relevance}
    reasoning_lookup = {}
    for _, row in reasoning_df.iterrows():
        key = (str(row['startup_id']).strip(), str(row['mentor_id']).strip())
        r_text = str(row.get('reasoning', '')).strip()
        rel_text = str(row.get('relevance', '')).strip()
        
        # Clean quotes
        if r_text.startswith('"') and r_text.endswith('"'): r_text = r_text[1:-1]
        
        reasoning_lookup[key] = {'reasoning': r_text, 'relevance': rel_text}

    audit_rows = []
    
    for _, row in comp_df.iterrows():
        venture_name_raw = str(row['Venture']).strip()
        venture_name_key = venture_name_raw.lower()
        
        if venture_name_key not in startup_map:
            print(f"Skipping {venture_name_raw} (No ID map)")
            continue
            
        s_id = startup_map[venture_name_key]
        
        # Helper to get name, score, and ID
        def get_mentor_details(name_raw, role_debug):
            if not pd.notna(name_raw):
                return "Unassigned", 0.0, None
            
            name_clean = str(name_raw).strip()
            name_key = name_clean.lower()
            score = 0.0
            m_id = None
            
            if name_key in mentor_map:
                m_id = mentor_map[name_key]
                if s_id in scores and m_id in scores[s_id]:
                    try:
                        score = float(scores[s_id][m_id])
                    except (ValueError, TypeError):
                        score = 0.0
            
            return f"{name_clean} ({score:.2f})", score, m_id

        # --- CDL ---
        cdl_os_str, cdl_os_score, cdl_os_id = get_mentor_details(row['Original_OS'], "CDL OS")
        cdl_oc_str, cdl_oc_score, cdl_oc_id = get_mentor_details(row['Original_OC'], "CDL OC")
        cdl_total = cdl_os_score + cdl_oc_score
        
        # --- ION ---
        ion_os_str, ion_os_score, ion_os_id = get_mentor_details(row['Created_OS'], "ION OS")
        ion_oc_str, ion_oc_score, ion_oc_id = get_mentor_details(row['Created_OC'], "ION OC")
        ion_total = ion_os_score + ion_oc_score
        
        # --- Deltas ---
        total_delta = ion_total - cdl_total
        os_delta = ion_os_score - cdl_os_score
        cr_delta = ion_oc_score - cdl_oc_score
        
        if total_delta > 1e-6:
            outcome = "Better"
        elif total_delta < -1e-6:
            outcome = "Worse"
        else:
            outcome = "Equal"
            
        # Reasoning & Relevance Lookup
        def lookup(s_id, m_id, key_type):
            if not m_id: return "No assignment."
            dat = reasoning_lookup.get((s_id, m_id), {})
            val = dat.get(key_type, "No data.")
            return val

        os_reason = lookup(s_id, ion_os_id, 'reasoning')
        cr_reason = lookup(s_id, ion_oc_id, 'reasoning')
        
        os_rel = lookup(s_id, ion_os_id, 'relevance')
        cr_rel = lookup(s_id, ion_oc_id, 'relevance')
        
        # Clean newlines
        os_reason = os_reason.replace('\n', ' ').replace('\r', '')
        cr_reason = cr_reason.replace('\n', ' ').replace('\r', '')
        os_rel = os_rel.replace('\n', ' ').replace('\r', '')
        cr_rel = cr_rel.replace('\n', ' ').replace('\r', '')
        
        full_reasoning = f"**Objective Setter**: {os_reason}\n**Critiquer**: {cr_reason}"
        full_relevance = f"**Objective Setter**: {os_rel}\n**Critiquer**: {cr_rel}"
        
        # Objectives
        # Replace | with newline for readability in cell
        objectives = obj_map.get(s_id, "N/A").replace('|', '\n')

        audit_rows.append({
            "Venture Name": venture_name_raw,
            "CDL Objective Setter (fit)": cdl_os_str,
            "CDL Critiquer (fit)": cdl_oc_str,
            "CDL Total Fit": f"{cdl_total:.2f}",
            "ION Objective Setter (fit)": ion_os_str,
            "ION Critiquer (fit)": ion_oc_str,
            "ION Total Fit": f"{ion_total:.2f}",
            "Difference in OS": f"{os_delta:+.2f}",
            "Difference in CR": f"{cr_delta:+.2f}",
            "Delta": f"{total_delta:+.2f}",
            "Outcome": outcome,
            "Startup Objectives/Needs": objectives,
            "Needs Relevance to Mentor Capabilities": full_relevance,
            "Model Reasoning": full_reasoning
        })
        
    audit_df = pd.DataFrame(audit_rows)
    return audit_df

def generate_preference_respect_table(comp_df, fit_df, startup_map, mentor_map):
    print("Generating Table 3: Preference-Respect Comparison (Detailed Split)...")
    
    prefs = load_preferences(mentor_map, startup_map)
    
    # Create ID -> Name map for display
    id_to_name = {}
    for name_key, m_id in mentor_map.items():
        if m_id not in id_to_name:
            id_to_name[m_id] = name_key.title()
            
    rows = []
    
    # Stats Counters
    stats = {
        "CDL_OS": {}, "CDL_OC": {},
        "ION_OS": {}, "ION_OC": {}
    }
    
    def increment_stat(group, rank):
        if rank not in stats[group]: stats[group][rank] = 0
        stats[group][rank] += 1
    
    for _, row in comp_df.iterrows():
        venture_name_raw = str(row['Venture']).strip()
        venture_name_key = venture_name_raw.lower()
        
        row_data = {
            "Venture Name": venture_name_raw,
            "Pref 1": "", "Pref 2": "", "Pref 3": "", "Pref 4": "",
            "CDL OS": "Unassigned", "CDL OS Rank": "-",
            "CDL OC": "Unassigned", "CDL OC Rank": "-",
            "ION OS": "Unassigned", "ION OS Rank": "-",
            "ION OC": "Unassigned", "ION OC Rank": "-"
        }
        
        # Prefs - Lookup by Startup ID now!
        s_id = startup_map.get(venture_name_key)
        if not s_id:
             # Try simple contains fallback same as load_prefs?
             for sm_key, sm_id in startup_map.items():
                 if venture_name_key in sm_key or sm_key in venture_name_key:
                     s_id = sm_id
                     break
             
        venture_prefs = prefs.get(s_id, [])
        # venture_prefs is a list of dicts: {'name': 'Raw Name', 'id': 'MENTOR_XXX'}
        
        pref_ids = [p['id'] for p in venture_prefs if p['id']]
        
        for i in range(4):
            key = f"Pref {i+1}"
            if i < len(venture_prefs):
                # Use the display name from the prefs file directly!
                row_data[key] = venture_prefs[i]['name']
            else:
                row_data[key] = "-"
                
        # Helper for Assignment + Rank
        def process_assignment(name_raw, group_key):
            if not pd.notna(name_raw):
                return "Unassigned", "-"
            
            clean_name = str(name_raw).strip()
            key = clean_name.lower()
            m_id = mentor_map.get(key)
            
            rank_display = "Unranked"
            stat_rank = "Unranked"
            
            # Check against pref_ids
            if m_id and m_id in pref_ids:
                rank_idx = pref_ids.index(m_id) + 1
                if rank_idx == 1: suffix = "st"
                elif rank_idx == 2: suffix = "nd"
                elif rank_idx == 3: suffix = "rd"
                else: suffix = "th"
                rank_display = f"{rank_idx}{suffix} Choice"
                stat_rank = str(rank_idx) # Track as "1", "2" etc
            
            increment_stat(group_key, stat_rank)
            return clean_name, rank_display
            
        # CDL
        c_os, c_os_r = process_assignment(row['Original_OS'], "CDL_OS")
        row_data["CDL OS"] = c_os
        row_data["CDL OS Rank"] = c_os_r
        
        c_oc, c_oc_r = process_assignment(row['Original_OC'], "CDL_OC")
        row_data["CDL OC"] = c_oc
        row_data["CDL OC Rank"] = c_oc_r
        
        # ION
        i_os, i_os_r = process_assignment(row['Created_OS'], "ION_OS")
        row_data["ION OS"] = i_os
        row_data["ION OS Rank"] = i_os_r
        
        i_oc, i_oc_r = process_assignment(row['Created_OC'], "ION_OC")
        row_data["ION OC"] = i_oc
        row_data["ION OC Rank"] = i_oc_r
        
        rows.append(row_data)

    # --- Stats Rows ---
    # Add empty row
    empty_row = {k: "" for k in row_data.keys()}
    rows.append(empty_row)
    
    # Header for Stats
    header_row = empty_row.copy()
    header_row["Venture Name"] = "STATISTICS SUMMARY"
    rows.append(header_row)
    
    # We want counts for 1st, 2nd, 3rd, 4th, Unranked
    # across groups
    rank_keys = sorted(list(set(k for c in stats.values() for k in c.keys())), key=lambda x: int(x) if x.isdigit() else 99)
    
    for rk in rank_keys:
        stat_row = empty_row.copy()
        label = f"{rk} Choice" if rk.isdigit() else rk
        stat_row["Venture Name"] = f"Count of {label}"
        
        stat_row["CDL OS Rank"] = stats["CDL_OS"].get(rk, 0)
        stat_row["CDL OC Rank"] = stats["CDL_OC"].get(rk, 0)
        stat_row["ION OS Rank"] = stats["ION_OS"].get(rk, 0)
        stat_row["ION OC Rank"] = stats["ION_OC"].get(rk, 0)
        
        rows.append(stat_row)

    pref_df = pd.DataFrame(rows)
    
    cols = [
        "Venture Name", 
        "Pref 1", "Pref 2", "Pref 3", "Pref 4",
        "CDL OS", "CDL OS Rank",
        "CDL OC", "CDL OC Rank",
        "ION OS", "ION OS Rank",
        "ION OC", "ION OC Rank"
    ]
    pref_df = pref_df[cols]
    
    return pref_df
                


def generate_mentor_utilization_table(comp_df, sched_df, mentor_map):
    print("Generating Table 4: Mentor Utilization & Slot Allocation...")
    
    # Use mentor_map to get all mentor names (ID -> Name)
    # Handle duplicates by keeping the first or most standard name for an ID
    id_to_name = {}
    for name_key, m_id in mentor_map.items():
        if m_id not in id_to_name:
            # Try to format name nicely (Title Case)
            id_to_name[m_id] = name_key.title()
            
    # Initialize Counts
    cdl_counts = {mid: 0 for mid in id_to_name}
    ion_counts = {mid: 0 for mid in id_to_name}
    
    # Count CDL from comp_df (assuming it represents CDL assignments correctly)
    # Note: CDL assignments might be from a different file structure, but comp_df "Original_OS/OC" is our best source for CDL baseline.
    for _, row in comp_df.iterrows():
        for col in ['Original_OS', 'Original_OC']:
            name = row[col]
            if pd.notna(name):
                k = str(name).strip().lower()
                mid = mentor_map.get(k)
                if mid and mid in cdl_counts:
                    cdl_counts[mid] += 1
                    
    # Count ION from sched_df (Operational Reality)
    # sched_df columns: os_mentor_id, oc_mentor_id
    for _, row in sched_df.iterrows():
        # OS
        os_id = row['os_mentor_id']
        if pd.notna(os_id) and os_id in ion_counts:
            ion_counts[os_id] += 1
            
        # OC
        oc_id = row['oc_mentor_id']
        if pd.notna(oc_id) and oc_id in ion_counts:
            ion_counts[oc_id] += 1
            
    # Build Table
    util_rows = []
    for mid, name in id_to_name.items():
        cdl_n = cdl_counts[mid]
        ion_n = ion_counts[mid]
        
        util_rows.append({
            "Mentor Name": name,
            "CDL # of Slots": cdl_n,
            "ION # of Slots": ion_n,
            "Max Slots Allowed": 3,
            "Total Assignments": ion_n
        })
        
    util_df = pd.DataFrame(util_rows)
    util_df = util_df.sort_values(by="ION # of Slots", ascending=False)
    
    return util_df

def main():
    if not os.path.exists(OUTPUT_DIR):
        print(f"Creating directory {OUTPUT_DIR}")
        os.makedirs(OUTPUT_DIR)

    fit_df, comp_df, sched_df, startup_map, mentor_map, reasoning_df, obj_map = load_data()
    
    # 1. Top Line (Strict Table 1)
    top_line = generate_top_line_table(comp_df, fit_df, startup_map, mentor_map)
    top_line.to_csv(f"{OUTPUT_DIR}/top_line_performance.csv", index=False)
    print(f"Saved {OUTPUT_DIR}/top_line_performance.csv")
    
    # 2. Audit (Strict Table 2)
    audit_df = generate_audit_table(comp_df, fit_df, startup_map, mentor_map, reasoning_df, obj_map)
    audit_df.to_csv(f"{OUTPUT_DIR}/startup_audit.csv", index=False)
    print(f"Saved {OUTPUT_DIR}/startup_audit.csv")

    # 3. Preference Respect (Table 3)
    pref_df = generate_preference_respect_table(comp_df, fit_df, startup_map, mentor_map)
    pref_df.to_csv(f"{OUTPUT_DIR}/preference_respect.csv", index=False)
    print(f"Saved {OUTPUT_DIR}/preference_respect.csv")
    
    # 4. Utilization (Table 4)
    # Use mentor_map from load_mappings (which covers all mapped mentors)
    util_df = generate_mentor_utilization_table(comp_df, sched_df, mentor_map)
    util_df.to_csv(f"{OUTPUT_DIR}/mentor_utilization.csv", index=False)
    print(f"Saved {OUTPUT_DIR}/mentor_utilization.csv")
    
    print("\nAll 4 Tables Generated Successfully.")

if __name__ == "__main__":
    main()
