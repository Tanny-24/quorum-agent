from __future__ import annotations

import pytest

from quorum.data.loader import seed_store
from quorum.persistence.memory import MemoryStore


@pytest.fixture
def store() -> MemoryStore:
    return seed_store(MemoryStore())
