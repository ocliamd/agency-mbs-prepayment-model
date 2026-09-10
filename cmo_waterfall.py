"""
cmo_waterfall.py

Splits a single pool's cash flows into multiple TRANCHES using a
sequential-pay structure -- the most basic real-world CMO (Collateralized
Mortgage Obligation) design, and the building block every more complex
structure (PAC/companion, IO/PO, credit tranching) is built from.

The mechanics:
    - Every tranche gets its pro-rata share of INTEREST based on its own
      outstanding balance (same coupon rate as the collateral here, for
      simplicity -- real deals often vary coupons by tranche).
    - ALL principal (scheduled + prepaid) goes to the SHORTEST tranche
      first. Once Tranche A is fully paid down to zero, principal starts
      flowing to Tranche B. Once B is retired, everything goes to Z.

Why this matters: the underlying collateral has one blended WAL, but
sequential tranching lets you carve that same collateral into pieces with
VERY different WALs and risk profiles -- a short, low-duration Tranche A
that appeals to money-market-like investors, and a longer, more
prepayment-exposed Z tranche that only appeals to investors willing to
take on that extension/contraction risk in exchange for extra yield.
This is exactly the mechanism private credit and structured credit shops
use to create subordination and tailor risk to different investors from
one pool of loans.
"""

import pandas as pd
from pool import MortgagePool
from cashflow import project_cash_flows, weighted_average_life


def sequential_pay_waterfall(cash_flows: pd.DataFrame, tranche_fractions: dict,
                              original_pool_balance: float, coupon_rate: float) -> dict:
    """
    tranche_fractions : e.g. {"A": 0.70, "B": 0.20, "Z": 0.10} -- fractions
                         of the ORIGINAL pool balance allocated to each
                         tranche, in PAY ORDER (first key paid down first).
    coupon_rate       : annualized rate paid on each tranche's outstanding
                         balance (kept the same across tranches here for
                         simplicity -- real deals often vary this).

    Returns a dict of {tranche_name: DataFrame} with month-by-month
    beginning balance, interest, principal, and ending balance for each
    tranche.
    """
    tranche_names = list(tranche_fractions.keys())
    balances = {name: original_pool_balance * frac for name, frac in tranche_fractions.items()}
    monthly_coupon = coupon_rate / 12

    tranche_rows = {name: [] for name in tranche_names}

    for _, row in cash_flows.iterrows():
        month = row["month"]
        principal_available = row["total_principal"]

        for name in tranche_names:
            beginning_balance = balances[name]
            interest = beginning_balance * monthly_coupon

            # Sequential pay: this tranche only gets principal once every
            # tranche ahead of it in the list has been fully retired.
            principal_to_tranche = min(principal_available, beginning_balance)
            principal_available -= principal_to_tranche

            ending_balance = beginning_balance - principal_to_tranche
            balances[name] = ending_balance

            tranche_rows[name].append({
                "month": month,
                "beginning_balance": beginning_balance,
                "interest": interest,
                "principal": principal_to_tranche,
                "total_cash_flow": interest + principal_to_tranche,
                "ending_balance": ending_balance,
            })

    return {name: pd.DataFrame(rows) for name, rows in tranche_rows.items()}


if __name__ == "__main__":
    pool = MortgagePool(balance=500_000_000, wac=0.06, wam=358)
    cash_flows = project_cash_flows(pool, psa_multiplier=1.65)

    tranche_fractions = {"A": 0.70, "B": 0.20, "Z": 0.10}
    tranches = sequential_pay_waterfall(
        cash_flows,
        tranche_fractions=tranche_fractions,
        original_pool_balance=pool.balance,
        coupon_rate=pool.pass_through_rate,
    )

    collateral_wal = weighted_average_life(cash_flows)
    print(f"Collateral (whole pool) WAL: {collateral_wal:.2f} years\n")

    print(f"{'Tranche':>8} | {'Orig. Balance':>15} | {'WAL (years)':>12} | {'Months to Retire':>17}")
    for name, df in tranches.items():
        wal = weighted_average_life(df.rename(columns={"principal": "total_principal"}))
        months_to_retire = (df["ending_balance"] > 1e-6).sum() + 1
        orig_balance = pool.balance * tranche_fractions[name]
        print(f"{name:>8} | {orig_balance:>15,.0f} | {wal:>12.2f} | {months_to_retire:>17}")

    print("\nTranche A, first 6 months (fully sequential -- gets ALL principal):")
    print(tranches["A"][["month", "beginning_balance", "interest", "principal", "ending_balance"]]
          .head(6).to_string(index=False))