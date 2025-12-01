# run_tests.py
from cdl_matching.data_generation.toy_dataset import make_toy_dataset
from cdl_matching.scheduling.solve import solve_schedule
from cdl_matching.scheduling.diagnostics import analyze_session_feasibility
from run_toy import optimize_mentor_selection

def run_test_case(name, num_startups, num_mentors_pool, target_mentors, target_tables):
    print(f"\n{'='*20}\nRUNNING TEST: {name}\n{'='*20}")
    
    # 1. Generate Data
    # Ensure initial tables isn't too high for the pool
    import math
    initial_tables = math.ceil(num_mentors_pool / 3)
    if initial_tables < 1: initial_tables = 1
    
    mentors, startups, mentor_fit = make_toy_dataset(
        num_tables=initial_tables, 
        num_startups=num_startups,
        mentors_per_table=3,
        num_mentors_pool=num_mentors_pool,
        seed=42
    )
    
    print(f"Generated {len(mentors)} mentors and {len(startups)} startups.")
    
    # 2. Optimize Selection
    if len(mentors) > target_mentors:
        print(f"Optimizing selection to {target_mentors} mentors...")
        mentors = optimize_mentor_selection(
            mentors, 
            startups, 
            mentor_fit, 
            target_count=target_mentors, 
            target_tables=target_tables
        )
        
        # Re-assign OS/OC
        from cdl_matching.data_generation.startup_factory import create_startups_with_os_oc
        startups = create_startups_with_os_oc(
            mentors=mentors,
            num_startups=num_startups,
            seed=42,
            mentor_fit=mentor_fit
        )
        
    # 3. Print Debug Info
    print("\n[DEBUG] Mentor Assignments:")
    mentors_by_table = {}
    for m in mentors:
        mentors_by_table.setdefault(m.table_id, []).append(m.id)
    for t in sorted(mentors_by_table.keys()):
        print(f"  Table {t}: {mentors_by_table[t]}")
        
    print("\n[DEBUG] Startup OS/OC:")
    for s in startups:
        print(f"  {s.id}: OS={s.os_id}, OC={s.oc_id}")

    # 4. Check Feasibility
    diag = analyze_session_feasibility(
        mentors,
        startups,
        num_sgms=3,
        os_sgms_allowed=(1, 2),
        oc_sgms_allowed=(2, 3),
    )
    if not diag["ok"]:
        print(f"\n[FAIL] Structurally Infeasible: {diag['messages']}")
        return

    # 5. Solve
    status, sol = solve_schedule(
        mentors,
        startups,
        mentor_fit,
        num_sgms=3,
    )
    print(f"\n[RESULT] Solver Status: {status}")
    
    if status == "Optimal":
        print("Schedule found!")

def main():
    # Test Case 1: One Startup, Many Mentors
    # Goal: Should pick the absolute best mentors for S1 and put them on tables.
    run_test_case(
        name="1 Startup, 20 Mentors -> Select 9",
        num_startups=1,
        num_mentors_pool=20,
        target_mentors=9,
        target_tables=3
    )

    # Test Case 2: Two Startups, Six Mentors (Edge Case)
    # Goal: Tight constraints. 6 mentors = 2 per table (if 3 tables) or 3 per table (if 2 tables).
    # We target 3 tables, so 2 mentors per table.
    # This is tricky because each table needs 3 slots usually? No, capacity is per SGM.
    # But if a table has only 2 mentors, it's fine as long as they are good.
    run_test_case(
        name="2 Startups, 9 Mentors -> Select 9",
        num_startups=2,
        num_mentors_pool=9,
        target_mentors=9,
        target_tables=3
    )

if __name__ == "__main__":
    main()
