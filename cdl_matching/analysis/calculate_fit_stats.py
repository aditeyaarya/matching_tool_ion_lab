import pandas as pd
import os

# File Paths
MENTOR_MAPPING_PATH = "cdl_matching/data/comparision_os_oc/mentor_mapping.csv"
STARTUP_MAPPING_PATH = "cdl_matching/data/comparision_os_oc/startup_mapping.csv"

FIT_SCORES_SESSION_1 = "cdl_matching/data/final_fit_scores_session_1.csv"
FIT_SCORES_SESSION_2 = "cdl_matching/data/final_fit_scores_session_2.csv"

FILE_1_INPUT = "cdl_matching/data/comparision_os_oc/CDL_Binder_OS_OC_Mentors.csv"
FILE_2_INPUT = "cdl_matching/data/comparision_os_oc/CDL_Binder_OS_OC_Mentors_Created.csv"

REPORT_OUTPUT = "data/outputs/comparision_os_oc/CDL_Binder_Comparison_Report.csv"

def load_mappings():
    """Returns (mentor_name_to_id, startup_name_to_id)"""
    mentor_df = pd.read_csv(MENTOR_MAPPING_PATH, header=None, names=["id", "name"])
    # Strip whitespace just in case
    mentor_df["name"] = mentor_df["name"].astype(str).str.strip()
    mentor_df["id"] = mentor_df["id"].astype(str).str.strip()
    mentor_name_to_id = dict(zip(mentor_df["name"], mentor_df["id"]))

    startup_df = pd.read_csv(STARTUP_MAPPING_PATH)
    startup_df["startup_name"] = startup_df["startup_name"].astype(str).str.strip()
    startup_df["startup_id"] = startup_df["startup_id"].astype(str).str.strip()
    startup_name_to_id = dict(zip(startup_df["startup_name"], startup_df["startup_id"]))

    return mentor_name_to_id, startup_name_to_id

def load_fit_scores():
    """Returns a dict: (startup_id, mentor_id) -> score"""
    scores = {}
    
    for path in [FIT_SCORES_SESSION_1, FIT_SCORES_SESSION_2]:
        if not os.path.exists(path):
            print(f"Warning: Fit score file not found: {path}")
            continue
            
        df = pd.read_csv(path)
        # Assuming format: startup_id, MENTOR_001, MENTOR_002...
        # Iterate over rows
        for _, row in df.iterrows():
            s_id = str(row['startup_id']).strip()
            # Iterate over columns
            for col in df.columns:
                if col == 'startup_id':
                    continue
                m_id = str(col).strip()
                try:
                    score = float(row[col])
                    scores[(s_id, m_id)] = score
                except (ValueError, TypeError):
                    continue
    return scores

def process_file(input_path, mentor_map, startup_map, fit_scores):
    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return None

    print(f"Processing {input_path}...")
    df = pd.read_csv(input_path)
    
    os_scores = []
    oc_scores = []
    averages = []
    
    for _, row in df.iterrows():
        venture_name = str(row['Venture']).strip()
        os_name = str(row['Objective Setter']).strip()
        oc_name = str(row['Objective Critiquer']).strip()
        
        # Get IDs
        s_id = startup_map.get(venture_name)
        os_id = mentor_map.get(os_name)
        oc_id = mentor_map.get(oc_name)
        
        # Look up scores
        score_os = fit_scores.get((s_id, os_id))
        score_oc = fit_scores.get((s_id, oc_id))
        
        os_scores.append(score_os)
        oc_scores.append(score_oc)
        
        if score_os is not None and score_oc is not None:
            avg = (score_os + score_oc) / 2.0
            averages.append(avg)
        elif score_os is not None:
            averages.append(score_os)
        elif score_oc is not None:
            averages.append(score_oc)
        else:
            averages.append(None)
            
    # Add columns
    df['OS_Score'] = os_scores
    df['OC_Score'] = oc_scores
    df['Average_Score'] = averages
    
    # Calculate stats
    avg_os = pd.Series(os_scores).mean()
    avg_oc = pd.Series(oc_scores).mean()
    avg_total = pd.Series(averages).mean()
    
    print(f"  Stats for {os.path.basename(input_path)}:")
    print(f"    Avg OS Score: {avg_os:.4f}")
    print(f"    Avg OC Score: {avg_oc:.4f}")
    print(f"    Overall Avg:  {avg_total:.4f}")
    
    return df

def generate_comparison_report(original_df, created_df, output_path):
    print("\nGenerating Comparison Report...")
    
    # Prefix columns to avoid collision
    orig = original_df[['Venture', 'Objective Setter', 'OS_Score', 'Objective Critiquer', 'OC_Score', 'Average_Score']].copy()
    orig['Venture'] = orig['Venture'].astype(str).str.title().str.strip() # Normalize
    orig.columns = ['Venture', 'Original_OS', 'Original_OS_Score', 'Original_OC', 'Original_OC_Score', 'Original_Avg']
    
    created = created_df[['Venture', 'Objective Setter', 'OS_Score', 'Objective Critiquer', 'OC_Score', 'Average_Score']].copy()
    created['Venture'] = created['Venture'].astype(str).str.title().str.strip() # Normalize
    created.columns = ['Venture', 'Created_OS', 'Created_OS_Score', 'Created_OC', 'Created_OC_Score', 'Created_Avg']
    
    # Merge on Venture
    # Use outer join to see mishaps if any, though ventures should match
    merged = pd.merge(orig, created, on='Venture', how='outer')
    
    # Calculate difference
    merged['Improvement'] = merged['Created_Avg'] - merged['Original_Avg']
    
    # Reorder for readability
    cols = [
        'Venture',
        'Original_OS', 'Created_OS', 'Original_OS_Score', 'Created_OS_Score',
        'Original_OC', 'Created_OC', 'Original_OC_Score', 'Created_OC_Score',
        'Original_Avg', 'Created_Avg', 'Improvement'
    ]
    # Check if all cols exist (in case of missing data), filter strictly
    final_cols = [c for c in cols if c in merged.columns]
    merged = merged[final_cols]
    
    merged.to_csv(output_path, index=False)
    print(f"Saved Comparison Report to {output_path}")

def main():
    print("Loading mappings...")
    mentor_map, startup_map = load_mappings()
    
    print("Loading fit scores...")
    fit_scores = load_fit_scores()
    
    # Process File 1 (Original)
    df1 = process_file(FILE_1_INPUT, mentor_map, startup_map, fit_scores)
    
    # Process File 2 (Created)
    df2 = process_file(FILE_2_INPUT, mentor_map, startup_map, fit_scores)
    
    if df1 is not None and df2 is not None:
        generate_comparison_report(df1, df2, REPORT_OUTPUT)

if __name__ == "__main__":
    main()
