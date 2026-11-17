-- 03_game_features.sql
-- Final feature table: one row per regular-season home game with
-- attendance, capacity, fill rate, calendar features, entering records,
-- back-to-back flag, and exclusion flags.
--
-- Reference tables (loaded from CSV by scripts/build_db.py):
--   arena_capacity      team, arena, first_season, last_season, capacity, source_url
--   neutral_site_games  game_id, venue, city, reason  (international + alternate venues)
--
-- Exclusion rules (excluded_flag = 1, first matching reason wins):
--   1. covid_bubble            2019-20 games on/after 2020-07-30 (Orlando bubble,
--                              no fans, neutral site)
--   2. covid_limited_capacity  the entire 2020-21 season (arenas closed or at
--                              reduced, team-specific capacity all year)
--   3. international_game      regular-season games hosted in London, Mexico City,
--                              or Paris (listed designated home team, not their arena)
--   4. alternate_venue         home games moved to a non-standard building
--                              (San Antonio's 2023 Alamodome game)
--
-- Fill-rate rule (documented in DATA_QUALITY.md): teams sometimes report
-- attendance above listed capacity (standing room, suites). fill_rate is
-- attendance / capacity CAPPED AT 1.0; the uncapped value is kept in
-- fill_rate_raw. sellout_flag = attendance >= capacity.
-- Capacity, fill rate, and sellout are NULL for neutral-site/alternate-venue
-- games: the home arena's capacity does not describe the building used.

DROP TABLE IF EXISTS game_features;

CREATE TABLE game_features AS
SELECT
    b.game_id,
    b.game_date,
    b.season,
    b.season_start_year,
    b.home_team,
    b.away_team,
    b.attendance,
    CASE WHEN n.game_id IS NULL THEN ac.arena    END AS arena,
    CASE WHEN n.game_id IS NULL THEN ac.capacity END AS capacity,
    CASE WHEN n.game_id IS NULL AND b.attendance IS NOT NULL
         THEN ROUND(CAST(b.attendance AS REAL) / ac.capacity, 4)
    END AS fill_rate_raw,
    CASE WHEN n.game_id IS NULL AND b.attendance IS NOT NULL
         THEN ROUND(MIN(CAST(b.attendance AS REAL) / ac.capacity, 1.0), 4)
    END AS fill_rate,
    CASE WHEN n.game_id IS NULL AND b.attendance IS NOT NULL
         THEN CASE WHEN b.attendance >= ac.capacity THEN 1 ELSE 0 END
    END AS sellout_flag,
    -- calendar features
    CASE CAST(STRFTIME('%w', b.game_date) AS INTEGER)
        WHEN 0 THEN 'Sun' WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue' WHEN 3 THEN 'Wed'
        WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' WHEN 6 THEN 'Sat'
    END AS day_of_week,
    CAST(STRFTIME('%m', b.game_date) AS INTEGER) AS month,
    -- entering records (prior games of the season only; NULL on each team's opener)
    he.win_pct_entering AS home_win_pct_entering,
    ae.win_pct_entering AS opp_win_pct_entering,
    he.back_to_back     AS home_back_to_back,
    -- exclusions
    CASE WHEN (b.season_start_year = 2019 AND b.game_date >= '2020-07-30')
           OR b.season_start_year = 2020
           OR n.game_id IS NOT NULL
         THEN 1 ELSE 0 END AS excluded_flag,
    CASE
        WHEN b.season_start_year = 2019 AND b.game_date >= '2020-07-30' THEN 'covid_bubble'
        WHEN b.season_start_year = 2020                                 THEN 'covid_limited_capacity'
        WHEN n.game_id IS NOT NULL                                      THEN n.reason
    END AS excluded_reason,
    n.venue AS neutral_venue
FROM game_base b
LEFT JOIN arena_capacity ac
       ON ac.team = b.home_team
      AND b.season_start_year BETWEEN ac.first_season AND ac.last_season
LEFT JOIN team_entering he
       ON he.game_id = b.game_id AND he.team = b.home_team
LEFT JOIN team_entering ae
       ON ae.game_id = b.game_id AND ae.team = b.away_team
LEFT JOIN neutral_site_games n
       ON n.game_id = b.game_id;
