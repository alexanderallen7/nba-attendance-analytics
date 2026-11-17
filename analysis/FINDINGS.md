# Findings

Based on 9,671 regular-season home games (2013-14 through 2022-23) with
complete fields, excluding COVID-affected and neutral-site games. The OLS
model explains R² = 0.167 of game-to-game variation in fill rate
(attendance ÷ capacity, capped at 1.0). Full coefficient table:
`data/processed/regression_results.csv`. **All results are associations,
not causal estimates.**

## 1. Home team quality is the strongest schedule-level association

A home team entering the game with a win percentage 0.100 higher is
associated with a fill rate about **1.7 percentage points** higher
(coefficient 0.173 on a 0-1 scale, p < 0.001). Visiting-team quality
points the same way but is roughly a quarter of the size: +0.5 points of
fill per 0.100 of opponent win percentage (coefficient 0.046, p < 0.001).
Winning at home is associated with more of the building sold than hosting
a marquee opponent.

## 2. The weekend premium is large and precise

Relative to Monday games, Saturday games average **+4.9 points** of fill
(p < 0.001), Friday **+4.2**, Sunday **+3.4**, Thursday **+2.9**.
Tuesday/Wednesday are within about a point of Monday. The season also
ramps: April games run **+3.7 points** above October ones, consistent
with playoff-race interest building over the year.

## 3. Back-to-backs don't show up at the gate

Games where the home team also played the previous day show no
meaningful fill-rate difference (−0.15 points, p = 0.59). Schedule
fatigue may matter on the court, but it has no detectable association
with how many tickets get used.

## 4. The Rockets ran at the top of the league, then the rebuild showed up at the gate

From 2013-14 through 2019-20 the Rockets averaged a **0.94-1.00 fill
rate every season** — at or near capacity, including a reported sellout
rate of 100% in 2018-19 and pre-bubble 2019-20 — while the league
averaged 0.91-0.95. After the roster turnover in 2021, Rockets fill fell
to **0.867 in 2021-22** (league: 0.914) and recovered only partly to
**0.903 in 2022-23** (league: 0.956), with the reported sellout rate
dropping from 100% to about **21-23%**. Given finding #1 — fill tracks
home win percentage league-wide — a returning-to-competitive Rockets
roster is the single association most clearly aligned with filling
Toyota Center again.

## Limitations

- **Attendance is team-reported** (tickets distributed, not turnstile
  scans). Several teams report identical sellout figures for long
  stretches, which overstates true crowds and compresses variance.
- **Fill rate is capped at 1.0**; about 19% of non-excluded games report
  attendance above listed capacity (standing room, suites). The uncapped
  ratio is kept in `fill_rate_raw`.
- **Associations only.** Game dates, opponents, and records are not
  randomly assigned; unmodeled factors (pricing, promotions, star
  players, market size) drive much of attendance — which is also why
  R² is modest at 0.167.
- COVID-affected games (2019-20 bubble, all of 2020-21) and
  international/alternate-venue games are excluded; two December 2021
  Toronto games under provincial capacity limits remain in the data and
  are documented in `DATA_QUALITY.md`.
- Capacity for stable arenas is the current listed figure; sub-500-seat
  reconfigurations are not modeled.
