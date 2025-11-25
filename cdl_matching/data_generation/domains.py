# cdl_matching/data_generation/domains.py
from typing import List, Set
from ..config import DEFAULT_DOMAINS

def get_default_domains() -> List[str]:
    return list(DEFAULT_DOMAINS)

def as_domain_set(*xs: str) -> Set[str]:
    return set(xs)
