"""Package the generated workbook as a self-contained .twbx with a Hyper extract.

Tableau Public only works with extract-based data sources, so this script:
 1. builds data/processed/extract.hyper from extract.csv (schema Extract,
    table Extract - the layout Tableau itself uses)
 2. rewrites the generated .twb so its data source carries an <extract>
    definition pointing at the packaged hyper file
 3. zips the .twb and the hyper file into tableau/nba_attendance_dashboard.twbx

Run after scripts/extend_workbook.py:
    python scripts/package_twbx.py
"""

from __future__ import annotations

import csv
import datetime
import zipfile
from pathlib import Path

from tableauhyperapi import (
    Connection, CreateMode, HyperProcess, NOT_NULLABLE, NULLABLE, SqlType,
    TableDefinition, TableName, Telemetry,
)

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "processed" / "extract.csv"
HYPER_PATH = ROOT / "data" / "processed" / "extract.hyper"
TWB_PATH = ROOT / "tableau" / "nba_attendance_dashboard.twb"
TWBX_PATH = ROOT / "tableau" / "nba_attendance_dashboard.twbx"

# column -> (SqlType factory, python converter)
INT = (SqlType.big_int(), int)
REAL = (SqlType.double(), float)
TEXT = (SqlType.text(), str)
DATE = (SqlType.date(), lambda s: datetime.date.fromisoformat(s))

COLUMNS = {
    "game_id": INT,
    "game_date": DATE,
    "season": TEXT,
    "season_start_year": INT,
    "home_team": TEXT,
    "away_team": TEXT,
    "arena": TEXT,
    "attendance": INT,
    "capacity": INT,
    "fill_rate": REAL,
    "fill_rate_raw": REAL,
    "sellout_flag": INT,
    "day_of_week": TEXT,
    "month": INT,
    "home_win_pct_entering": REAL,
    "opp_win_pct_entering": REAL,
    "home_back_to_back": INT,
    "excluded_flag": INT,
    "excluded_reason": TEXT,
}

SEED_PATH = ROOT / "tableau" / "seed.backup.twb"


def seed_extract_block() -> str:
    """Reuse the seed workbook's own <extract> block (with its complete
    per-column metadata records), repointing dbname at the packaged hyper."""
    import re

    seed = SEED_PATH.read_text(encoding="utf-8")
    m = re.search(r"[ \t]*<extract count=.*?</extract>\n", seed, flags=re.S)
    assert m, "no <extract> block found in seed backup"
    block = m.group(0)
    block = re.sub(r"dbname='[^']*'", "dbname='Data/extract/extract.hyper'", block)
    return block


def build_hyper() -> None:
    table = TableDefinition(
        table_name=TableName("Extract", "Extract"),
        columns=[
            TableDefinition.Column(name, sqltype, NULLABLE)
            for name, (sqltype, _) in COLUMNS.items()
        ],
    )
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(hyper.endpoint, str(HYPER_PATH), CreateMode.CREATE_AND_REPLACE) as con:
            con.catalog.create_schema_if_not_exists("Extract")
            con.catalog.create_table(table)
            with open(CSV_PATH, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = []
                for r in reader:
                    rows.append([
                        conv(r[name]) if r[name] != "" else None
                        for name, (_, conv) in COLUMNS.items()
                    ])
            with con.execute_query(f"SELECT COUNT(*) FROM {table.table_name}") as res:  # noqa: S608
                pass
            from tableauhyperapi import Inserter
            with Inserter(con, table) as inserter:
                inserter.add_rows(rows)
                inserter.execute()
            with con.execute_query(f"SELECT COUNT(*) FROM {table.table_name}") as res:  # noqa: S608
                n = list(res)[0][0]
    print(f"built {HYPER_PATH.name}: {n} rows")


def build_twbx() -> None:
    xml = TWB_PATH.read_text(encoding="utf-8")
    anchor = "      <layout dim-ordering='alphabetic'"
    assert anchor in xml, "layout anchor not found in twb"
    assert "<extract " not in xml, "twb already has an extract block"
    xml = xml.replace(anchor, seed_extract_block() + anchor, 1)
    # restore the extract entry in the object graph so the data model
    # knows the extract relation for the table object
    og_anchor = """            <properties context=''>"""
    assert og_anchor in xml
    xml = xml.replace(
        "          </object>",
        """            <properties context='extract'>
              <relation name='Extract' table='[Extract].[Extract]' type='table' />
            </properties>
          </object>""",
        1,
    )
    with zipfile.ZipFile(TWBX_PATH, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("nba_attendance_dashboard.twb", xml)
        z.write(HYPER_PATH, "Data/extract/extract.hyper")
    print(f"wrote {TWBX_PATH.name} ({TWBX_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build_hyper()
    build_twbx()
