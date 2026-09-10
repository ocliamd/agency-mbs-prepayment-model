"""
prepayment.py

Implements the PSA (Public Securities Association) standard prepayment
benchmark -- the baseline every agency MBS desk quotes pools against
(e.g. "this pool is trading at 165 PSA").

100% PSA definition:
    - CPR (Conditional Prepayment Rate, annualized) ramps up linearly by
      0.2% per month for the first 30 months of the loan's age, reaching 6%.
    - CPR then stays flat at 6% for the remaining life of the loan.

A pool quoted at X% PSA simply scales that entire curve by X/100 -- e.g.
165% PSA means the pool prepays at 1.65x the standard speed at every
point on the ramp and on the plateau.

CPR is an ANNUALIZED rate. To apply it to a single month's beginning
balance we need SMM (Single Monthly Mortality), the monthly-equivalent
rate, converted via:

    SMM = 1 - (1 - CPR)^(1/12)
"""


def psa_cpr(loan_age_months: int, psa_multiplier: float = 1.0) -> float:
    """
    loan_age_months : how many months old the loan is (NOT months remaining).
                       A brand-new loan starts at age 0/1.
    psa_multiplier  : 1.0 = 100% PSA (the standard benchmark speed).
                       1.65 = 165% PSA, 0.5 = 50% PSA, etc.
    Returns the annualized CPR as a decimal (e.g. 0.06 for 6%).
    """
    base_cpr = min(loan_age_months / 30, 1.0) * 0.06
    return base_cpr * psa_multiplier


def cpr_to_smm(cpr: float) -> float:
    """Converts an annualized CPR into the monthly SMM rate."""
    return 1 - (1 - cpr) ** (1 / 12)


if __name__ == "__main__":
    print("Age (mo) | 100% PSA CPR | 100% PSA SMM | 165% PSA CPR")
    for age in [1, 6, 12, 24, 30, 60, 120, 300]:
        cpr_100 = psa_cpr(age, 1.0)
        smm_100 = cpr_to_smm(cpr_100)
        cpr_165 = psa_cpr(age, 1.65)
        print(f"{age:>8} | {cpr_100:>11.2%} | {smm_100:>11.3%} | {cpr_165:>11.2%}")