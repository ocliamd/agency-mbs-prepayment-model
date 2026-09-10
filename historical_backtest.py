"""
historical_backtest.py

Originates a hypothetical pool at a specific historical date and projects
its cash flows month by month using ACTUAL subsequent market mortgage
rates (from fred_data.py) as the refinancing incentive driver -- instead
of a static assumed PSA speed.

This is the payoff of the whole project: you can literally watch a pool
originated right before the 2020 rate collapse prepay itself down to
almost nothing within two years, then watch that same cohort dynamic
freeze solid once rates spike in 2022-2023. That's not a PSA assumption
-- that's the model responding to real market history.
"""

import pandas as pd
from pool import MortgagePool
from prepayment import cpr_to_smm
from refi_curve import refi_driven_cpr
from fred_data import load_mortgage_rates, rate_on_or_before


def project_refi_driven_cash_flows(pool: MortgagePool, origination_date: str) -> pd.DataFrame:
    """
    origination_date : 'YYYY-MM-DD' string -- when this pool's loans were
                        assumed to have closed. Cash flows are projected
                        forward from here using the actual historical
                        mortgage rate path as of each subsequent month.
    """
    rates = load_mortgage_rates()
    origination = pd.Timestamp(origination_date)

    payment = pool.monthly_payment()
    r_wac = pool.wac / 12
    r_pt = pool.pass_through_rate / 12

    rows = []
    balance = pool.balance
    for month in range(1, pool.wam + 1):
        if balance <= 0:
            break

        current_date = origination + pd.DateOffset(months=month)
        market_rate = rate_on_or_before(rates, current_date)
        incentive = pool.wac - market_rate
        pool_factor = balance / pool.balance

        cpr = refi_driven_cpr(incentive, loan_age_months=month, pool_factor=pool_factor)
        smm = cpr_to_smm(cpr)

        scheduled_interest = balance * r_wac
        scheduled_principal = max(min(payment - scheduled_interest, balance), 0.0)
        balance_after_scheduled = balance - scheduled_principal
        prepayment = smm * balance_after_scheduled

        total_principal = scheduled_principal + prepayment
        ending_balance = balance - total_principal
        investor_interest = balance * r_pt

        rows.append({
            "month": month,
            "date": current_date.date(),
            "market_rate": market_rate,
            "incentive": incentive,
            "cpr": cpr,
            "beginning_balance": balance,
            "prepayment": prepayment,
            "total_principal": total_principal,
            "investor_interest": investor_interest,
            "pool_factor": pool_factor,
            "ending_balance": max(ending_balance, 0.0),
        })

        balance = ending_balance

    return pd.DataFrame(rows)


if __name__ == "__main__":
    # A pool originated right at the edge of the COVID-era rate collapse.
    # 3.75% WAC was a realistic 30Y rate in early 2020.
    pool = MortgagePool(balance=500_000_000, wac=0.0375, wam=360)
    cf = project_refi_driven_cash_flows(pool, origination_date="2020-01-01")

    print("Pool: $500M, 3.75% WAC, originated 2020-01-01\n")
    print(f"{'Date':>10} | {'Mkt Rate':>8} | {'Incentive':>9} | {'CPR':>7} | {'Pool Factor':>11}")
    # Print roughly every 6 months so the story is readable
    for i in range(0, len(cf), 6):
        row = cf.iloc[i]
        print(f"{str(row['date']):>10} | {row['market_rate']:>7.2%} | "
              f"{row['incentive']:>8.2%} | {row['cpr']:>6.2%} | {row['pool_factor']:>10.1%}")

    print(f"\nPool factor after 24 months: {cf.iloc[23]['pool_factor']:.1%} "
          f"(vs. {1 - 24/360:.1%} if it had only amortized on schedule)")
    print(f"Pool factor at end of data ({cf.iloc[-1]['date']}): {cf.iloc[-1]['pool_factor']:.1%}")