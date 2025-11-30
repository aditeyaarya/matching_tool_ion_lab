# cdl_matching/data_generation/fit_loader.py
import csv

def load_fit_scores(path):
    """
    Reads a CSV of shape:
        ,S1,S2,S3
        M001,0.8,0.3,0.5
        ...

    Returns:
        mentor_ids: List[str]
        fit_scores: Dict[str, Dict[str, float]]
    """
    with open(path, "r", newline="") as f:
        rows = list(csv.reader(f))

    startup_ids = [c.strip() for c in rows[0][1:]]
    mentor_ids = []
    fit = {}

    for row in rows[1:]:
        mid = row[0].strip()
        mentor_ids.append(mid)
        fit[mid] = {
            startup_ids[i]: float(row[i+1])
            for i in range(len(startup_ids))
        }

    return mentor_ids, fit