"""Leakage tests for the entering-record fields.

Recomputes every team's running record in plain Python, ordered by date,
and asserts the SQL window-function values used only PRIOR games:
the entering record before game i+1 must equal the entering record before
game i plus the result of game i, and every team's season opener must have
a null entering win percentage.
"""

from collections import defaultdict


def test_entering_record_uses_prior_games_only(con):
    rows = con.execute("""
        SELECT team, season_start_year, game_date, game_id, won,
               games_entering, wins_entering, win_pct_entering
        FROM team_entering
        ORDER BY team, season_start_year, game_date, game_id""").fetchall()
    assert rows, "team_entering is empty"

    running = defaultdict(lambda: (0, 0))  # (games, wins) so far per team-season
    for team, season, _date, _gid, won, games_ent, wins_ent, pct in rows:
        g, w = running[(team, season)]
        assert games_ent == g, f"{team} {season}: games_entering leaked"
        assert wins_ent == w, f"{team} {season}: wins_entering leaked"
        if g == 0:
            assert pct is None, f"{team} {season}: opener must have null entering pct"
        else:
            assert abs(pct - w / g) < 1e-3, f"{team} {season}: pct mismatch"
        running[(team, season)] = (g + 1, w + won)


def test_entering_fields_join_correct_side(con):
    # Spot-check that home/away entering fields in game_features come from
    # the matching team's row in team_entering.
    bad = con.execute("""
        SELECT COUNT(*) FROM game_features f
        JOIN team_entering h ON h.game_id = f.game_id AND h.team = f.home_team
        JOIN team_entering a ON a.game_id = f.game_id AND a.team = f.away_team
        WHERE COALESCE(f.home_win_pct_entering, -1) != COALESCE(h.win_pct_entering, -1)
           OR COALESCE(f.opp_win_pct_entering, -1) != COALESCE(a.win_pct_entering, -1)
           OR f.home_back_to_back != h.back_to_back""").fetchone()[0]
    assert bad == 0


def test_back_to_back_recomputed(con):
    from datetime import date, timedelta

    rows = con.execute("""
        SELECT team, season_start_year, game_date, back_to_back
        FROM team_entering
        ORDER BY team, season_start_year, game_date, game_id""").fetchall()
    prev = {}
    for team, season, d, b2b in rows:
        day = date.fromisoformat(d)
        expected = 1 if prev.get((team, season)) == day - timedelta(days=1) else 0
        assert b2b == expected, f"{team} {d}: back_to_back wrong"
        prev[(team, season)] = day
