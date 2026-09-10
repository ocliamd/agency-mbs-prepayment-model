"""
convexity_chart.py

Plots the pool's price across a range of rate shocks (the MBS price/yield
curve) against a hypothetical OPTION-FREE bond that has the SAME cash
flows as the MBS at zero shock, but those cash flows are held FIXED
regardless of the rate shock (i.e. no prepayment response -- a plain
bullet-ish bond).

Overlaying these two curves is the standard way this concept gets shown
in textbooks and on trading desks: the option-free bond's price curve is
convex (bows upward, accelerating gains as rates fall). The MBS curve
tracks it closely for small rate moves but bends AWAY from it (bows
downward / concave) as rates fall further, because prepayments accelerate
and cap the price. That visible gap between the two curves at the
low-rate end IS negative convexity, drawn as a picture instead of a
number.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pool import MortgagePool
from pricing import project_constant_rate_cashflows, price_from_cash_flows, price_under_shock


def option_free_bond_price(base_cash_flows, discount_rate: float, original_balance: float) -> float:
    """Prices the base-case (zero-shock) cash flow stream at a shocked
    discount rate WITHOUT changing the cash flows themselves -- this is
    what the pool would be worth if prepayments didn't respond to rates
    at all."""
    pv = price_from_cash_flows(base_cash_flows, discount_rate)
    return (pv / original_balance) * 100


def build_convexity_chart(output_path: str = "convexity_chart.png"):
    base_rate = 0.0665
    pool = MortgagePool(balance=500_000_000, wac=base_rate, wam=360)

    shocks_bps = list(range(-200, 201, 25))
    mbs_prices = []
    bond_prices = []

    # Base-case cash flows (zero shock) -- these are FROZEN and reused for
    # the option-free bond comparison at every shock level.
    base_cash_flows = project_constant_rate_cashflows(pool, market_rate=base_rate)

    for shock in shocks_bps:
        mbs_prices.append(price_under_shock(pool, base_rate, shock))
        shocked_discount_rate = base_rate + (shock / 10000)
        bond_prices.append(option_free_bond_price(base_cash_flows, shocked_discount_rate, pool.balance))

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot([s / 100 for s in shocks_bps], bond_prices, label="Option-free bond (fixed cash flows)",
             color="#888888", linestyle="--", linewidth=2)
    ax.plot([s / 100 for s in shocks_bps], mbs_prices, label="MBS pool (refi-driven prepayment)",
             color="#1f5fa8", linewidth=2.5)

    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Rate shock (percentage points)")
    ax.set_ylabel("Price (per 100 of original face)")
    ax.set_title("Negative Convexity: MBS Price/Yield vs. an Option-Free Bond\n"
                 f"$500M pool, {base_rate:.2%} WAC, 360 WAM")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    print(f"Saved chart to {output_path}")

    print(f"\n{'Shock':>8} | {'MBS Price':>10} | {'Bond Price':>10} | {'Gap':>7}")
    for shock, mp, bp in zip(shocks_bps, mbs_prices, bond_prices):
        print(f"{shock:>+6}bp | {mp:>10.2f} | {bp:>10.2f} | {mp - bp:>6.2f}")


if __name__ == "__main__":
    build_convexity_chart()