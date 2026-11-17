"""OLS regression of fill rate on game and schedule features.

Model (non-excluded games with complete fields):
    fill_rate ~ home_win_pct_entering + opp_win_pct_entering
              + C(day_of_week) + C(month) + C(season) + home_back_to_back

Outputs:
    data/processed/regression_results.csv  tidy coefficient table
    data/processed/season_trend.csv        league vs Rockets fill rate by season
    analysis/regression_summary.txt        full statsmodels summary (reference)

All results are associations between schedule context and fill rate,
not causal estimates.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"


def main() -> None:
    df = pd.read_csv(PROCESSED / "extract.csv", dtype={"game_id": str})

    model_df = df[
        (df["excluded_flag"] == 0)
        & df["fill_rate"].notna()
        & df["home_win_pct_entering"].notna()
        & df["opp_win_pct_entering"].notna()
    ].copy()

    # Order categoricals so the baselines are readable:
    # day baseline = Monday, month baseline = October, season baseline = 2013-14.
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    months = [10, 11, 12, 1, 2, 3, 4]
    model_df["day_of_week"] = pd.Categorical(model_df["day_of_week"], categories=days)
    model_df["month"] = pd.Categorical(model_df["month"], categories=months)

    model = smf.ols(
        "fill_rate ~ home_win_pct_entering + opp_win_pct_entering"
        " + C(day_of_week) + C(month) + C(season) + home_back_to_back",
        data=model_df,
    ).fit()

    tidy = pd.DataFrame(
        {
            "term": model.params.index,
            "coefficient": model.params.values,
            "std_error": model.bse.values,
            "p_value": model.pvalues.values,
        }
    )
    tidy["r_squared"] = model.rsquared
    tidy["adj_r_squared"] = model.rsquared_adj
    tidy["n_obs"] = int(model.nobs)
    tidy.to_csv(PROCESSED / "regression_results.csv", index=False)

    (ROOT / "analysis" / "regression_summary.txt").write_text(
        model.summary().as_text(), encoding="utf-8"
    )

    # Season-level trend: league average vs Rockets, with year-over-year change.
    usable = df[(df["excluded_flag"] == 0) & df["fill_rate"].notna()]
    league = usable.groupby("season")["fill_rate"].mean().rename("league_fill_rate")
    hou = (
        usable[usable["home_team"] == "HOU"]
        .groupby("season")["fill_rate"]
        .mean()
        .rename("rockets_fill_rate")
    )
    sellout = usable.groupby("season")["sellout_flag"].mean().rename("league_sellout_rate")
    hou_sellout = (
        usable[usable["home_team"] == "HOU"]
        .groupby("season")["sellout_flag"]
        .mean()
        .rename("rockets_sellout_rate")
    )
    trend = pd.concat([league, hou, sellout, hou_sellout], axis=1).reset_index()
    trend["league_yoy_change"] = trend["league_fill_rate"].diff()
    trend["rockets_yoy_change"] = trend["rockets_fill_rate"].diff()
    # 2020-21 is fully excluded, so the trend table skips it; mark the gap.
    trend["note"] = ""
    trend.loc[trend["season"] == "2021-22", "note"] = "yoy vs 2019-20; 2020-21 excluded (COVID)"
    trend.loc[trend["season"] == "2019-20", "note"] = "pre-bubble games only"
    trend.round(4).to_csv(PROCESSED / "season_trend.csv", index=False)

    print(model.summary())
    print(f"\nn = {int(model.nobs)}, R^2 = {model.rsquared:.3f}")
    print(trend.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
