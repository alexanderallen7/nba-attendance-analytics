# Data dictionary — `data/processed/extract.csv`

One row per NBA regular-season game, seasons 2013-14 through 2022-23
(11,979 rows). Built by `scripts/build_db.py` from the Kaggle "NBA
Database" (wyattowalsh/basketball) plus two curated reference tables.

| Column | Type | Description |
|---|---|---|
| `game_id` | text | NBA game id from the source database (e.g. `0021300579`). |
| `game_date` | date | Game date (YYYY-MM-DD). |
| `season` | text | Season label, e.g. `2013-14`. |
| `season_start_year` | int | Season start year, e.g. `2013` for 2013-14. |
| `home_team` | text | Home team's three-letter abbreviation (designated home team for neutral-site games). |
| `away_team` | text | Away team's three-letter abbreviation. |
| `arena` | text | Home arena for that team and season, from `data/arena_capacity.csv`. Null for neutral-site/alternate-venue games. |
| `attendance` | int | Reported attendance from the source's `game_info` table. Team-reported (tickets distributed, not turnstile count). Null when the source has no value or reports 0. |
| `capacity` | int | Listed basketball capacity of the home arena for that season era, from `data/arena_capacity.csv` (every row cited). Null for neutral-site/alternate-venue games. |
| `fill_rate` | real | `attendance / capacity`, **capped at 1.0**. Null when attendance or capacity is null. |
| `fill_rate_raw` | real | Uncapped `attendance / capacity`; can exceed 1 because teams report standing room and suite attendance above listed capacity (max 1.13 in this window). |
| `sellout_flag` | 0/1 | 1 when `attendance >= capacity`. |
| `day_of_week` | text | `Mon` … `Sun`, from the game date. |
| `month` | int | Calendar month 1-12. |
| `home_win_pct_entering` | real | Home team's win percentage over PRIOR games of the same regular season only. Null for the team's season opener (no prior games). No information from the current game or later games is used. |
| `opp_win_pct_entering` | real | Same, for the visiting team. |
| `home_back_to_back` | 0/1 | 1 when the home team also played the previous calendar day (home or away). |
| `excluded_flag` | 0/1 | 1 when the row should be left out of fill-rate analysis. |
| `excluded_reason` | text | `covid_bubble` (2019-20 games on/after 2020-07-30), `covid_limited_capacity` (entire 2020-21 season), `international_game` (London/Mexico City/Paris), `alternate_venue` (San Antonio's 2023 Alamodome game). Null when not excluded. |

Notes

- Attendance above capacity is kept in `fill_rate_raw` and documented in
  `DATA_QUALITY.md`; `fill_rate` is the capped analysis column.
- Entering-record fields are leakage-tested by `tests/test_no_leakage.py`.
- The companion file `data/processed/regression_results.csv` holds model
  output, and `data/processed/season_trend.csv` the season-level league
  vs. Rockets trend table (see `analysis/`).
