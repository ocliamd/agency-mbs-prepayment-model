"""
fred_data.py

Loads the FRED MORTGAGE30US series (weekly 30-year fixed mortgage rate,
Freddie Mac Primary Mortgage Market Survey).

Design note: this tries to pull LIVE data directly from FRED's public CSV
endpoint first (no API key needed), since that's what you'd actually want
running day to day. It falls back to a locally cached snapshot
(data/mortgage30us.csv) if the live fetch fails -- no internet, firewall,
rate limiting, etc. This also makes the project reproducible: you can hand
someone this repo and it still runs even if FRED is unreachable.

The cached file was snapshotted 2026-09-10 and covers 2015-01-08 through
2026-09-10 -- long enough to include the COVID-era refi boom (rates down
to ~2.65% in Jan 2021) and the 2022-2023 hiking cycle (up to ~7.8%), which
is exactly the kind of rate environment variation you want to stress-test
a prepayment model against.

Source: Freddie Mac, 30-Year Fixed Rate Mortgage Average in the United
States [MORTGAGE30US], retrieved from FRED, Federal Reserve Bank of St.
Louis; https://fred.stlouisfed.org/series/MORTGAGE30US
"""

import os
import pandas as pd

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
CACHE_PATH = os.path.join(os.path.dirname(__file__), "data", "mortgage30us.csv")


def load_mortgage_rates(refresh: bool = False) -> pd.Series:
    """
    Returns a pandas Series of 30Y mortgage rates (as decimals, e.g. 0.0665
    for 6.65%), indexed by date.

    refresh=True forces a live pull from FRED and overwrites the local cache.
    Otherwise: try live first, silently fall back to cache on any failure.
    """
    if refresh:
        return _fetch_live(save_cache=True)

    try:
        return _fetch_live(save_cache=False)
    except Exception as e:
        print(f"[fred_data] Live fetch failed ({e}); falling back to cached snapshot.")
        return _load_cache()


def _fetch_live(save_cache: bool) -> pd.Series:
    df = pd.read_csv(FRED_CSV_URL)
    # FRED's CSV columns are typically ["observation_date", "MORTGAGE30US"]
    df.columns = ["date", "rate"]
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["rate"])
    df["rate"] = df["rate"].astype(float) / 100.0
    series = df.set_index("date")["rate"].sort_index()

    if save_cache:
        out = df.copy()
        out["rate"] = out["rate"] * 100.0  # keep cache in the original "percent" units
        out.to_csv(CACHE_PATH, index=False)
        print(f"[fred_data] Refreshed cache with {len(out)} rows -> {CACHE_PATH}")

    return series


def _load_cache() -> pd.Series:
    df = pd.read_csv(CACHE_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df["rate"] = df["rate"].astype(float) / 100.0
    return df.set_index("date")["rate"].sort_index()


def rate_on_or_before(series: pd.Series, target_date) -> float:
    """
    Mortgage rates are published weekly, so for any given calendar date we
    want the most recent published rate as of that date (not an exact
    match, which will usually miss).
    """
    target_date = pd.Timestamp(target_date)
    eligible = series[series.index <= target_date]
    if eligible.empty:
        raise ValueError(f"No rate data on or before {target_date.date()}")
    return eligible.iloc[-1]


if __name__ == "__main__":
    rates = load_mortgage_rates()
    print(f"Loaded {len(rates)} weekly observations")
    print(f"Range: {rates.index.min().date()} to {rates.index.max().date()}")
    print(f"Min rate: {rates.min():.2%}  (on {rates.idxmin().date()})")
    print(f"Max rate: {rates.max():.2%}  (on {rates.idxmax().date()})")
    print(f"Most recent: {rates.iloc[-1]:.2%} (on {rates.index[-1].date()})")