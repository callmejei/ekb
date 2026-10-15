"""Synthetic sample documents for the POC (no confidential data).

"Sample Bank" and the regulatory notices named here are fictional. Run inside the api container:
    python -m app.samples          # writes PDFs to /samples
"""

import sys
from pathlib import Path

import fitz

CSS = """
body { font-family: sans-serif; font-size: 10pt; color: #1a1a1a; }
h1 { font-size: 18pt; color: #8b1a1a; margin-bottom: 4pt; }
h2 { font-size: 13pt; color: #222; margin-top: 12pt; margin-bottom: 4pt; }
p { margin-bottom: 6pt; line-height: 1.35; }
table { border-collapse: collapse; margin-bottom: 8pt; }
th, td { border: 1px solid #555; padding: 3pt 6pt; font-size: 9pt; }
th { background-color: #eeeeee; }
.meta { font-size: 8.5pt; color: #555; }
li { margin-bottom: 3pt; }
"""


def table(header: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{h}</th>" for h in header)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{th}</tr>{trs}</table>"


def meta(code: str, eff: str, owner: str, cls: str) -> str:
    return f'<p class="meta">Document {code} · Effective {eff} · Owner: {owner} · Classification: {cls}</p>'


# ── Home loan ──────────────────────────────────────────────────────────────────


def home_loan(version: int) -> str:
    if version == 1:
        eff, fixed = "1 January 2026", [["Year 1", "2.45%"], ["Year 2", "2.45%"], ["Year 3", "2.65%"], ["Thereafter", "3M SORA + 1.10%"]]
        floating = [["Year 1", "3M SORA + 0.70%"], ["Year 2", "3M SORA + 0.80%"], ["Year 3", "3M SORA + 0.90%"], ["Thereafter", "3M SORA + 1.10%"]]
        penalty, cancel = "1.50%", "SGD 2,000"
    else:
        eff, fixed = "1 October 2026", [["Year 1", "2.15%"], ["Year 2", "2.15%"], ["Year 3", "2.40%"], ["Thereafter", "3M SORA + 1.00%"]]
        floating = [["Year 1", "3M SORA + 0.55%"], ["Year 2", "3M SORA + 0.65%"], ["Year 3", "3M SORA + 0.85%"], ["Thereafter", "3M SORA + 1.00%"]]
        penalty, cancel = "1.25%", "SGD 1,500"
    return f"""
<h1>Home Loan — Product Disclosure Sheet</h1>
{meta(f"PDS-HL-00{version}", eff, "Retail Banking, Secured Lending", "Public")}
<h2>1. About this product</h2>
<p>The Sample Bank Home Loan helps individuals finance the purchase of completed private residential
property and HDB flats in Singapore, or refinance an existing housing loan from another bank. This
Product Disclosure Sheet (PDS) summarises the key features, interest rates, fees and risks. Please read it
together with the Letter of Offer and the Home Loan Terms and Conditions.</p>
<h2>2. Eligibility</h2>
<ul>
<li>Borrowers must be at least 21 years old and not more than 65 years old at loan maturity.</li>
<li>Minimum annual income of SGD 30,000 for Singapore citizens and permanent residents, and SGD 60,000 for foreigners.</li>
<li>Minimum loan quantum of SGD 100,000. Maximum loan tenure of 30 years for HDB flats and 35 years for private property.</li>
<li>All applications are assessed under the Total Debt Servicing Ratio (TDSR) framework; the TDSR must not exceed 55%.</li>
</ul>
<h2>3. Interest rate packages</h2>
<p>Two packages are available. The fixed rate package offers certainty of instalments during the lock-in period.
The floating package is pegged to the 3-month Compounded Singapore Overnight Rate Average (3M SORA),
which is published daily and may go up or down.</p>
<p><b>Table 1: Fixed rate package (2-year lock-in)</b></p>
{table(["Period", "Interest rate (p.a.)"], fixed)}
<p><b>Table 2: SORA floating package (no lock-in after year 2)</b></p>
{table(["Period", "Interest rate (p.a.)"], floating)}
<h2>4. Fees and charges</h2>
{table(["Fee", "Amount", "When charged"], [
    ["Prepayment penalty (within lock-in)", f"{penalty} of amount prepaid", "Partial or full prepayment during lock-in"],
    ["Cancellation fee", cancel, "Cancellation after acceptance of Letter of Offer"],
    ["Late payment charge", "SGD 120 per instance", "Instalment not received by due date"],
    ["Repricing fee", "SGD 800", "Switching packages within Sample Bank"],
    ["Legal subsidy clawback", "Full subsidy amount", "Redemption within 3 years"],
])}
<h2>5. Loan-to-value limits</h2>
<p>The maximum loan-to-value (LTV) ratio is 75% for a borrower's first outstanding housing loan, 45% for the
second and 35% for the third and subsequent housing loans, in line with Notice R-632 on Residential Property
Loans. A lower LTV applies where the loan tenure exceeds 30 years or extends beyond age 65.</p>
<h2>6. Key risks</h2>
<p>If you choose the floating package, your monthly instalment will rise if 3M SORA rises. You should ensure you
can still afford your instalments if interest rates increase by 3 percentage points. If you fail to pay your
instalments, the bank may take possession of and sell the property, and you remain liable for any shortfall.</p>
<h2>7. Free look and cancellation</h2>
<p>There is no free-look period for housing loans. Cancellation after you accept the Letter of Offer attracts the
cancellation fee shown in section 4. Fire insurance on the property is mandatory for the full loan tenure;
see the Home Protection Insurance PDS for an optional mortgage-linked cover.</p>
<h2>8. Contact</h2>
<p>For enquiries, visit any Sample Bank branch or call the mortgage hotline at 1800-000-0000.</p>
"""


# ── Personal / car loans ───────────────────────────────────────────────────────

PERSONAL_LOAN = f"""
<h1>Personal Instalment Loan — Product Disclosure Sheet</h1>
{meta("PDS-PL-001", "1 March 2026", "Retail Banking, Unsecured Lending", "Public")}
<h2>1. About this product</h2>
<p>The Personal Instalment Loan is an unsecured term loan repaid in equal monthly instalments over 1 to 5 years.
Funds may be used for any personal purpose, including education, renovation, weddings and medical expenses.</p>
<h2>2. Eligibility</h2>
<ul>
<li>Age 21 to 65 years.</li>
<li>Minimum annual income of SGD 20,000 for Singapore citizens and permanent residents; SGD 45,000 for foreigners.</li>
<li>Borrowers with annual income below SGD 30,000 may borrow up to 2 times monthly income; otherwise up to 6 times
monthly income, subject to the unsecured credit limit across all banks.</li>
</ul>
<h2>3. Interest rates</h2>
{table(["Tenure", "Applied rate (p.a.)", "Effective interest rate (p.a.)"], [
    ["1 year", "4.88%", "9.12%"],
    ["2 years", "4.38%", "8.40%"],
    ["3 years", "4.28%", "8.13%"],
    ["5 years", "4.28%", "7.92%"],
])}
<p>The effective interest rate (EIR) reflects the processing fee and the reducing balance of the loan.</p>
<h2>4. Fees and charges</h2>
{table(["Fee", "Amount"], [
    ["Processing fee", "1% of approved loan amount, deducted upfront"],
    ["Early redemption fee", "3% of outstanding principal"],
    ["Late payment charge", "SGD 100 per month"],
])}
<h2>5. Key risks</h2>
<p>An unsecured loan increases your total debt. Missing payments will be reported to the credit bureau and may
affect future borrowing. Lending decisions follow the bank's Responsible Lending Policy.</p>
"""

CAR_LOAN = f"""
<h1>Car Loan — Product Disclosure Sheet</h1>
{meta("PDS-CL-001", "1 February 2026", "Retail Banking, Secured Lending", "Public")}
<h2>1. About this product</h2>
<p>The Sample Bank Car Loan finances the purchase of new and used passenger vehicles registered in Singapore.
The loan is repaid in equal monthly instalments at a flat interest rate.</p>
<h2>2. Financing limits</h2>
{table(["Open market value (OMV) of vehicle", "Maximum loan-to-value", "Maximum tenure"], [
    ["OMV up to SGD 20,000", "70% of purchase price", "7 years"],
    ["OMV above SGD 20,000", "60% of purchase price", "7 years"],
])}
<h2>3. Interest rates</h2>
{table(["Vehicle type", "Flat rate (p.a.)", "Effective interest rate (p.a.)"], [
    ["New car", "2.78%", "5.25%"],
    ["Used car (up to 5 years old)", "3.28%", "6.18%"],
])}
<h2>4. Fees and charges</h2>
{table(["Fee", "Amount"], [
    ["Early full settlement", "Rule of 78 rebate; administrative fee of SGD 300"],
    ["Late payment charge", "SGD 80 per instance"],
])}
<h2>5. Key risks</h2>
<p>The vehicle is mortgaged to the bank until the loan is fully repaid and may be repossessed if instalments are
not paid. Comprehensive motor insurance is mandatory.</p>
"""

FIXED_DEPOSIT = f"""
<h1>SGD Fixed Deposit — Product Disclosure Sheet</h1>
{meta("PDS-FD-001", "1 April 2026", "Retail Banking, Deposits", "Public")}
<h2>1. About this product</h2>
<p>A Fixed Deposit (time deposit) earns a fixed interest rate for a chosen tenure. Interest is paid at maturity.
Deposits are insured up to SGD 100,000 per depositor by the Deposit Insurance Scheme.</p>
<h2>2. Board rates</h2>
<p><b>Table 1: SGD fixed deposit rates (minimum placement SGD 1,000)</b></p>
{table(["Tenure", "SGD 1,000 – 19,999", "SGD 20,000 – 99,999", "SGD 100,000 and above"], [
    ["3 months", "1.20%", "1.35%", "1.45%"],
    ["6 months", "1.40%", "1.55%", "1.65%"],
    ["12 months", "1.60%", "1.75%", "1.90%"],
    ["24 months", "1.50%", "1.60%", "1.70%"],
])}
<h2>3. Premature withdrawal</h2>
<p>If you withdraw before maturity, no interest is paid on the amount withdrawn and an early withdrawal fee of
SGD 30 applies. Partial withdrawal is not allowed; the full deposit must be withdrawn.</p>
<h2>4. Renewal</h2>
<p>Unless instructed otherwise, the deposit is auto-renewed at maturity for the same tenure at the prevailing
board rate.</p>
"""

CREDIT_CARD = f"""
<h1>Credit Card Fees and Charges</h1>
{meta("CFS-CC-002", "1 January 2026", "Cards and Payments", "Public")}
<h2>1. Annual fees</h2>
{table(["Card", "Principal card", "Supplementary card", "First-year fee waiver"], [
    ["Everyday Cashback Card", "SGD 196.20", "SGD 98.10", "Yes"],
    ["Travel Miles Card", "SGD 261.60", "SGD 130.80", "No"],
    ["Platinum Rewards Card", "SGD 196.20", "Free", "Yes"],
])}
<h2>2. Interest and charges</h2>
{table(["Item", "Rate or amount"], [
    ["Interest on retail purchases", "27.80% p.a."],
    ["Cash advance interest", "28.00% p.a., charged from the transaction date"],
    ["Cash advance fee", "8% of amount withdrawn, minimum SGD 15"],
    ["Late payment fee", "SGD 100"],
    ["Overseas transaction fee", "3.25% of the converted amount"],
    ["Minimum payment", "3% of statement balance or SGD 50, whichever is higher"],
])}
<h2>3. Annual fee waiver</h2>
<p>From the second year, the annual fee is waived when the principal cardholder spends at least SGD 10,000 in the
12 months before the fee is charged. Requests for a waiver can be made through the mobile app.</p>
"""

HOME_INSURANCE = f"""
<h1>Home Protection Insurance — Product Disclosure Sheet</h1>
{meta("BI-HP-001", "1 January 2026", "Bancassurance", "Public")}
<h2>1. About this product</h2>
<p>Home Protection Insurance is a fire and home contents policy distributed by Sample Bank and underwritten by a
partner general insurer. It satisfies the fire insurance requirement for Sample Bank Home Loan customers.</p>
<h2>2. Plans</h2>
{table(["Plan", "Building cover", "Contents cover", "Annual premium (incl. GST)"], [
    ["Essential", "Up to SGD 100,000", "SGD 30,000", "SGD 98"],
    ["Enhanced", "Up to SGD 200,000", "SGD 60,000", "SGD 168"],
    ["Prestige", "Up to SGD 400,000", "SGD 120,000", "SGD 298"],
])}
<h2>3. Key exclusions</h2>
<p>The policy does not cover wear and tear, gradual deterioration, damage caused by pests, or losses while the
home is unoccupied for more than 60 consecutive days.</p>
<h2>4. Free look</h2>
<p>You may cancel within 14 days of receiving the policy for a full refund of premium, provided no claim was made.</p>
"""

# ── Internal policies (restricted) ────────────────────────────────────────────

RESPONSIBLE_LENDING = f"""
<h1>Responsible Lending Policy</h1>
{meta("POL-RISK-014", "1 January 2026", "Group Risk Management", "Internal — Restricted")}
<h2>1. Purpose and scope</h2>
<p>This policy sets the minimum credit standards for all consumer lending at Sample Bank. It governs the Home Loan,
Personal Instalment Loan and Car Loan products, and applies to all branches and digital channels. The policy
implements the requirements of Notice R-632 on Residential Property Loans and the Total Debt Servicing Ratio
(TDSR) framework.</p>
<h2>2. Affordability assessment</h2>
<p>Every application must include a full affordability assessment. Gross monthly debt obligations, including the
new facility, must not exceed 55% of gross monthly income (TDSR). For property loans the assessment uses a
medium-term interest rate floor of 4.0% p.a. for residential property, or the actual rate if higher.</p>
<p>Variable income such as commissions and bonuses is subject to a 30% haircut. Rental income is subject to a 30%
haircut and must be supported by a stamped tenancy agreement.</p>
<h2>3. Approval authority</h2>
{table(["Loan amount", "Approval authority", "Second signatory required"], [
    ["Up to SGD 500,000", "Branch credit officer", "No"],
    ["SGD 500,001 – 2,000,000", "Regional credit manager", "Yes"],
    ["Above SGD 2,000,000", "Head of Retail Credit", "Yes, plus Group Risk review"],
])}
<h2>4. Exceptions</h2>
<p>Exceptions to this policy (for example LTV above product limits for staff loans) require written approval from
the Head of Retail Credit and must be logged in the exceptions register within 2 business days. Exceptions are
reported to the Group Risk Committee every quarter. INTERNAL-CANARY-RLP-7731.</p>
<h2>5. Vulnerable customers</h2>
<p>Customers aged 62 and above, or customers who show signs of financial difficulty, must be offered a
plain-language explanation of repayment obligations and a cooling-off review before disbursement.</p>
"""

PRICING_GUIDELINES = f"""
<h1>Retail Loan Pricing Guidelines</h1>
{meta("GL-RB-PRC-003", "1 January 2026", "Retail Banking", "Internal — Restricted")}
<h2>1. Purpose</h2>
<p>These guidelines set the discretionary pricing that frontline staff may offer on the Home Loan, Personal
Instalment Loan and Car Loan. They are governed by the Responsible Lending Policy. Not for distribution to
customers. INTERNAL-CANARY-PRC-4410.</p>
<h2>2. Discretionary discounts</h2>
{table(["Product", "Relationship manager", "Branch manager", "Regional head"], [
    ["Home Loan (spread over SORA)", "Up to 0.05%", "Up to 0.10%", "Up to 0.15%"],
    ["Personal Instalment Loan (applied rate)", "Up to 0.20%", "Up to 0.40%", "Up to 0.60%"],
    ["Car Loan (flat rate)", "Up to 0.10%", "Up to 0.20%", "Up to 0.30%"],
])}
<h2>3. Conditions</h2>
<p>Discounts may only be offered to customers with a Premier relationship or total relationship balance above
SGD 200,000. Discounts cannot be combined with campaign pricing. Every discount must be recorded in the pricing
system with a reason code.</p>
<h2>4. Legal subsidy</h2>
<p>For Home Loans above SGD 500,000, a legal subsidy of up to SGD 2,500 may be granted, subject to clawback if the
loan is redeemed within 3 years.</p>
"""

CDD_POLICY = f"""
<h1>Customer Due Diligence Policy</h1>
{meta("POL-COMP-002", "1 January 2026", "Group Compliance", "Internal")}
<h2>1. Purpose</h2>
<p>This policy describes the customer due diligence (CDD) that must be completed before opening any account or
granting any facility, including the Home Loan, Personal Instalment Loan, Car Loan, Fixed Deposit and credit cards.
It implements Notice R-626 on Prevention of Money Laundering and Countering the Financing of Terrorism.</p>
<h2>2. Standard CDD</h2>
<ul>
<li>Verify identity using an original NRIC, passport or employment pass, or via MyInfo.</li>
<li>Screen the customer against sanctions and adverse news lists before account opening.</li>
<li>Record the purpose of the account and the expected source of funds.</li>
</ul>
<h2>3. Enhanced due diligence</h2>
<p>Enhanced due diligence (EDD) is mandatory for politically exposed persons, customers from higher-risk
jurisdictions and any customer with a risk score of High. EDD requires source-of-wealth evidence and senior
management approval before onboarding.</p>
<h2>4. Periodic review</h2>
{table(["Customer risk rating", "Review frequency"], [
    ["Low", "Every 5 years"],
    ["Medium", "Every 3 years"],
    ["High", "Every year"],
])}
"""


HARDSHIP_POLICY = f"""
<h1>Financial Hardship Assistance Policy</h1>
{meta("POL-RB-021", "1 September 2026", "Retail Banking, Collections and Recoveries", "Internal")}
<h2>1. Purpose and scope</h2>
<p>This policy sets out how Sample Bank helps individual customers who are temporarily unable to meet their
repayments because of job loss, serious illness, disability, the death of a family member or a natural disaster.
It applies to the Home Loan, Car Loan, Personal Instalment Loan and Credit Card. It implements the fair-dealing
expectations in Notice R-640 on Fair Treatment of Customers in Financial Difficulty.</p>
<p>The policy does not apply to business or corporate facilities, or to customers who are already subject to
bankruptcy proceedings.</p>
<h2>2. Eligibility</h2>
<ul>
<li>The customer must have held the facility for at least 6 months before applying.</li>
<li>The account must not be more than 90 days past due at the time of application.</li>
<li>The customer must provide evidence of hardship, such as a retrenchment letter, a medical certificate covering at
least 30 consecutive days, or a death certificate.</li>
<li>Each customer may receive hardship assistance at most twice in any rolling 5-year period.</li>
</ul>
<h2>3. Relief measures by product</h2>
<p><b>Table 1: Maximum relief available</b></p>
{table(["Product", "Relief measure", "Maximum duration", "Interest during relief"], [
    ["Home Loan", "Principal moratorium (interest-only payments)", "12 months", "Contractual rate continues"],
    ["Home Loan", "Tenure extension", "Up to 5 additional years, not beyond age 75", "Contractual rate"],
    ["Car Loan", "Instalment deferral", "3 months", "Deferred interest added to the loan; no compounding"],
    ["Personal Instalment Loan", "Reduced instalment (50% of normal)", "6 months", "Rate reduced to 0% during relief"],
    ["Credit Card", "Balance conversion to a 36-month instalment plan", "36 months", "Fixed 6.0% p.a."],
    ["Credit Card", "Waiver of late payment fees", "6 months", "Not applicable"],
])}
<h2>4. Approval authority</h2>
{table(["Total relief requested", "Approver", "Turnaround time"], [
    ["Up to SGD 50,000 of deferred payments", "Collections team leader", "3 business days"],
    ["SGD 50,001 to SGD 250,000", "Head of Collections", "5 business days"],
    ["Above SGD 250,000", "Head of Retail Credit", "10 business days"],
])}
<p>Applications that fall outside Table 1 are treated as exceptions under the Responsible Lending Policy.</p>
<h2>5. Customer communication</h2>
<p>The bank must acknowledge every hardship application within 2 business days and give the customer a written
decision. If the application is declined, the letter must state the reason and explain how to request a review.
Customers on relief must not be contacted by external collection agencies.</p>
<h2>6. Credit reporting</h2>
<p>Accounts on an approved relief plan are reported to the credit bureau as "restructured" and not as "delinquent",
provided the customer meets the revised payment terms.</p>
<h2>7. Monitoring and review</h2>
<p>Collections reviews every account on relief 30 days before the relief period ends. Group Risk Management reports
hardship volumes and the 12-month re-default rate to the Group Risk Committee every quarter. This policy is
reviewed every 2 years, or earlier if Notice R-640 is amended.</p>
<h2>8. Record keeping</h2>
<p>All hardship applications, evidence and decisions must be kept for at least 5 years after the facility is closed.</p>
"""


def near_duplicate_home_loan() -> str:
    # Same content as v1 with a different title and a small wording change — for the near-duplicate demo.
    return home_loan(1).replace("Home Loan — Product Disclosure Sheet", "Housing Loan Factsheet").replace(
        "mortgage hotline", "home loan hotline"
    )


SAMPLES = [
    # file, html, metadata, load_at_seed
    ("home_loan_pds_v1.pdf", home_loan(1), dict(title="Home Loan Product Disclosure Sheet", business_unit="Retail Banking", category="Loans", product="Home Loan", access_group="RETAIL_PRODUCTS", effective_date="2026-01-01"), True),
    ("personal_loan_pds.pdf", PERSONAL_LOAN, dict(title="Personal Instalment Loan Product Disclosure Sheet", business_unit="Retail Banking", category="Loans", product="Personal Loan", access_group="RETAIL_PRODUCTS", effective_date="2026-03-01"), True),
    ("car_loan_pds.pdf", CAR_LOAN, dict(title="Car Loan Product Disclosure Sheet", business_unit="Retail Banking", category="Loans", product="Car Loan", access_group="RETAIL_PRODUCTS", effective_date="2026-02-01"), True),
    ("fixed_deposit_pds.pdf", FIXED_DEPOSIT, dict(title="SGD Fixed Deposit Product Disclosure Sheet", business_unit="Retail Banking", category="Funding", product="Fixed Deposit", access_group="RETAIL_PRODUCTS", effective_date="2026-04-01"), True),
    ("credit_card_fees.pdf", CREDIT_CARD, dict(title="Credit Card Fees and Charges", business_unit="Cards and Payments", category="CFS", product="Credit Card", access_group="RETAIL_PRODUCTS", effective_date="2026-01-01"), True),
    ("home_protection_insurance.pdf", HOME_INSURANCE, dict(title="Home Protection Insurance Product Disclosure Sheet", business_unit="Bancassurance", category="Insurance", product="Home Protection Insurance", access_group="RETAIL_PRODUCTS", effective_date="2026-01-01"), True),
    ("cdd_policy.pdf", CDD_POLICY, dict(title="Customer Due Diligence Policy", business_unit="Group Compliance", category="Policy", product="", access_group="RETAIL_PRODUCTS", effective_date="2026-01-01"), True),
    ("responsible_lending_policy.pdf", RESPONSIBLE_LENDING, dict(title="Responsible Lending Policy", business_unit="Group Risk Management", category="Policy", product="", access_group="RISK_POLICY", effective_date="2026-01-01"), True),
    ("loan_pricing_guidelines.pdf", PRICING_GUIDELINES, dict(title="Retail Loan Pricing Guidelines", business_unit="Retail Banking", category="Policy", product="", access_group="RISK_POLICY", effective_date="2026-01-01"), True),
    # Live-demo files, not loaded at seed time:
    ("home_loan_pds_v2.pdf", home_loan(2), dict(title="Home Loan Product Disclosure Sheet", business_unit="Retail Banking", category="Loans", product="Home Loan", access_group="RETAIL_PRODUCTS", effective_date="2026-10-01"), False),
    ("financial_hardship_policy.pdf", HARDSHIP_POLICY, dict(title="Financial Hardship Assistance Policy", business_unit="Retail Banking", category="Policy", product="", access_group="RETAIL_PRODUCTS", effective_date="2026-09-01"), False),
    ("housing_loan_factsheet.pdf", near_duplicate_home_loan(), dict(title="Housing Loan Factsheet", business_unit="Retail Banking", category="Loans", product="Home Loan", access_group="RETAIL_PRODUCTS", effective_date="2026-01-01"), False),
]


def render(html: str, path: Path) -> None:
    story = fitz.Story(html=f"<body>{html}</body>", user_css=CSS)
    writer = fitz.DocumentWriter(str(path))
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (54, 54, -54, -64)
    more = 1
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    doc = fitz.open(str(path))
    for i, page in enumerate(doc, start=1):
        page.insert_text(
            (54, mediabox.height - 36),
            f"Sample Bank (fictional) · Synthetic document for the Enterprise Knowledge Base POC · Page {i} of {doc.page_count}",
            fontsize=7.5,
            color=(0.4, 0.4, 0.4),
        )
    doc.save(str(path) + ".tmp")
    doc.close()
    Path(str(path) + ".tmp").replace(path)


def main(out_dir: str = "/samples") -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, html, _, _ in SAMPLES:
        render(html, out / name)
        print("wrote", out / name)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/samples")
