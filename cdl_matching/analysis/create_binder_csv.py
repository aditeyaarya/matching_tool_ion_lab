import pandas as pd
import os

# File paths
MENTOR_MAPPING_PATH = "cdl_matching/data/comparision_os_oc/mentor_mapping.csv"
STARTUP_MAPPING_PATH = "cdl_matching/data/comparision_os_oc/startup_mapping.csv"
OUTPUT_PATH = "cdl_matching/data/comparision_os_oc/CDL_Binder_OS_OC_Mentors_Created.csv"

# Session configurations
SESSIONS = [
    {
        "name": "Session 1",
        "os_oc_path": "data/outputs/joint_milp_startup_os_oc_session_1.csv",
        "full_schedule_path": "data/outputs/joint_milp_full_schedule_session1.csv"
    },
    {
        "name": "Session 2",
        "os_oc_path": "data/outputs/joint_milp_startup_os_oc_session_2.csv",
        "full_schedule_path": "data/outputs/joint_milp_full_schedule_session_2.csv"
    }
]

def load_mappings():
    """Lengths IDs to Names."""
    mentor_df = pd.read_csv(MENTOR_MAPPING_PATH, header=None, names=["id", "name"])
    mentor_map = dict(zip(mentor_df["id"], mentor_df["name"]))

    startup_df = pd.read_csv(STARTUP_MAPPING_PATH)
    startup_map = dict(zip(startup_df["startup_id"], startup_df["startup_name"]))
    
    return mentor_map, startup_map

def main():
    print("Loading mappings...")
    mentor_map, startup_map = load_mappings()
    
    results = []
    
    for session in SESSIONS:
        print(f"Processing {session['name']}...")
        os_oc_path = session['os_oc_path']
        full_schedule_path = session['full_schedule_path']
        
        if not os.path.exists(os_oc_path) or not os.path.exists(full_schedule_path):
            print(f"  Warning: Missing files for {session['name']}, skipping.")
            continue

        # Load OS/OC assignments
        os_oc_df = pd.read_csv(os_oc_path)
        
        # Load Full Schedule
        schedule_df = pd.read_csv(full_schedule_path)
        
        # Process each startup found in the OS/OC file
        for _, row in os_oc_df.iterrows():
            startup_id = row['startup_id']
            # Some files might have 'startup_name' col but we rely on mapping for consistency
            startup_name = startup_map.get(startup_id, startup_id)
            
            # Get OS and OC IDs
            os_id = row['os_mentor_id']
            oc_id = row['oc_mentor_id']
            
            # Resolve Names
            os_name = mentor_map.get(os_id, os_id)
            oc_name = mentor_map.get(oc_id, oc_id)
            
            # Find all mentors for this startup in the schedule
            startup_schedule = schedule_df[schedule_df['startup_id'] == startup_id]
            
            all_mentor_ids = set()
            for ids_str in startup_schedule['mentor_ids_at_table']:
                if pd.isna(ids_str):
                    continue
                # IDs are separated by " | "
                ids = [m.strip() for m in str(ids_str).split('|')]
                all_mentor_ids.update(ids)
                
            # Exclude OS and OC from the list
            other_mentor_ids = {m for m in all_mentor_ids if m != os_id and m != oc_id}
            
            # Resolve names for other mentors
            other_mentor_names = [mentor_map.get(m, m) for m in other_mentor_ids]
            
            # Build the row
            row_data = {
                "Venture": startup_name,
                "Objective Setter": os_name,
                "Objective Critiquer": oc_name
            }
            
            # Add Mentor columns (Mentor1, Mentor2, ...)
            for i, m_name in enumerate(sorted(other_mentor_names), start=1):
                row_data[f"Mentor{i}"] = m_name
                
            results.append(row_data)
        
    # Create DataFrame
    result_df = pd.DataFrame(results)
    
    # Reorder columns to match target format (Venture, OS, OC, Mentor1, Mentor2...)
    cols = ["Venture", "Objective Setter", "Objective Critiquer"]
    mentor_cols = [c for c in result_df.columns if c.startswith("Mentor")]
    # Sort mentor columns numerically
    mentor_cols.sort(key=lambda x: int(x.replace("Mentor", "")))
    
    final_cols = cols + mentor_cols
    result_df = result_df[final_cols]
    
    print(f"Writing output to {OUTPUT_PATH}...")
    result_df.to_csv(OUTPUT_PATH, index=False)
    print("Done!")

if __name__ == "__main__":
    main()
