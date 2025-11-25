# cdl_matching/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Set, Optional


@dataclass
class Mentor:
    id: str
    name: str
    table_id: int
    domains: Set[str]
    can_be_os: bool = True
    can_be_oc: bool = True
    conflicts: Set[str] = field(default_factory=set)  # startup IDs or domains, up to you


@dataclass
class Startup:
    id: str
    name: str
    domain: str
    os_id: Optional[str] = None   # OS mentor ID
    oc_id: Optional[str] = None   # OC mentor ID
