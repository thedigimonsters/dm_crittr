# crittr/ui/timeline/model.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
import uuid

@dataclass
class Layer:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Layer"
    order: int = 0  # 0 = top