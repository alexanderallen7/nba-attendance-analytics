-- 02_team_entering.sql
-- Per team per game: record ENTERING the game (prior games of the same
-- regular season only -- no leakage from the game itself or later games)
-- and a back-to-back flag (team played the previous calendar day).
--
-- Method: unpivot game_base into one row per team per game, then use
-- window functions with an explicit frame ending at 1 PRECEDING so the
-- current game is never included in its own "entering" record.

DROP TABLE IF EXISTS team_game;

CREATE TABLE team_game AS
SELECT
    game_id,
    game_date,
    season_start_year,
    home_team AS team,
    CASE wl_home WHEN 'W' THEN 1 ELSE 0 END AS won
FROM game_base
UNION ALL
SELECT
    game_id,
    game_date,
    season_start_year,
    away_team AS team,
    CASE wl_home WHEN 'L' THEN 1 ELSE 0 END AS won
FROM game_base;

DROP TABLE IF EXISTS team_entering;

CREATE TABLE team_entering AS
SELECT
    game_id,
    team,
    game_date,
    season_start_year,
    won,
    -- games/wins BEFORE this game in the same season (frame excludes current row)
    COUNT(*) OVER w                       AS games_entering,
    COALESCE(SUM(won) OVER w, 0)          AS wins_entering,
    -- NULL for a team's first game of the season (0/0)
    CASE WHEN COUNT(*) OVER w > 0
         THEN ROUND(CAST(SUM(won) OVER w AS REAL) / COUNT(*) OVER w, 4)
    END                                   AS win_pct_entering,
    -- back-to-back: previous game was exactly one day earlier
    CASE WHEN LAG(game_date) OVER
              (PARTITION BY team, season_start_year ORDER BY game_date, game_id)
              = DATE(game_date, '-1 day')
         THEN 1 ELSE 0 END                AS back_to_back
FROM team_game
WINDOW w AS (
    PARTITION BY team, season_start_year
    ORDER BY game_date, game_id
    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
);
