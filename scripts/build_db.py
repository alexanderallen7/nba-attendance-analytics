"""Build the processed database and Tableau extract.

Steps:
 1. Open (or create) data/processed/attendance.db
 2. Attach the raw Kaggle SQLite database read-only as `raw`
 3. Load the reference CSVs (arena_capacity, neutral_site_games)
 4. Run sql/01..03 to build game_base, team_entering, game_features
 5. Run sql/04_extract.sql and write data/processed/extract.csv

Usage:
    python scripts/build_db.py [path/to/nba.sqlite]

If no path is given, the script looks for data/raw/nba.sqlite, then for
the kagglehub cache under data/raw/kagglehub/.
"""

from __future__ import annotations

import csv
import glob
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
DB_PATH = PROCESSED / "attendance.db"
EXTRACT_PATH = PROCESSED / "extract.csv"


def find_raw_db() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    direct = ROOT / "data" / "raw" / "nba.sqlite"
    if direct.exists():
        return direct
    hits = glob.glob(str(ROOT / "data" / "raw" / "kagglehub" / "**" / "nba.sqlite"), recursive=True)
    if hits:
        return Path(hits[0])
    sys.exit(
        "Could not find nba.sqlite. Download the Kaggle 'NBA Database' "
        "(wyattowalsh/basketball) and place nba.sqlite in data/raw/, or pass its path."
    )


def load_csv(con: sqlite3.Connection, table: str, path: Path, int_cols: set[str]) -> None:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
        assert cols, f"{path} has no header"
        con.execute(f"DROP TABLE IF EXISTS {table}")
        con.execute(f"CREATE TABLE {table} ({', '.join(cols)})")
        rows = [
            [int(r[c]) if c in int_cols and r[c] != "" else (r[c] or None) for c in cols]
            for r in reader
        ]
    con.executemany(
        f"INSERT INTO {table} VALUES ({', '.join('?' * len(cols))})", rows
    )
    print(f"loaded {table}: {len(rows)} rows")


def main() -> None:
    raw = find_raw_db()
    print(f"raw database: {raw}")
    PROCESSED.mkdir(parents=True, exist_ok=True)

    # uri=True on the main connection enables URI filenames for ATTACH too,
    # letting us attach the raw database strictly read-only.
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=rwc", uri=True)
    con.execute(f"ATTACH DATABASE 'file:{raw.as_posix()}?mode=ro' AS raw")

    load_csv(con, "arena_capacity", ROOT / "data" / "arena_capacity.csv",
             int_cols={"first_season", "last_season", "capacity"})
    load_csv(con, "neutral_site_games", ROOT / "data" / "neutral_site_games.csv",
             int_cols=set())

    for name in ("01_game_base.sql", "02_team_entering.sql", "03_game_features.sql"):
        script = (ROOT / "sql" / name).read_text(encoding="utf-8")
        con.executescript(script)
        print(f"ran {name}")

    extract_sql = (ROOT / "sql" / "04_extract.sql").read_text(encoding="utf-8")
    cur = con.execute(extract_sql)
    headers = [d[0] for d in cur.description]
    with open(EXTRACT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        n = 0
        for row in cur:
            writer.writerow(row)
            n += 1
    print(f"wrote {EXTRACT_PATH.name}: {n} rows")

    con.commit()
    con.close()


if __name__ == "__main__":
    main()
