# CDL Matching & Scheduling Joint MILP System

A sophisticated Mixed Integer Linear Programming (MILP) optimization tool for jointly matching mentors with startups (for OS and OC roles) and simultaneously scheduling their meetings across multiple Small Group Meetings (SGMs). The solver optimally assigns roles and schedules meetings while respecting all operational constraints.

## Overview

The system addresses a multi-objective optimization problem:
1. **Assigns Mentors to Startups:** Chooses Operational Support (OS) and Operational Coach (OC) mentors for each startup to maximize total fit scores.
2. **Assigns Mentors to Tables:** Distributes mentors across physical/virtual tables dynamically.
3. **Schedules Meetings:** Dictates which startup visits which table in which SGM (time slot).
4. **Denormalizes output:** Post-processes the anonymous schedules by mapping IDs back to human-readable mentor and startup names.

## Key Features

- **Optimal Joint Selection & Scheduling:** Instead of sequentially assigning roles and then scheduling, the system uses a Joint MILP formulation to handle selection and scheduling simultaneously via Python's `pulp` and CBC solver.
- **Constraints Satisfaction:** Validates that:
  - Startup visits each table at most once across the day.
  - OS meetings occur in SGMs 1 or 2, and OC meetings in SGMs 2 or 3.
  - OS meetings always occur *before* OC meetings for each startup.
  - Tables maintain configurable min/max capacities (e.g., 2 to 5 mentors).
  - Configurable penalties for overloading tables beyond preferred capacities.
- **Automated Denormalization:** Integrates an automated script (`mapping.py`) to map anonymous internal pseudo IDs (e.g., `MENTOR_001`) back to their real names via JSON lookup files.

## Project Structure

```
MILP_matching_tool/
├── cdl_matching/
│   ├── config.py                 # Configuration constraints limits (e.g. max OS per mentor)
│   ├── models.py                 # Core Data models (Mentor, Startup)
│   ├── input_data/               # Fit matrices and naming maps (JSON)
│   └── scheduling/
│       ├── joint_milp.py         # MILP constraint formulation and solver setup
│       └── post_solve_export.py  # Utility functions to build output CSVs
├── data/
│   ├── outputs/                  # Raw anonymous CSVs exported by run_joint_milp.py
│   └── final_results/            # Combined & Denormalized CSVs exported by mapping.py
├── mapping.py                    # Maps pseudo IDs to real names to generate final results
├── run_joint_milp.py             # Main entrypoint script to run the joint solver
└── README.md                     # You're reading this!
```

## Prerequisites

Install the required Python packages:
```bash
pip install pulp pandas
```

## Running the Optimization

### 1. Solve the Problem

To run the joint formulation algorithm and generate the schedule:
```bash
python3 run_joint_milp.py
```
* **Process:** This script imports fit data (`cdl_matching/input_data/S3_final_fit_shift2.csv`), sets up the startup/mentor arrays, and configures algorithmic constraints such as table counts and exclusion rules.
* **Output:** It populates the `data/outputs/` directory with intermediate anonymous solution files (e.g. full schedule, tables, mentor assignments).
* **Configuration:** Edit variables like `EXCLUDE_FROM_OS_OC` and `EXCLUDE_FROM_ALGO` inside `run_joint_milp.py` to prevent specific mentors from being assigned roles.

### 2. Generate Human Readable Outputs

After generating the optimal schedule mappings via the MILP execution, the results primarily use generic ids. Run the post-processing mapping script to pair them with their actual names:

```bash
python3 mapping.py
```
* **Process:** `mapping.py` pairs the generated outputs against `S3_mentors_available.json` and `S3_startups_available.json` maps located typically in the `input_data/` directory.
* **Output:** This generates the final clean, denormalized CSVs ready for operational reporting in `data/final_results/`.

## Key Scheduling Constraints Details

- **Time Windows:** SGMs consists of exactly 3 slots. OS meetings can be held in either SGM 1 or 2, while OC meetings in SGM 2 or 3.
- **Table Capacity:** By default, each table must hold between 2 to 5 Mentors. 
- **Seating Limitation:** A single Startup can only visit a single table per SGM, and cannot sit at the same table more than once throughout the day.
- **Exclusion Check:** OS and OC mentors for the exact same startup must inherently sit at different tables.

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

