# Agency MBS Prepayment & Cash-Flow Model

A Python model of an agency mortgage-backed securities pool: amortization,
PSA and refinancing-driven (S-curve) prepayment, and price/duration/
convexity analysis under rate shocks — built to demonstrate **negative
convexity**, the defining risk characteristic of MBS, using real
historical mortgage rate data.

<img width="1350" height="900" alt="convexity_chart" src="https://github.com/user-attachments/assets/ef27abb7-b7a0-416e-89f3-b419db42d9ba" />

## Why this project


Fixed income and structured credit desks care about prepayment risk more
than almost anything else in the mortgage market — it's the reason MBS
trade at a spread to Treasuries of the same duration, and the reason a
pool's *effective* life can be years shorter than its stated maturity.
This project builds that intuition from the ground up instead of taking
it on faith: starting from a plain amortization schedule, layering in the
industry-standard PSA benchmark, then replacing that static assumption
with a refinancing-incentive-driven model run against actual FRED rate
history, and finishing with the price/yield analysis that shows negative
convexity as both a number and a chart.

## What it does

| Module | Purpose |
|---|---|
| `pool.py` | Defines a mortgage pool (balance, WAC, WAM) and generates its scheduled (no-prepayment) amortization cash flows. |
| `prepayment.py` | The 100% PSA prepayment benchmark — the industry-standard CPR ramp every agency MBS desk quotes pools against. |
| `cashflow.py` | Combines the pool and PSA model into realistic, prepayment-adjusted cash flows; computes Weighted Average Life (WAL) across PSA speeds. |
| `fred_data.py` | Loads the FRED `MORTGAGE30US` weekly rate series, with a live fetch (works with any internet connection) and a local cache fallback for reproducibility. |
| `refi_curve.py` | A logistic S-curve prepayment model driven by refinancing incentive (pool WAC vs. current market rate), with seasoning ramp and burnout effects. |
| `historical_backtest.py` | Projects a pool's cash flows against **actual historical mortgage rates**, showing prepayment speed respond in real time to real rate moves. |
| `pricing.py` | Prices the pool under parallel rate shocks and computes effective duration and effective convexity. |
| `convexity_chart.py` | Generates the headline chart: the pool's price/yield curve against a hypothetical option-free bond with identical but *fixed* cash flows. |

## Key results

**A pool originated in January 2020 at a 3.75% WAC** — right before the
COVID-era rate collapse — fell to **57% of its original balance within 24
months**, versus 93% if it had only amortized on schedule, because the
refinancing incentive spiked past 100bp and CPR jumped to nearly 40%.
Once rates crossed back above the pool's own coupon in 2022, prepayment
speed collapsed straight back down to the housing-turnover floor.

**Effective duration and convexity** for a current-coupon $500M pool
(360 WAM):

| Metric | Value |
|---|---|
| Effective duration | ~5.16 years |
| Effective convexity | **-233** (negative) |
| Price gain, rates -50bp | +2.26 |
| Price loss, rates +50bp | -2.83 |

The asymmetry in that last row — smaller gain than loss for an equal-size
rate move in either direction — is negative convexity. The chart above
shows the same thing visually: the MBS price curve (blue) tracks the
option-free bond (gray dashed) closely near the current rate, then bends
away and flattens as rates fall further, because prepayments accelerate
and cap the price.

## Important caveat

The refinancing S-curve's parameters (floor, ceiling, midpoint,
steepness) are **illustrative, not calibrated** to actual GSE loan-level
performance data. Real prepayment models used on trading desks (Fannie
Mae's own model, Andrew Davidson & Co., Yield Book) are fit to millions
of loan-months of historical data and are proprietary. This model is
structurally correct and directionally realistic — built to demonstrate
*why* prepayment behaves the way it does, not to be a production-grade
calibrated pricing tool.

## Running it

Requires Python 3 with `pandas`, `numpy`, and `matplotlib`:

```bash
pip install pandas numpy matplotlib
```

Then, from the repo root:

```bash
python3 pool.py                  # amortization engine demo
python3 prepayment.py            # PSA CPR/SMM curve
python3 cashflow.py              # WAL across PSA speeds
python3 fred_data.py             # loads rate history (live, falls back to cache)
python3 refi_curve.py            # S-curve shape and burnout demo
python3 historical_backtest.py   # cash flows against real 2020-2026 rate history
python3 pricing.py               # duration/convexity under rate shocks
python3 convexity_chart.py       # generates convexity_chart.png
```

`fred_data.py` tries to pull live data from FRED first and only falls
back to the bundled snapshot in `data/mortgage30us.csv` (through
2026-09-10) if that fails — so results may differ slightly from the
numbers above if you run it after new rate data has been published.

## Data source

Freddie Mac, 30-Year Fixed Rate Mortgage Average in the United States
[MORTGAGE30US], retrieved from FRED, Federal Reserve Bank of St. Louis:
https://fred.stlouisfed.org/series/MORTGAGE30US

## Possible extensions

- A sequential-pay CMO tranche waterfall (A/B/Z structure), to
  demonstrate subordination mechanics on top of the existing cash flows.
- Calibrating the refi S-curve against public loan-level GSE performance
  data instead of illustrative parameters.
- OAS (option-adjusted spread) calculation via Monte Carlo rate paths
  instead of the constant-rate-shock approximation used here.
