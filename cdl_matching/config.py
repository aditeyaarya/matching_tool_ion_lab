# cdl_matching/config.py

# Toy data knobs
NUM_TABLES_DEFAULT = 10
NUM_STARTUPS_DEFAULT = 10
MENTORS_PER_TABLE_DEFAULT = 3

# Mentor seating bounds (NEW)
MIN_MENTORS_PER_TABLE = 2
MAX_MENTORS_PER_TABLE = 4

# Optional: default global mentor pool size (NEW)
NUM_MENTORS_POOL_DEFAULT = None

# Domains for matching
DEFAULT_DOMAINS = [
    "AI", "FinTech", "Healthcare", "Marketing", "Robotics",
    "ClimateTech", "Retail", "Education", "Biotech", "Cybersecurity",
]

# OS/OC load caps per mentor
MAX_OS_PER_MENTOR = 3
MAX_OC_PER_MENTOR = 3

# Random seed for reproducible toy sets
DEFAULT_SEED = 42

# -----------------------------------------------------------
# Backwards-compatibility for older scheduling modules
# -----------------------------------------------------------

# Old interactive_repair.py expects table-level caps.
# We approximate them using mentor-level caps or set to a safe high default.

MAX_OS_PER_TABLE = MAX_OS_PER_MENTOR * 3   # or simply a big number like 99
MAX_OC_PER_TABLE = MAX_OC_PER_MENTOR * 3

# Path to fit-scores CSV for toy dataset generation (if any)
FIT_SCORES_CSV_PATH = "cdl_matching/data_generation/fit_matrix.csv"
