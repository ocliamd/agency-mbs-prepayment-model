"""
cashflow.py

Combines the pool's amortization engine (pool.py) with the PSA prepayment
model (prepayment.py) to produce realistic, prepayment-adjusted cash flows
-- the actual output that an MBS investor receives every month.

Key modeling choice, worth understanding cold for an interview:
    The borrower's monthly PAYMENT is fixed at closing based on the
    ORIGINAL balance/WAC/WAM (see MortgagePool.monthly_payment()). That
    payment amount never changes just because other borrowers in the pool
    prepay. So each month:

        scheduled_interest  = current beginning balance * (WAC / 12)
        scheduled_principal = original fixed payment - scheduled_interest

    That's the "as if nobody ever prepays" principal paydown. On TOP of
    that, prepayments (SMM applied to whatever balance is left after the
    scheduled principal is paid) return additional principal to the
    investor immediately, which is what causes the pool to amortize much
    faster than its stated WAM -- and why WAL, not WAM, is the number
    that actually matters for pricing.
"""

import pandas as pd
from pool import MortgagePool
from prepayment import psa_cpr, cpr_to_smm


def project_cash_flows(pool: MortgagePool, psa_multiplier: float = 1.0,
                        loan_age_at_start: int = 0) -> pd.DataFrame:
    """
    loan_age_at_start : age (in months) of the loans in the pool as of month 0
                         of this projection. Use 0 for a brand-new pool; use
                         e.g. 24 if the pool has already seasoned 2 years
                         before you start projecting.
    """
    payment = pool.monthly_payment()
    r_wac = pool.wac / 12
    r_pt = pool.pass_through_rate / 12

    rows = []
    balance = pool.balance
    for month in range(1, pool.wam + 1):
        if balance <= 0:
            break

        age = loan_age_at_start + month
        cpr = psa_cpr(age, psa_multiplier)
        smm = cpr_to_smm(cpr)

        scheduled_interest = balance * r_wac
        scheduled_principal = payment - scheduled_interest
        scheduled_principal = max(min(scheduled_principal, balance), 0.0)

        balance_after_scheduled = balance - scheduled_principal
        prepayment = smm * balance_after_scheduled

        total_principal = scheduled_principal + prepayment
        ending_balance = balance - total_principal

        investor_interest = balance * r_pt
        total_cash_flow = investor_interest + total_principal

        rows.append({
            "month": month,
            "loan_age": age,
            "cpr": cpr,
            "smm": smm,
            "beginning_balance": balance,
            "scheduled_principal": scheduled_principal,
            "prepayment": prepayment,
            "total_principal": total_principal,
            "investor_interest": investor_interest,
            "total_cash_flow": total_cash_flow,
            "ending_balance": max(ending_balance, 0.0),
        })

        balance = ending_balance

    return pd.DataFrame(rows)


def weighted_average_life(cash_flows: pd.DataFrame) -> float:
    """
    WAL (in years) = sum(month * principal_paid_that_month) / sum(principal_paid) / 12

    This is THE number MBS traders quote instead of WAM once prepayments
    are in the picture -- it tells you the average time it actually takes
    to get your principal back, not the stated maturity of the loans.
    """
    total_principal = cash_flows["total_principal"].sum()
    weighted_months = (cash_flows["month"] * cash_flows["total_principal"]).sum()
    return (weighted_months / total_principal) / 12


if __name__ == "__main__":
    pool = MortgagePool(balance=500_000_000, wac=0.06, wam=358)

    print(f"{'PSA Speed':>10} | {'WAL (years)':>12} | {'Months to fully pay down':>25}")
    for psa_mult, label in [(0.5, "50% PSA"), (1.0, "100% PSA"),
                             (1.65, "165% PSA"), (3.0, "300% PSA")]:
        cf = project_cash_flows(pool, psa_multiplier=psa_mult)
        wal = weighted_average_life(cf)
        print(f"{label:>10} | {wal:>12.2f} | {len(cf):>25}")

    print("\nDetail for 165% PSA, first 6 months:")
    cf_165 = project_cash_flows(pool, psa_multiplier=1.65)
    cols = ["month", "loan_age", "cpr", "smm", "beginning_balance",
            "scheduled_principal", "prepayment", "total_cash_flow"]
    print(cf_165[cols].head(6).to_string(index=False))