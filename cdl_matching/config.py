# cdl_matching/config.py

# Defaults for running the solver
NUM_TABLES_DEFAULT = 9
NUM_SGMS_DEFAULT = 3

# Mentor seating bounds (solver bounds)
MIN_MENTORS_PER_TABLE = 2
MAX_MENTORS_PER_TABLE = 5

# OS/OC load caps per mentor
MAX_OS_PER_MENTOR = 3
MAX_OC_PER_MENTOR = 3

# Optional: reproducibility for toy/test instances
DEFAULT_SEED = 42

# Optional: default fit-score path IF you load from CSV
FIT_SCORES_CSV_PATH = "cdl_matching/data/final_fit_scores_session_2.csv"
