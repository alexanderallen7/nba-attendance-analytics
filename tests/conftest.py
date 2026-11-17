import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "attendance.db"
EXTRACT = ROOT / "data" / "processed" / "extract.csv"


@pytest.fixture(scope="session")
def con():
    if not DB.exists():
        pytest.skip("attendance.db not built; run scripts/build_db.py first")
    con = sqlite3.connect(DB)
    yield con
    con.close()


@pytest.fixture(scope="session")
def extract_path():
    if not EXTRACT.exists():
        pytest.skip("extract.csv not built; run scripts/build_db.py first")
    return EXTRACT
