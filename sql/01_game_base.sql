-- 01_game_base.sql
-- One row per regular-season game, seasons 2013-14 through 2022-23,
-- with attendance joined in from game_info.
--
-- Source tables (attached read-only as "raw"):
--   raw.game       one row per game with home/away team columns
--   raw.game_info  game_id -> attendance
--
-- Notes:
--   * season_id in the source is e.g. '22013' for the 2013-14 regular
--     season; the leading '2' is the season-type prefix, the rest is the
--     season start year.
--   * attendance of 0 is treated as missing (NULLIF): zeros appear only
--     for games played with no admitted fans (2020-21) or data gaps.
--   * The source database is missing the 2012-13 season entirely, which
--     is one reason the window starts at 2013-14.

DROP TABLE IF EXISTS game_base;

CREATE TABLE game_base AS
SELECT
    g.game_id,
    DATE(g.game_date)                                   AS game_date,
    CAST(SUBSTR(g.season_id, 2) AS INTEGER)             AS season_start_year,
    -- '2013' -> '2013-14' label for display
    SUBSTR(g.season_id, 2)
      || '-'
      || SUBSTR(CAST(CAST(SUBSTR(g.season_id, 2) AS INTEGER) + 1 AS TEXT), 3) AS season,
    g.team_abbreviation_home                            AS home_team,
    g.team_abbreviation_away                            AS away_team,
    NULLIF(gi.attendance, 0)                            AS attendance,
    g.wl_home                                           AS wl_home
FROM raw.game g
LEFT JOIN raw.game_info gi
       ON gi.game_id = g.game_id
WHERE g.season_type = 'Regular Season'
  AND CAST(SUBSTR(g.season_id, 2) AS INTEGER) BETWEEN 2013 AND 2022;
