"""One test per documented data-quality check (see DATA_QUALITY.md)."""

import csv


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_row_count_matches_schedule(con):
    # 8 full 1,230-game seasons + 1,059 (2019-20) + 1,080 (2020-21)
    assert one(con, "SELECT COUNT(*) FROM game_features") == 11_979


def test_every_season_present(con):
    seasons = [r[0] for r in con.execute(
        "SELECT DISTINCT season_start_year FROM game_features ORDER BY 1")]
    assert seasons == list(range(2013, 2023))


def test_thirty_home_teams_every_full_season(con):
    bad = con.execute("""
        SELECT season_start_year, COUNT(DISTINCT home_team)
        FROM game_features GROUP BY 1
        HAVING COUNT(DISTINCT home_team) != 30""").fetchall()
    assert bad == []


def test_missing_attendance_within_known_bounds(con):
    # Source gap is ~8-10% per season among usable games; fail above 15%
    bad = con.execute("""
        SELECT season, 1.0 * SUM(attendance IS NULL) / COUNT(*) AS miss
        FROM game_features
        WHERE excluded_flag = 0
        GROUP BY season HAVING miss > 0.15""").fetchall()
    assert bad == []


def test_capacity_matched_for_all_non_neutral_games(con):
    assert one(con, """
        SELECT COUNT(*) FROM game_features
        WHERE capacity IS NULL AND excluded_reason IS NULL""") == 0


def test_fill_rate_capped_at_one(con):
    assert one(con, "SELECT COUNT(*) FROM game_features WHERE fill_rate > 1.0") == 0


def test_fill_rate_raw_kept_uncapped(con):
    # The cap rule is real: some games report above capacity, none absurdly so
    assert one(con, "SELECT COUNT(*) FROM game_features WHERE fill_rate_raw > 1.0") > 0
    assert one(con, """SELECT COUNT(*) FROM game_features
                       WHERE excluded_flag=0 AND fill_rate_raw > 1.2""") == 0


def test_sellout_flag_consistent(con):
    assert one(con, """
        SELECT COUNT(*) FROM game_features
        WHERE sellout_flag = 1 AND attendance < capacity""") == 0
    assert one(con, """
        SELECT COUNT(*) FROM game_features
        WHERE sellout_flag = 0 AND attendance >= capacity""") == 0


def test_exclusion_counts(con):
    counts = dict(con.execute("""
        SELECT excluded_reason, COUNT(*) FROM game_features
        WHERE excluded_flag = 1 GROUP BY 1""").fetchall())
    assert counts == {
        "covid_bubble": 88,
        "covid_limited_capacity": 1080,
        "international_game": 19,
        "alternate_venue": 1,
    }


def test_entire_2020_21_season_excluded(con):
    assert one(con, """
        SELECT COUNT(*) FROM game_features
        WHERE season_start_year = 2020 AND excluded_flag = 0""") == 0


def test_neutral_games_have_no_fill_rate(con):
    assert one(con, """
        SELECT COUNT(*) FROM game_features
        WHERE excluded_reason IN ('international_game', 'alternate_venue')
          AND (capacity IS NOT NULL OR fill_rate IS NOT NULL
               OR sellout_flag IS NOT NULL)""") == 0


def test_no_unexplained_tiny_crowds(con):
    # Only the two documented Toronto restriction games fall below 6,000
    rows = con.execute("""
        SELECT game_date, home_team FROM game_features
        WHERE excluded_flag = 0 AND attendance < 6000""").fetchall()
    assert rows == []
    tor = con.execute("""
        SELECT game_date FROM game_features
        WHERE excluded_flag = 0 AND attendance < 12000
          AND home_team = 'TOR' AND season_start_year = 2021
        ORDER BY 1""").fetchall()
    assert [r[0] for r in tor] == ["2021-12-18", "2021-12-28"]


def test_extract_csv_matches_db(con, extract_path):
    with open(extract_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        n = sum(1 for _ in reader)
    assert "fill_rate" in header and "excluded_flag" in header
    assert n == one(con, "SELECT COUNT(*) FROM game_features")
