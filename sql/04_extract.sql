-- 04_extract.sql
-- The tidy one-table extract consumed by Tableau and the regression.
-- scripts/build_db.py runs this SELECT and writes the result to
-- data/processed/extract.csv.

SELECT
    game_id,
    game_date,
    season,
    season_start_year,
    home_team,
    away_team,
    arena,
    attendance,
    capacity,
    fill_rate,
    fill_rate_raw,
    sellout_flag,
    day_of_week,
    month,
    home_win_pct_entering,
    opp_win_pct_entering,
    home_back_to_back,
    excluded_flag,
    excluded_reason
FROM game_features
ORDER BY game_date, game_id;
