"""
refi_curve.py

A refinancing-incentive-driven prepayment model. This replaces "prepayment
speed is a fixed assumption you pick" (the PSA approach) with "prepayment
speed responds to where current market rates sit relative to the pool's
coupon" -- which is the actual economic behavior driving real MBS cash
flows.

Three effects are combined, each with a real-world justification:

1. SEASONING RAMP
   Brand-new loans prepay slowly regardless of rate incentive -- movers
   haven't had time to move yet, and there's often a soft prepayment
   penalty period. Ramps from 0 to full effect over `ramp_months`.

2. REFINANCING S-CURVE
   As the rate incentive (pool's WAC minus current market rate) increases,
   prepayment speed rises -- slowly at first, then sharply once
   refinancing is clearly worth the closing costs and hassle, then
   levels off (not everyone who COULD refinance WILL -- some borrowers
   are unreachable, credit-impaired, or simply inattentive). That
   flattening at both ends is what makes it an S-curve rather than a
   straight line, and it's modeled here with a logistic function.

3. BURNOUT
   If a pool has already been sitting at a deep refinancing incentive for
   a while, the borrowers who were going to refinance already have --
   what's left is a residual population that's slower to respond even
   at the same incentive level. Approximated here with the pool factor
   (current balance / original balance): as the pool paydown accelerates
   ahead of pure seasoning, that in itself is evidence of burnout, so we
   scale down future refi response accordingly.

IMPORTANT CAVEAT (say this out loud in an interview): the specific
constants below (floor, ceiling, midpoint, steepness) are illustrative,
NOT calibrated to actual GSE loan-level performance data. Real dealer and
agency prepayment models (Fannie Mae's own model, Andrew Davidson & Co.,
Yield Book, etc.) are fit to millions of loan-months of historical data
and are proprietary. This model is structurally correct and directionally
realistic -- it's meant to demonstrate understanding of WHY prepayment
behaves this way, not to be a production-grade calibrated model.
"""

import math


def seasoning_ramp(loan_age_months: int, ramp_months: int = 12) -> float:
    """Returns a 0-to-1 multiplier that ramps up linearly over the first
    `ramp_months` of the loan's life, then stays at 1.0."""
    return min(loan_age_months / ramp_months, 1.0)


def refi_s_curve(incentive: float, floor: float = 0.06, ceiling: float = 0.55,
                  midpoint: float = 0.0075, steepness: float = 500) -> float:
    """
    incentive : pool WAC minus current market rate, as a decimal
                (e.g. 0.01 for a 100bp refinancing incentive).
    floor     : baseline annualized CPR from ordinary housing turnover
                (moving, death, divorce, etc.) even with NO refi incentive.
    ceiling   : the annualized CPR the curve saturates toward at very deep
                in-the-money incentive.
    midpoint  : the incentive level (in decimal) at which prepayment speed
                is rising fastest -- roughly "where refinancing clearly
                becomes worth it net of closing costs."
    steepness : controls how sharply the curve transitions from floor to
                ceiling around the midpoint.

    Returns an annualized CPR as a decimal.
    """
    return floor + (ceiling - floor) / (1 + math.exp(-steepness * (incentive - midpoint)))


def burnout_multiplier(pool_factor: float, strength: float = 0.5) -> float:
    """
    pool_factor : current balance / original balance, in (0, 1].
    strength    : how strongly burnout suppresses further refi response.
                  0 = no burnout effect; 1 = full linear suppression.
    A pool that has already paid down faster than scheduled (because
    borrowers already refinanced) gets a reduced multiplier on FUTURE
    refi-driven prepayment, since the fastest-to-respond borrowers are
    already gone.
    """
    return pool_factor ** strength


def refi_driven_cpr(incentive: float, loan_age_months: int, pool_factor: float) -> float:
    """Combines seasoning, the refi S-curve, and burnout into a single
    annualized CPR for one month."""
    base_cpr = refi_s_curve(incentive)
    return base_cpr * seasoning_ramp(loan_age_months) * burnout_multiplier(pool_factor)


if __name__ == "__main__":
    print("Incentive | CPR (no burnout, fully seasoned)")
    for incentive_bps in [-100, -50, 0, 25, 50, 75, 100, 150, 200, 300]:
        incentive = incentive_bps / 10000
        cpr = refi_s_curve(incentive)
        print(f"{incentive_bps:>9}bp | {cpr:>8.2%}")

    print("\nSeasoning ramp:")
    for age in [1, 3, 6, 9, 12, 24]:
        print(f"  age {age:>2} mo -> ramp multiplier {seasoning_ramp(age):.2f}")

    print("\nBurnout effect at 150bp incentive, fully seasoned:")
    for factor in [1.0, 0.9, 0.7, 0.5, 0.3]:
        cpr = refi_driven_cpr(incentive=0.015, loan_age_months=24, pool_factor=factor)
        print(f"  pool factor {factor:.1f} -> CPR {cpr:.2%}")