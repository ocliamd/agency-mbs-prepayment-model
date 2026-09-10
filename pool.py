"""
pool.py

Defines a stylized agency mortgage pool and generates its SCHEDULED
(no-prepayment) amortization cash flows. This is the foundation everything
else in the project builds on top of: prepayment speeds (PSA, then the
refi S-curve) will later be applied on top of this schedule to produce
realistic pool cash flows.

Key terms:
    WAC  - Weighted Average Coupon: the average gross interest rate
           borrowers in the pool are paying.
    WAM  - Weighted Average Maturity: the average number of months
           remaining until the loans in the pool are scheduled to pay off.
    Pass-through rate - what the pool investor actually receives, i.e.
           WAC minus the servicing/guarantee fee retained by the servicer
           and agency (Fannie Mae / Freddie Mac / Ginnie Mae).
"""

import pandas as pd


class MortgagePool:
    def __init__(self, balance: float, wac: float, wam: int, servicing_fee: float = 0.0025):
        """
        balance        : original pool balance in dollars (e.g. 500_000_000)
        wac            : weighted average coupon, annualized, as a decimal (e.g. 0.06 for 6%)
        wam            : weighted average maturity in months (e.g. 358)
        servicing_fee  : annualized servicing + guarantee fee, as a decimal.
                         Default 0.25%, a typical agency g-fee + servicing strip.
        """
        self.balance = balance
        self.wac = wac
        self.wam = wam
        self.servicing_fee = servicing_fee
        self.pass_through_rate = wac - servicing_fee

    def monthly_payment(self) -> float:
        """Standard fixed-rate fully amortizing payment formula (borrower's payment,
        calculated at the WAC, since that's the rate borrowers actually pay)."""
        r = self.wac / 12
        n = self.wam
        if r == 0:
            return self.balance / n
        return self.balance * (r * (1 + r) ** n) / ((1 + r) ** n - 1)

    def scheduled_amortization(self) -> pd.DataFrame:
        """
        Generates the month-by-month SCHEDULED cash flows assuming zero
        prepayments. Returns a DataFrame with both the borrower-rate cash
        flows (interest at WAC) and the investor-facing interest (at the
        pass-through rate), since those two differ by the servicing fee.
        """
        payment = self.monthly_payment()
        r_wac = self.wac / 12
        r_pt = self.pass_through_rate / 12

        rows = []
        balance = self.balance
        for month in range(1, self.wam + 1):
            interest_wac = balance * r_wac
            scheduled_principal = payment - interest_wac
            # guard against floating point drift on the final payment
            scheduled_principal = min(scheduled_principal, balance)

            investor_interest = balance * r_pt

            ending_balance = balance - scheduled_principal

            rows.append({
                "month": month,
                "beginning_balance": balance,
                "scheduled_interest_wac": interest_wac,
                "scheduled_principal": scheduled_principal,
                "total_borrower_payment": scheduled_principal + interest_wac,
                "investor_interest": investor_interest,
                "ending_balance": max(ending_balance, 0.0),
            })

            balance = ending_balance
            if balance <= 0:
                break

        return pd.DataFrame(rows)


if __name__ == "__main__":
    # Demo: a $500M pool, 6.0% WAC, 358 months WAM (a "new-ish" TBA-eligible pool)
    pool = MortgagePool(balance=500_000_000, wac=0.06, wam=358)

    print(f"Monthly borrower payment: ${pool.monthly_payment():,.2f}")
    print(f"Pass-through rate:        {pool.pass_through_rate:.3%}")

    schedule = pool.scheduled_amortization()
    print("\nFirst 3 months:")
    print(schedule.head(3).to_string(index=False))
    print("\nLast 3 months:")
    print(schedule.tail(3).to_string(index=False))
    print(f"\nTotal scheduled principal paid: ${schedule['scheduled_principal'].sum():,.2f}")
    print(f"Pool fully amortizes in {len(schedule)} months")