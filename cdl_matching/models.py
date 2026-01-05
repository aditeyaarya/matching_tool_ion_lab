from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Mentor:
    id: str
    name: str
    can_be_os: bool = True
    can_be_oc: bool = True
    table_id: Optional[int] = None  # optional: set post-solve if you want


@dataclass
class Startup:
    id: str
    name: str
    os_id: Optional[str] = None  # set post-solve
    oc_id: Optional[str] = None  # set post-solve
