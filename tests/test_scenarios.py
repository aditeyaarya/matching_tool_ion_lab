# tests/test_scenarios.py
import unittest
import math
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cdl_matching.data_generation.toy_dataset import make_toy_dataset
from cdl_matching.scheduling.solve import solve_schedule
from cdl_matching.scheduling.diagnostics import analyze_session_feasibility
from cdl_matching.data_generation.startup_factory import create_startups_with_os_oc
from run_toy import optimize_mentor_selection

class TestMatchingScenarios(unittest.TestCase):

    def run_pipeline(self, num_startups, num_mentors_pool, target_mentors, target_tables, fit_matrix=None):
        """
        Helper to run the full generation -> optimization -> scheduling pipeline.
        Returns: (status, solution, mentors, startups)
        """
        # 1. Generate Data
        # Ensure initial tables isn't too high for the pool
        initial_tables = math.ceil(num_mentors_pool / 3)
        if initial_tables < 1: initial_tables = 1
        
        mentors, startups, mentor_fit = make_toy_dataset(
            num_tables=initial_tables, 
            num_startups=num_startups,
            mentors_per_table=3,
            num_mentors_pool=num_mentors_pool,
            seed=42,
            fit_matrix=fit_matrix
        )
        
        # 2. Optimize Selection
        if len(mentors) > target_mentors:
            mentors = optimize_mentor_selection(
                mentors, 
                startups, 
                mentor_fit, 
                target_count=target_mentors, 
                target_tables=target_tables
            )
            
            # Re-assign OS/OC
            startups = create_startups_with_os_oc(
                mentors=mentors,
                num_startups=num_startups,
                seed=42,
                mentor_fit=mentor_fit
            )
            
        # 3. Check Feasibility
        diag = analyze_session_feasibility(
            mentors,
            startups,
            num_sgms=3,
            os_sgms_allowed=(1, 2),
            oc_sgms_allowed=(2, 3),
        )
        
        if not diag["ok"]:
            return "Structurally Infeasible", {}, mentors, startups

        # 4. Solve
        status, sol = solve_schedule(
            mentors,
            startups,
            mentor_fit,
            num_sgms=3,
        )
        return status, sol, mentors, startups, mentor_fit

    def verify_os_before_oc(self, sol, startups, mentors):
        """Verify that OS meetings happen before OC meetings for all startups."""
        from cdl_matching.scheduling.sets_and_params import build_sets_and_params
        
        S, T, table_os, table_oc = build_sets_and_params(mentors, startups)
        
        # Extract meeting times for each startup
        startup_schedule = {s.id: {} for s in startups}
        for (s_id, t_id, k), v in sol.items():
            if v == 1:
                role = "Other"
                if t_id == table_os.get(s_id):
                    role = "OS"
                elif t_id == table_oc.get(s_id):
                    role = "OC"
                startup_schedule[s_id][role] = k

        for s in startups:
            sched = startup_schedule[s.id]
            os_sgm = sched.get("OS")
            oc_sgm = sched.get("OC")
            
            self.assertIsNotNone(os_sgm, f"{s.id} missing OS meeting")
            self.assertIsNotNone(oc_sgm, f"{s.id} missing OC meeting")
            self.assertLess(os_sgm, oc_sgm, f"{s.id}: OS (SGM {os_sgm}) should be before OC (SGM {oc_sgm})")

    def verify_mentor_fit_quality(self, mentors, startups, mentor_fit, min_fit_threshold=0.3):
        """
        Verify that each startup has access to at least one good-fit mentor on each table.
        This ensures no startup is completely isolated from quality mentorship.
        """
        from cdl_matching.scheduling.solve import _build_table_fit
        
        table_fit = _build_table_fit(mentors, startups, mentor_fit)
        tables = sorted(set(m.table_id for m in mentors))
        
        for s in startups:
            # Check that the startup has at least one "decent" table
            max_fit_for_startup = max(table_fit.get((s.id, t), 0.0) for t in tables)
            self.assertGreater(
                max_fit_for_startup, 
                min_fit_threshold,
                f"{s.id} has no table with fit > {min_fit_threshold} (max: {max_fit_for_startup:.2f})"
            )

    def test_one_startup_many_mentors(self):
        """Test 1 startup, 20 mentors -> Select 9. Should be Optimal."""
        print("\nRunning test_one_startup_many_mentors...")
        status, sol, mentors, startups, mentor_fit = self.run_pipeline(
            num_startups=1,
            num_mentors_pool=20,
            target_mentors=9,
            target_tables=3
        )
        
        # 1. Status should be Optimal
        self.assertEqual(status, "Optimal")
        
        # 2. Verify OS before OC
        self.verify_os_before_oc(sol, startups, mentors)
        
        # 3. Verify mentor fit quality
        self.verify_mentor_fit_quality(mentors, startups, mentor_fit, min_fit_threshold=0.3)

    def test_two_startups_few_mentors(self):
        """Test 2 startups, 6 mentors -> Select 6. Expected Infeasible due to tight constraints."""
        print("\nRunning test_two_startups_few_mentors...")
        status, sol, mentors, startups, mentor_fit = self.run_pipeline(
            num_startups=2,
            num_mentors_pool=6,
            target_mentors=6,
            target_tables=3 # 2 mentors per table effectively
        )
        # Depending on exact constraints, this might be Infeasible or Structurally Infeasible
        self.assertIn(status, ["Infeasible", "Structurally Infeasible"])
        # Note: We don't verify OS/OC or fit quality for infeasible cases

    def test_high_fit_scores(self):
        """Test where ALL mentors have high fit scores (> 0.8)."""
        print("\nRunning test_high_fit_scores...")
        # Manually create a fit matrix where everyone is a genius
        # We need to add slight variance so that OS/OC are distinct and not just the first ones in the list
        # If everyone is 0.9, then M001 is OS, M002 is OC for EVERYONE.
        # And if M001/M002 are on Table 1, we crash.
        
        import random
        rng = random.Random(42)
        
        fit_matrix = {}
        mentors = [f"M{i:03d}" for i in range(1, 11)]
        startups = ["S1", "S2", "S3"]
        
        for m in mentors:
            for s in startups:
                # Score between 0.8 and 1.0
                fit_matrix[(s, m)] = 0.8 + (rng.random() * 0.2)
                
        status, sol, selected_mentors, startups, mentor_fit = self.run_pipeline(
            num_startups=3,
            num_mentors_pool=10,
            target_mentors=9,
            target_tables=3,
            fit_matrix=fit_matrix
        )
        
        # 1. Status should be Optimal
        self.assertEqual(status, "Optimal")
        
        # 2. Verify that we selected 9 mentors
        self.assertEqual(len(selected_mentors), 9)
        
        # 3. Verify OS before OC
        self.verify_os_before_oc(sol, startups, selected_mentors)
        
        # 4. Verify mentor fit quality (all scores are high, so threshold should be met)
        self.verify_mentor_fit_quality(selected_mentors, startups, mentor_fit, min_fit_threshold=0.7)

    def test_low_fit_scores(self):
        """Test where ALL mentors have low fit scores (< 0.2)."""
        print("\nRunning test_low_fit_scores...")
        import random
        rng = random.Random(42)
        
        fit_matrix = {}
        mentors = [f"M{i:03d}" for i in range(1, 11)]
        startups = ["S1", "S2", "S3"]
        
        for m in mentors:
            for s in startups:
                # Score between 0.0 and 0.2
                fit_matrix[(s, m)] = rng.random() * 0.2
                
        status, sol, selected_mentors, startups, mentor_fit = self.run_pipeline(
            num_startups=3,
            num_mentors_pool=10,
            target_mentors=9,
            target_tables=3,
            fit_matrix=fit_matrix
        )
        
        # 1. Status should be Optimal (even with low scores)
        self.assertEqual(status, "Optimal")
        
        # 2. Verify that we selected 9 mentors
        self.assertEqual(len(selected_mentors), 9)
        
        # 3. Verify OS before OC
        self.verify_os_before_oc(sol, startups, selected_mentors)
        
        # 4. Verify mentor fit quality (low threshold since all scores are low)
        self.verify_mentor_fit_quality(selected_mentors, startups, mentor_fit, min_fit_threshold=0.05)

if __name__ == '__main__':
    unittest.main()
