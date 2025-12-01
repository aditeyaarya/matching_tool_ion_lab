# Scheduling System

A sophisticated optimization system for matching mentors with startups and scheduling their meetings across multiple time slots, ensuring optimal fit while respecting operational constraints.

## Overview

This system solves a complex multi-objective optimization problem:
1. **Select** the best subset of mentors from a larger pool
2. **Assign** mentors to tables to maximize startup-mentor fit
3. **Schedule** meetings across time slots (SGMs) while respecting constraints
4. **Verify** that all startups receive high-quality mentorship

## Key Features

- **Optimal Mentor Selection**: Heuristic-based selection to minimize costs while maximizing fit
- **MILP Scheduling**: Mixed Integer Linear Programming for optimal time slot assignments
-  **Constraint Satisfaction**: Ensures OS meetings before OC meetings, table capacity limits, etc.
-  **Comprehensive Verification**: Multi-level checks for quality and correctness
- **Extensive Testing**: pytest-based test suite with multiple scenarios

## Quick Start

### Prerequisites
```bash
pip install pulp pandas pytest
```

### Run the Main Algorithm
```bash
python3 run_toy.py
```

This will:
1. Load mentor-startup fit scores from `cdl_matching/data_generation/fit_matrix.csv`
2. Select the top 9 mentors from 15
3. Assign them to 3 tables
4. Schedule 3 meetings per startup across 3 time slots (SGMs)
5. Display comprehensive diagnostics and verification

### Run Tests
```bash
pytest tests/test_scenarios.py -v
```

## Project Structure

```
matching_tool_ion_lab/
├── cdl_matching/
│   ├── config.py                    # Configuration constants
│   ├── models.py                    # Data models (Mentor, Startup)
│   ├── data_generation/
│   │   ├── fit_matrix.csv          # Mentor-startup fit scores (0-1)
│   │   ├── toy_dataset.py          # Data generation utilities
│   │   ├── mentor_factory.py       # Mentor creation logic
│   │   └── startup_factory.py      # Startup creation & OS/OC assignment
│   ├── optimization/
│   │   └── selector.py             # MILP-based mentor selector (experimental)
│   └── scheduling/
│       ├── milp_model.py           # MILP scheduling model
│       ├── solve.py                # Scheduling solver
│       ├── diagnostics.py          # Feasibility checks
│       └── sets_and_params.py      # Helper utilities
├── tests/
│   └── test_scenarios.py           # Comprehensive test suite
├── run_toy.py                       # Main execution script
├── run_tests.py                     # Ad-hoc test runner
└── README.md                        # This file
```

## Algorithm Workflow

### Phase 1: Mentor Selection
- **Input**: Pool of N mentors, M startups
- **Output**: Top K mentors (e.g., 9 from 15)
- **Method**: Heuristic scoring based on sum of top-5 fit scores per mentor

### Phase 2: Table Assignment
- **Input**: Selected mentors
- **Output**: Mentors distributed across T tables (e.g., 3 tables)
- **Method**: Round-robin assignment for even distribution

### Phase 3: OS/OC Assignment
- **Input**: Mentors, startups, fit scores
- **Output**: Each startup assigned an OS (Operational Support) and OC (Operational Coach) mentor
- **Constraints**:
  - OS = Best-fit mentor for the startup
  - OC = 2nd-best mentor on a *different* table
  - OS and OC must be on different tables

### Phase 4: Scheduling (MILP)
- **Input**: Startups, tables, time slots (SGMs), OS/OC assignments
- **Output**: Optimal schedule assigning each startup to tables across SGMs
- **Objective**: Maximize total fit scores
- **Constraints**:
  - Each startup meets at exactly 3 tables
  - Each table hosts max 1 meeting per SGM
  - OS meeting must occur before OC meeting
  - OS meetings only in SGM 1-2
  - OC meetings only in SGM 2-3

### Phase 5: Verification
- OS meetings occur before OC meetings
- All startups have access to high-fit mentors
- No structural capacity violations

## Understanding the Output

### Mentor-Startup Fit Matrix
```
    M001  M003  M004  ...
S1  0.78  0.89  0.33  ...
S2  0.22  0.19  0.83  ...
```
Values range from 0 (poor fit) to 1 (perfect fit).

### Table-Startup Fit Matrix
```
    Table 1  Table 2  Table 3
S1     0.94     0.89     0.76
```
For each (Startup, Table), shows the **best** mentor fit at that table.

### Schedule
```
=== SGM 1 ===
Table 1: S2  ← S2 meets their OS mentor at Table 1
Table 2: S3
Table 3: S1
```

## Configuration

### Customize Fit Scores
Edit `cdl_matching/data_generation/fit_matrix.csv`:
```csv
,S1,S2,S3
M001,0.78,0.22,0.81
M002,0.41,0.74,0.58
...
```

### Adjust Parameters
In `run_toy.py`:
```python
target_mentors = 9      # Number of mentors to select
target_tables = 3       # Number of tables
num_sgms = 3           # Number of time slots
```

## Testing

The test suite (`tests/test_scenarios.py`) includes:

1. **test_one_startup_many_mentors**: Verifies selection works with abundant mentors
2. **test_two_startups_few_mentors**: Tests edge case with tight constraints
3. **test_high_fit_scores**: All mentors have high fit (0.8-1.0)
4. **test_low_fit_scores**: All mentors have low fit (0.0-0.2)

Each test verifies:
- Solver finds optimal solution
- OS meetings occur before OC meetings
-  Each startup has access to quality mentors

## Key Constraints

| Constraint | Description |
|------------|-------------|
| **3 Mentors/Table** | Each table has exactly 3 mentors |
| **3 Meetings/Startup** | Each startup attends 3 tables |
| **OS Before OC** | OS meeting must occur in an earlier SGM than OC |
| **Different Tables** | OS and OC mentors must be on different tables |
| **Capacity** | Each table hosts max 1 meeting per SGM |
| **Time Windows** | OS in SGM 1-2, OC in SGM 2-3 |

## Troubleshooting

### "Structural Infeasibility" Error
This occurs when OS/OC assignments create impossible scheduling constraints.

**Common causes**:
- Too many OS mentors clustered on one table
- Not enough time slots for required meetings

**Solutions**:
- Increase number of tables
- Adjust OS/OC selection logic
- Increase number of SGMs

### "Infeasible" Solver Status
The MILP couldn't find a valid schedule.

**Solutions**:
- Check fit matrix for extreme values
- Verify mentor distribution across tables
- Review diagnostic output for capacity issues


## Contributing

When adding new features:
1. Add tests to `tests/test_scenarios.py`
2. Update this README
3. Run `pytest tests/test_scenarios.py -v` to verify

