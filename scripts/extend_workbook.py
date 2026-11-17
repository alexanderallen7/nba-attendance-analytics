"""Extend the Tableau seed workbook into the full dashboard workbook.

Reads tableau/seed.twb (saved by hand from Tableau Public Desktop) and
writes tableau/nba_attendance_dashboard.twb with:

- a Select Team parameter (default HOU) with all 30 teams
- calculated fields: fill rate, included (non-excluded) fill rate, a
  FIXED LOD team average, sellout %, selected-team vs league measures,
  a highlight dimension, and a year-over-year table calculation
- sheets: 3 KPI tiles, fill rate by team (sorted bar, selected team
  highlighted), fill rate by season (selected team vs other teams),
  weekday x month heatmap, win pct vs fill rate scatter, YoY bar
- a fixed-size dashboard with the parameter control

It also removes the seed's machine-local temp extract reference so the
workbook opens as a live connection to data/processed/extract.csv.

Usage:
    python scripts/extend_workbook.py
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "tableau" / "seed.twb"
OUT = ROOT / "tableau" / "nba_attendance_dashboard.twb"

DS = "federated.1pt6fmd1tboxmb1fpttad1kn09nl"

TEAMS = [
    ("ATL", "Atlanta Hawks"), ("BKN", "Brooklyn Nets"), ("BOS", "Boston Celtics"),
    ("CHA", "Charlotte Hornets"), ("CHI", "Chicago Bulls"), ("CLE", "Cleveland Cavaliers"),
    ("DAL", "Dallas Mavericks"), ("DEN", "Denver Nuggets"), ("DET", "Detroit Pistons"),
    ("GSW", "Golden State Warriors"), ("HOU", "Houston Rockets"), ("IND", "Indiana Pacers"),
    ("LAC", "LA Clippers"), ("LAL", "Los Angeles Lakers"), ("MEM", "Memphis Grizzlies"),
    ("MIA", "Miami Heat"), ("MIL", "Milwaukee Bucks"), ("MIN", "Minnesota Timberwolves"),
    ("NOP", "New Orleans Pelicans"), ("NYK", "New York Knicks"), ("OKC", "Oklahoma City Thunder"),
    ("ORL", "Orlando Magic"), ("PHI", "Philadelphia 76ers"), ("PHX", "Phoenix Suns"),
    ("POR", "Portland Trail Blazers"), ("SAC", "Sacramento Kings"), ("SAS", "San Antonio Spurs"),
    ("TOR", "Toronto Raptors"), ("UTA", "Utah Jazz"), ("WAS", "Washington Wizards"),
]

ROCKETS_RED = "#c8102e"
GRAY = "#b5b5b5"

# ----------------------------------------------------------------------------
# Parameter datasource
# ----------------------------------------------------------------------------

members = "\n".join(
    f"      <member alias='{name}' value='&quot;{abbr}&quot;' />" for abbr, name in TEAMS
)

PARAMETERS_DS = f"""  <datasource hasconnection='false' inline='true' name='Parameters' version='18.1'>
    <aliases enabled='yes' />
    <column caption='Select Team' datatype='string' name='[Parameter 1]' param-domain-type='list' role='measure' type='nominal' value='&quot;HOU&quot;'>
      <calculation class='tableau' formula='&quot;HOU&quot;' />
      <members>
{members}
      </members>
    </column>
  </datasource>
"""

# ----------------------------------------------------------------------------
# Calculated fields (added to the extract datasource)
# ----------------------------------------------------------------------------

# name -> (caption, datatype, role, type, formula, default-format or None)
CALCS = {
    "[Calculation_FillRateCalc]": (
        "Fill Rate (calc)", "real", "measure", "quantitative",
        "[attendance] / [capacity]", "p0.0%"),
    "[Calculation_IncludedFill]": (
        "Included Fill Rate", "real", "measure", "quantitative",
        "IF [excluded_flag] = 0 THEN [fill_rate] END", "p0.0%"),
    "[Calculation_TeamAvgLOD]": (
        "Team Avg Fill Rate (LOD)", "real", "measure", "quantitative",
        "{ FIXED [home_team] : AVG([Calculation_IncludedFill]) }", "p0.0%"),
    "[Calculation_SelloutPct]": (
        "Sellout % (included games)", "real", "measure", "quantitative",
        "AVG(IF [excluded_flag] = 0 THEN [sellout_flag] END)", "p0%"),
    "[Calculation_LeagueFill]": (
        "League Avg Fill Rate", "real", "measure", "quantitative",
        "AVG([Calculation_IncludedFill])", "p0.0%"),
    "[Calculation_TeamFill]": (
        "Selected Team Fill Rate", "real", "measure", "quantitative",
        "AVG(IF [home_team] = [Parameters].[Parameter 1] THEN [Calculation_IncludedFill] END)",
        "p0.0%"),
    "[Calculation_TeamSellout]": (
        "Selected Team Sellout %", "real", "measure", "quantitative",
        "AVG(IF [home_team] = [Parameters].[Parameter 1] AND [excluded_flag] = 0 THEN [sellout_flag] END)",
        "p0%"),
    "[Calculation_Highlight]": (
        "Team vs League", "string", "dimension", "nominal",
        "IF [home_team] = [Parameters].[Parameter 1] THEN &quot;Selected team&quot; ELSE &quot;Other teams&quot; END",
        None),
    # No ZN() here on purpose: 2020-21 has no included games, and ZN would
    # turn that null into 0 and paint a misleading -100% bar. The YoY sheet
    # also filters 2020-21 out of the view, so the table calc compares
    # 2021-22 against 2019-20 (stated in the sheet title).
    "[Calculation_YoY]": (
        "Fill Rate YoY % (table calc)", "real", "measure", "quantitative",
        "AVG([Calculation_IncludedFill]) / LOOKUP(AVG([Calculation_IncludedFill]), -1) - 1",
        "p0.0%"),
}


def calc_column_xml(name: str, indent: str = "      ") -> str:
    caption, dtype, role, typ, formula, fmt = CALCS[name]
    fmt_attr = f" default-format='{fmt}'" if fmt else ""
    return (
        f"{indent}<column caption='{caption}' datatype='{dtype}'{fmt_attr} "
        f"name='{name}' role='{role}' type='{typ}'>\n"
        f"{indent}  <calculation class='tableau' formula='{formula}' />\n"
        f"{indent}</column>"
    )


CALC_COLUMNS = "\n".join(calc_column_xml(n) for n in CALCS)

# ----------------------------------------------------------------------------
# Worksheet scaffolding
# ----------------------------------------------------------------------------

# Base (non-calculated) column declarations for dependency blocks.
BASE_COLS = {
    "[home_team]": "<column caption='Home Team' datatype='string' name='[home_team]' role='dimension' type='nominal' />",
    "[season]": "<column caption='Season' datatype='string' name='[season]' role='dimension' type='nominal' />",
    "[day_of_week]": "<column caption='Day Of Week' datatype='string' name='[day_of_week]' role='dimension' type='nominal' />",
    "[month]": "<column caption='Month' datatype='integer' name='[month]' role='dimension' type='quantitative' />",
    "[fill_rate]": "<column caption='Fill Rate' datatype='real' name='[fill_rate]' role='measure' type='quantitative' />",
    "[sellout_flag]": "<column caption='Sellout Flag' datatype='integer' name='[sellout_flag]' role='measure' type='quantitative' />",
    "[excluded_flag]": "<column caption='Excluded Flag' datatype='integer' name='[excluded_flag]' role='measure' type='quantitative' />",
    "[home_win_pct_entering]": "<column caption='Home Win Pct Entering' datatype='real' name='[home_win_pct_entering]' role='measure' type='quantitative' />",
}

PARAM_DEP = """      <datasource-dependencies datasource='Parameters'>
        <column caption='Select Team' datatype='string' name='[Parameter 1]' param-domain-type='list' role='measure' type='nominal' value='&quot;HOU&quot;'>
          <calculation class='tableau' formula='&quot;HOU&quot;' />
        </column>
      </datasource-dependencies>
"""


def deps(base: list[str], calcs: list[str], instances: list[str]) -> str:
    cols = [f"        {BASE_COLS[b]}" for b in base]
    cols += [calc_column_xml(c, indent="        ") for c in calcs]
    cols += [f"        {i}" for i in instances]
    inner = "\n".join(cols)
    return f"      <datasource-dependencies datasource='{DS}'>\n{inner}\n      </datasource-dependencies>\n"


def inst_none(field: str, typ: str = "nominal", suffix: str = "nk") -> str:
    return (f"<column-instance column='{field}' derivation='None' "
            f"name='[none:{field[1:-1]}:{suffix}]' pivot='key' type='{typ}' />")


def inst_avg(field: str) -> str:
    return (f"<column-instance column='{field}' derivation='Avg' "
            f"name='[avg:{field[1:-1]}:qk]' pivot='key' type='quantitative' />")


def inst_usr(field: str) -> str:
    return (f"<column-instance column='{field}' derivation='User' "
            f"name='[usr:{field[1:-1]}:qk]' pivot='key' type='quantitative' />")


def ref(instance_xml: str) -> str:
    m = re.search(r"name='(\[[^']+\])'", instance_xml)
    assert m
    return f"[{DS}].{m.group(1)}"


def worksheet(name, title, view_extra, style, panes, rows, cols, uuid,
              dep_block, with_param_dep=True) -> str:
    param = PARAM_DEP if with_param_dep else ""
    return f"""    <worksheet name='{name}'>
      <layout-options>
        <title>
          <formatted-text>
            <run bold='true'>{title}</run>
          </formatted-text>
        </title>
      </layout-options>
      <table>
        <view>
          <datasources>
            <datasource caption='extract' name='{DS}' />
          </datasources>
{param}{dep_block}{view_extra}          <aggregation value='true' />
        </view>
        <style>
{style}        </style>
        <panes>
{panes}        </panes>
        <rows>{rows}</rows>
        <cols>{cols}</cols>
      </table>
      <simple-id uuid='{{{uuid}}}' />
    </worksheet>
"""


def highlight_style() -> str:
    # NOTE: style-rule encodings reference the bare instance name, WITHOUT
    # the datasource prefix (verified against a Tableau-written workbook);
    # with the prefix the map is silently ignored and the default palette wins.
    return f"""          <style-rule element='mark'>
            <encoding attr='color' field='[none:Calculation_Highlight:nk]' type='palette'>
              <map to='{ROCKETS_RED}'>
                <bucket>&quot;Selected team&quot;</bucket>
              </map>
              <map to='{GRAY}'>
                <bucket>&quot;Other teams&quot;</bucket>
              </map>
            </encoding>
          </style-rule>
"""


def pane(mark: str, encodings: str = "") -> str:
    enc = f"            <encodings>\n{encodings}            </encodings>\n" if encodings else ""
    return f"""          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='{mark}' />
{enc}          </pane>
"""


def build_worksheets() -> str:
    sheets = []

    # --- KPI tiles -----------------------------------------------------------
    kpis = [
        ("KPI League Fill Rate", "LEAGUE AVG FILL RATE", "[Calculation_LeagueFill]",
         ["[fill_rate]", "[excluded_flag]"], ["[Calculation_IncludedFill]", "[Calculation_LeagueFill]"],
         False, "A1B2C3D4-0001-4000-9000-000000000001"),
        ("KPI Selected Team Fill Rate", "SELECTED TEAM FILL RATE", "[Calculation_TeamFill]",
         ["[fill_rate]", "[excluded_flag]", "[home_team]"],
         ["[Calculation_IncludedFill]", "[Calculation_TeamFill]"],
         True, "A1B2C3D4-0002-4000-9000-000000000002"),
        ("KPI Selected Team Sellout Pct", "SELECTED TEAM SELLOUT %", "[Calculation_TeamSellout]",
         ["[sellout_flag]", "[excluded_flag]", "[home_team]"], ["[Calculation_TeamSellout]"],
         True, "A1B2C3D4-0003-4000-9000-000000000003"),
    ]
    kpi_style = """          <style-rule element='mark'>
            <format attr='font-size' value='20' />
          </style-rule>
"""
    for name, title, measure, base, calcs, needs_param, uuid in kpis:
        mi = inst_usr(measure)
        dep = deps(base, calcs, [mi])
        p = pane("Text", f"              <text column='{ref(mi)}' />\n")
        sheets.append(worksheet(name, title, "", kpi_style, p, "", "", uuid, dep,
                                with_param_dep=needs_param))

    # --- Fill rate by team (sorted bar, highlighted) -------------------------
    team_i = inst_none("[home_team]")
    # ATTR instance referenced by the dashboard's parameter action; it must be
    # declared in a sheet's dependencies or the action's source-field cannot
    # be resolved and the workbook refuses to load.
    team_attr_i = ("<column-instance column='[home_team]' derivation='Attribute' "
                   "name='[attr:home_team:nk]' pivot='key' type='nominal' />")
    fill_i = inst_avg("[Calculation_IncludedFill]")
    hl_i = inst_none("[Calculation_Highlight]")
    dep = deps(["[home_team]", "[fill_rate]", "[excluded_flag]"],
               ["[Calculation_IncludedFill]", "[Calculation_Highlight]"],
               [team_attr_i, hl_i, fill_i, team_i])  # attr instance kept for the UI-added parameter action
    sort = (f"          <sort class='computed' column='{ref(team_i)}' "
            f"direction='DESC' using='{ref(fill_i)}' />\n")
    p = pane("Bar", f"              <color column='{ref(hl_i)}' />\n")
    sheets.append(worksheet(
        "Fill Rate by Team",
        "Average fill rate by home team, 2013-14 to 2022-23 &#8212; selected team in red",
        sort, highlight_style(), p, ref(team_i), ref(fill_i),
        "A1B2C3D4-0004-4000-9000-000000000004", dep))

    # --- Fill rate by season (selected team vs other teams) ------------------
    season_i = inst_none("[season]")
    dep = deps(["[season]", "[home_team]", "[fill_rate]", "[excluded_flag]"],
               ["[Calculation_IncludedFill]", "[Calculation_Highlight]"],
               [hl_i, fill_i, season_i])
    p = pane("Line", f"              <color column='{ref(hl_i)}' />\n")
    sheets.append(worksheet(
        "Fill Rate by Season",
        "Average fill rate by season &#8212; selected team vs all other teams. Gap = 2020-21 (COVID, excluded); 2019-20 is pre-bubble games only",
        "", highlight_style(), p, ref(fill_i), ref(season_i),
        "A1B2C3D4-0005-4000-9000-000000000005", dep))

    # --- Weekday x month heatmap --------------------------------------------
    dow_i = inst_none("[day_of_week]")
    month_i = inst_none("[month]", typ="ordinal", suffix="ok")
    dep = deps(["[day_of_week]", "[month]", "[fill_rate]", "[excluded_flag]"],
               ["[Calculation_IncludedFill]"],
               [fill_i, dow_i, month_i])
    sorts = f"""          <sort class='manual' column='{ref(dow_i)}' direction='ASC'>
            <dictionary>
              <bucket>&quot;Mon&quot;</bucket>
              <bucket>&quot;Tue&quot;</bucket>
              <bucket>&quot;Wed&quot;</bucket>
              <bucket>&quot;Thu&quot;</bucket>
              <bucket>&quot;Fri&quot;</bucket>
              <bucket>&quot;Sat&quot;</bucket>
              <bucket>&quot;Sun&quot;</bucket>
            </dictionary>
          </sort>
          <sort class='manual' column='{ref(month_i)}' direction='ASC'>
            <dictionary>
              <bucket>10</bucket>
              <bucket>11</bucket>
              <bucket>12</bucket>
              <bucket>1</bucket>
              <bucket>2</bucket>
              <bucket>3</bucket>
              <bucket>4</bucket>
            </dictionary>
          </sort>
"""
    p = pane("Square",
             f"              <color column='{ref(fill_i)}' />\n"
             f"              <text column='{ref(fill_i)}' />\n")
    sheets.append(worksheet(
        "Weekday Month Heatmap",
        "Average fill rate by day of week and month (Oct&#8211;Apr, season order)",
        sorts, "", p, ref(dow_i), ref(month_i),
        "A1B2C3D4-0006-4000-9000-000000000006", dep, with_param_dep=False))

    # --- Win pct vs fill rate scatter (team-season points) -------------------
    win_i = inst_avg("[home_win_pct_entering]")
    dep = deps(["[home_team]", "[season]", "[home_win_pct_entering]",
                "[fill_rate]", "[excluded_flag]"],
               ["[Calculation_IncludedFill]", "[Calculation_Highlight]"],
               [hl_i, fill_i, win_i, team_i, season_i])
    enc = (f"              <color column='{ref(hl_i)}' />\n"
           f"              <lod column='{ref(team_i)}' />\n"
           f"              <lod column='{ref(season_i)}' />\n")
    p = pane("Circle", enc)
    sheets.append(worksheet(
        "Win Pct vs Fill Rate",
        "Each dot is one team-season: average win % entering games vs average fill rate",
        "", highlight_style(), p, ref(fill_i), ref(win_i),
        "A1B2C3D4-0007-4000-9000-000000000007", dep))

    # --- YoY table-calc bar (workbook only, not on dashboard) ----------------
    yoy_i = inst_usr("[Calculation_YoY]")
    dep = deps(["[season]", "[fill_rate]", "[excluded_flag]"],
               ["[Calculation_IncludedFill]", "[Calculation_YoY]"],
               [yoy_i, season_i])
    # Exclude 2020-21 from the view entirely (no included games), so the
    # table calc's LOOKUP(-1) for 2021-22 lands on 2019-20.
    yoy_filter = f"""          <filter class='categorical' column='{ref(season_i)}'>
            <groupfilter function='except'>
              <groupfilter function='level-members' level='[none:season:nk]' />
              <groupfilter function='member' level='[none:season:nk]' member='&quot;2020-21&quot;' />
            </groupfilter>
          </filter>
"""
    p = pane("Bar")
    sheets.append(worksheet(
        "Fill Rate YoY Change",
        "League average fill rate &#8212; change vs previous season (2021-22 compares to 2019-20; 2020-21 excluded, COVID)",
        yoy_filter, "", p, ref(yoy_i), ref(season_i),
        "A1B2C3D4-0008-4000-9000-000000000008", dep, with_param_dep=False))

    # NOTE: a <edit-parameter-action> block was attempted here but Tableau
    # rejects the hand-written version even when modeled byte-for-byte on a
    # Tableau-authored workbook; the parameter action is added through the UI
    # instead (see BUILD_NOTES.md "Finishing steps").
    return "  <worksheets>\n" + "".join(sheets) + "  </worksheets>\n"


# ----------------------------------------------------------------------------
# Dashboard actions (clicking a team's bar sets the Select Team parameter;
# structure copied from a Tableau-written workbook's edit-parameter-action)
# ----------------------------------------------------------------------------

ACTIONS = f"""  <actions>
    <datasources>
      <datasource name='Parameters' />
    </datasources>
    <datasource-dependencies datasource='Parameters'>
      <column caption='Select Team' datatype='string' name='[Parameter 1]' param-domain-type='list' role='measure' type='nominal' value='&quot;HOU&quot;'>
        <calculation class='tableau' formula='&quot;HOU&quot;' />
      </column>
    </datasource-dependencies>
    <edit-parameter-action caption='Select team from bar' name='[Action1_A1B2C3D4E5F60718293041526374850F]'>
      <activation type='on-select' />
      <source dashboard='NBA Home Attendance' type='sheet' worksheet='Fill Rate by Team' />
      <agg-type type='attr' />
      <clear-option type='do-nothing' value='s:LROOT:' />
      <params>
        <param name='source-field' value='[{DS}].[attr:home_team:nk]' />
        <param name='target-parameter' value='[Parameters].[Parameter 1]' />
      </params>
    </edit-parameter-action>
  </actions>
"""

# ----------------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------------

DASHBOARD = """  <dashboards>
    <dashboard name='NBA Home Attendance'>
      <style />
      <size maxheight='900' maxwidth='1100' minheight='900' minwidth='1100' sizing-mode='fixed' />
      <zones>
        <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>
          <zone h='7000' id='2' type-v2='text' w='100000' x='0' y='0'>
            <formatted-text>
              <run bold='true' fontsize='16'>What drives NBA home attendance?</run>
              <run fontcolor='#666666' fontsize='10'>&#10;Regular seasons 2013-14 to 2022-23 &#183; pick a team with the Select Team control &#183; associations only, not causal estimates</run>
            </formatted-text>
          </zone>
          <zone h='12000' id='4' name='KPI League Fill Rate' show-title='true' w='22000' x='0' y='7000'>
            <layout-cache cell-count-w='1' type-h='fixed' type-w='cell' />
            <zone-style>
              <format attr='margin' value='6' />
            </zone-style>
          </zone>
          <zone h='12000' id='5' name='KPI Selected Team Fill Rate' show-title='true' w='22000' x='22000' y='7000'>
            <layout-cache cell-count-w='1' type-h='fixed' type-w='cell' />
            <zone-style>
              <format attr='margin' value='6' />
            </zone-style>
          </zone>
          <zone h='12000' id='6' name='KPI Selected Team Sellout Pct' show-title='true' w='22000' x='44000' y='7000'>
            <layout-cache cell-count-w='1' type-h='fixed' type-w='cell' />
            <zone-style>
              <format attr='margin' value='6' />
            </zone-style>
          </zone>
          <zone h='12000' id='7' param='[Parameters].[Parameter 1]' type-v2='paramctrl' w='34000' x='66000' y='7000'>
            <zone-style>
              <format attr='margin' value='6' />
            </zone-style>
          </zone>
          <zone h='37000' id='9' name='Fill Rate by Team' w='50000' x='0' y='19000'>
            <zone-style>
              <format attr='margin' value='6' />
            </zone-style>
          </zone>
          <zone h='37000' id='10' name='Fill Rate by Season' w='50000' x='50000' y='19000'>
            <zone-style>
              <format attr='margin' value='6' />
            </zone-style>
          </zone>
          <zone h='37000' id='12' name='Weekday Month Heatmap' w='50000' x='0' y='56000'>
            <zone-style>
              <format attr='margin' value='6' />
            </zone-style>
          </zone>
          <zone h='37000' id='13' name='Win Pct vs Fill Rate' w='50000' x='50000' y='56000'>
            <zone-style>
              <format attr='margin' value='6' />
            </zone-style>
          </zone>
          <zone h='7000' id='15' type-v2='text' w='100000' x='0' y='93000'>
            <formatted-text>
              <run bold='true' fontsize='9'>How to read this: </run>
              <run fontsize='9'>Fill rate = reported attendance &#247; listed arena capacity, capped at 100%. Sellout = attendance at or above listed capacity. Win % entering = team record over that season&#8217;s earlier games only. Excluded: 2019-20 bubble games, all of 2020-21 (COVID), and international/alternate-venue games. Attendance is team-reported (tickets distributed, not turnstile counts). Sources: Kaggle NBA Database (wyattowalsh); arena capacities from Wikipedia, cited per row in the repo. Associations only &#8212; not causal estimates.</run>
            </formatted-text>
            <zone-style>
              <format attr='margin' value='8' />
            </zone-style>
          </zone>
        </zone>
      </zones>
      <simple-id uuid='{A1B2C3D4-0009-4000-9000-000000000009}' />
    </dashboard>
  </dashboards>
"""

SHEET_NAMES = [
    "KPI League Fill Rate", "KPI Selected Team Fill Rate",
    "KPI Selected Team Sellout Pct", "Fill Rate by Team",
    "Fill Rate by Season", "Weekday Month Heatmap",
    "Win Pct vs Fill Rate", "Fill Rate YoY Change",
]


def _sheet_window(name: str, idx: int) -> str:
    return f"""    <window class='worksheet' name='{name}'>
      <cards>
        <edge name='left'>
          <strip size='160'>
            <card type='pages' />
            <card type='filters' />
            <card type='marks' />
          </strip>
        </edge>
        <edge name='top'>
          <strip size='2147483647'>
            <card type='columns' />
          </strip>
          <strip size='2147483647'>
            <card type='rows' />
          </strip>
          <strip size='2147483647'>
            <card type='title' />
          </strip>
        </edge>
      </cards>
      <simple-id uuid='{{A1B2C3D4-0100-4000-9000-0000000001{idx:02d}}}' />
    </window>
"""


WINDOWS = (
    "  <windows saved-dpi-scale-factor='1.25' source-height='37'>\n"
    + "".join(_sheet_window(n, i) for i, n in enumerate(SHEET_NAMES))
    + """    <window class='dashboard' maximized='true' name='NBA Home Attendance'>
      <viewpoints>
"""
    + "".join(
        f"        <viewpoint name='{n}'>\n          <zoom type='entire-view' />\n        </viewpoint>\n"
        for n in SHEET_NAMES if n != "Fill Rate YoY Change"
    )
    + """      </viewpoints>
      <active id='1' />
      <simple-id uuid='{A1B2C3D4-0010-4000-9000-000000000010}' />
    </window>
  </windows>
"""
)

# ----------------------------------------------------------------------------
# Assembly
# ----------------------------------------------------------------------------

def main() -> None:
    xml = SEED.read_text(encoding="utf-8")

    # 1. Drop the machine-local temp extract reference (live CSV remains).
    xml = re.sub(r"[ \t]*<extract count=.*?</extract>\n", "", xml, flags=re.S)
    xml = re.sub(
        r"[ \t]*<properties context='extract'>.*?</properties>\n", "", xml, flags=re.S)

    # 2. Drop the stale thumbnail.
    xml = re.sub(r"[ \t]*<thumbnails>.*?</thumbnails>\n", "", xml, flags=re.S)

    # 3. Insert the Parameters datasource before the extract datasource.
    anchor = "  <datasources>\n"
    assert anchor in xml
    xml = xml.replace(anchor, anchor + PARAMETERS_DS, 1)

    # 4. Insert calculated fields after the last plain column definition.
    anchor = ("      <column caption='Sellout Flag' datatype='integer' "
              "name='[sellout_flag]' role='measure' type='quantitative' />")
    assert anchor in xml
    xml = xml.replace(anchor, anchor + "\n" + CALC_COLUMNS, 1)

    # 5. Replace the worksheets section.
    xml = re.sub(r"  <worksheets>.*?</worksheets>\n", build_worksheets(), xml,
                 flags=re.S)

    # 6. Replace the windows section and add the dashboard before it.
    xml = re.sub(r"  <windows .*?</windows>\n", DASHBOARD + WINDOWS, xml, flags=re.S)

    # 7. Validate well-formedness.
    ET.fromstring(xml)

    OUT.write_text(xml, encoding="utf-8")
    print(f"wrote {OUT} ({len(xml):,} bytes), XML is well-formed")


if __name__ == "__main__":
    main()
