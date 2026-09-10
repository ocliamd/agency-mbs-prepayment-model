"""
pricing.py

The payoff module. Takes a pool priced at par against today's market rate
(a "current coupon" pool -- WAC equals the market rate at issuance, which
is how newly-originated TBA-eligible pools actually work), shocks rates
in both directions, and re-projects cash flows under the refi-driven
prepayment model for each shock.

This is fundamentally different from pricing a normal bond under rate
shocks: a normal bond's cash flows are FIXED regardless of what rates do,
so you get a smooth, convex price/yield curve (price accelerates upward
as rates fall). An MBS's cash flows CHANGE with rate shocks -- prepayment
speeds rise when rates fall, returning principal early and capping how
much the price can appreciate. That capped upside next to a normal-ish
downside is exactly what "negative convexity" means, and it's the reason
MBS investors demand extra yield (spread) versus Treasuries of the same
duration.

Modeling choice: for a clean, isolated view of this effect, cash flows
here are projected assuming the SHOCKED rate holds constant for the life
of the pool (not a real historical rate path -- that's what
historical_backtest.py is for). Both the market rate driving prepayment
incentive AND the discount rate are shocked by the same parallel amount,
which approximates an MBS investor's yield moving in line with the
overall rate market.
"""

import pandas as pd
from pool import MortgagePool
from prepayment import cpr_to_smm
from refi_curve import refi_driven_cpr


def project_constant_rate_cashflows(pool: MortgagePool, market_rate: float) -> pd.DataFrame:
    """
    Projects cash flows assuming `market_rate` (and therefore the
    refinancing incentive = pool.wac - market_rate) stays constant for
    the entire remaining life of the pool.
    """
    payment = pool.monthly_payment()
    r_wac = pool.wac / 12
    r_pt = pool.pass_through_rate / 12
    incentive = pool.wac - market_rate

    rows = []
    balance = pool.balance
    for month in range(1, pool.wam + 1):
        if balance <= 0:
            break

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
        total_cash_flow = investor_interest + total_principal

        rows.append({
            "month": month,
            "total_cash_flow": total_cash_flow,
            "total_principal": total_principal,
            "ending_balance": max(ending_balance, 0.0),
        })

        balance = ending_balance

    return pd.DataFrame(rows)


def price_from_cash_flows(cash_flows: pd.DataFrame, discount_rate: float) -> float:
    """
    Present-values the monthly cash flow stream at `discount_rate`
    (annualized), returned as a percentage of the pool's original balance
    (i.e. quoted like a bond price, ~100 = par).
    """
    monthly_rate = discount_rate / 12
    months = cash_flows["month"].values
    cfs = cash_flows["total_cash_flow"].values
    discount_factors = (1 + monthly_rate) ** months
    pv = (cfs / discount_factors).sum()
    return pv


def price_under_shock(pool: MortgagePool, base_rate: float, shock_bps: float) -> float:
    """
    Shocks both the market rate (drives prepayment incentive) and the
    discount rate by the same parallel amount, then prices the pool as a
    percentage of its ORIGINAL balance.
    """
    shock = shock_bps / 10000
    shocked_market_rate = base_rate + shock
    shocked_discount_rate = base_rate + shock

    cf = project_constant_rate_cashflows(pool, market_rate=shocked_market_rate)
    pv = price_from_cash_flows(cf, discount_rate=shocked_discount_rate)
    return (pv / pool.balance) * 100  # quoted per 100 of original face


def effective_duration_convexity(pool: MortgagePool, base_rate: float, shock_bps: float = 50):
    """
    Standard effective duration/convexity formulas using a +/- shock_bps
    parallel shift:

        EffDur  = (P(-shock) - P(+shock)) / (2 * P(0) * shock_decimal)
        EffConv = (P(+shock) + P(-shock) - 2*P(0)) / (P(0) * shock_decimal^2)
    """
    p0 = price_under_shock(pool, base_rate, 0)
    p_down = price_under_shock(pool, base_rate, -shock_bps)
    p_up = price_under_shock(pool, base_rate, shock_bps)

    shock_decimal = shock_bps / 10000
    eff_duration = (p_down - p_up) / (2 * p0 * shock_decimal)
    eff_convexity = (p_up + p_down - 2 * p0) / (p0 * shock_decimal ** 2)

    return {
        "price_down": p_down,
        "price_base": p0,
        "price_up": p_up,
        "effective_duration": eff_duration,
        "effective_convexity": eff_convexity,
    }


if __name__ == "__main__":
    # A current-coupon pool: WAC set exactly at today's market rate, so it
    # prices near par at zero shock -- a clean baseline for comparison.
    base_rate = 0.0665  # ~today's 30Y rate per the cached FRED data
    pool = MortgagePool(balance=500_000_000, wac=base_rate, wam=360)

    print(f"Pool: $500M, {base_rate:.2%} WAC (current coupon), 360 WAM\n")
    print(f"{'Shock':>8} | {'Price':>8}")
    for shock in [-100, -50, 0, 50, 100]:
        price = price_under_shock(pool, base_rate, shock)
        print(f"{shock:>+6}bp | {price:>7.2f}")

    print("\nEffective duration / convexity (using +/-50bp shocks):")
    result = effective_duration_convexity(pool, base_rate, shock_bps=50)
    for k, v in result.items():
        print(f"  {k:>20}: {v:.4f}")

    gain_on_rate_decline = result["price_down"] - result["price_base"]
    loss_on_rate_increase = result["price_base"] - result["price_up"]
    print("\nNegative convexity check (+/-50bp):")
    print(f"  Price gain when rates FALL 50bp:  +{gain_on_rate_decline:.3f}")
    print(f"  Price loss when rates RISE 50bp:  -{loss_on_rate_increase:.3f}")
    if gain_on_rate_decline < loss_on_rate_increase:
        print("  -> Upside is smaller than downside: negative convexity confirmed.")
    else:
        print("  -> Upside is NOT smaller than downside -- unexpected, check the model.")