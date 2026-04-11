#!/usr/bin/env python3
"""Seed deterministic eval dataset into DuckDB.

Run: python -m scripts.seed_eval_data
Or:  make seed-eval
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import duckdb
from faker import Faker

SEED = 42
DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "duckdb" / "eval.db"

fake = Faker()
Faker.seed(SEED)
random.seed(SEED)

SEGMENTS = ["retail", "business", "premium"]
SEGMENT_WEIGHTS = [0.5, 0.3, 0.2]
REGIONS = ["northeast", "southeast", "midwest", "west"]
ACCOUNT_TYPES = ["checking", "savings", "money_market"]
LOAN_TYPES = ["personal", "auto", "mortgage", "business"]
TXN_CATEGORIES = ["payroll", "utilities", "transfer", "merchant", "atm", "wire"]


def create_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Drop and recreate all 5 eval tables."""
    for table in ("transactions", "loans", "accounts", "daily_rates", "customers"):
        con.execute(f"DROP TABLE IF EXISTS {table}")

    con.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            segment VARCHAR NOT NULL,
            region VARCHAR NOT NULL,
            join_date DATE NOT NULL,
            credit_score INTEGER NOT NULL,
            is_active BOOLEAN NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE accounts (
            account_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            account_type VARCHAR NOT NULL,
            opened_date DATE NOT NULL,
            balance DECIMAL(12, 2) NOT NULL,
            status VARCHAR NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE transactions (
            txn_id INTEGER PRIMARY KEY,
            account_id INTEGER NOT NULL,
            txn_date DATE NOT NULL,
            amount DECIMAL(12, 2) NOT NULL,
            category VARCHAR NOT NULL,
            counterparty VARCHAR NOT NULL,
            description VARCHAR NOT NULL,
            is_flagged BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    con.execute("""
        CREATE TABLE loans (
            loan_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            loan_type VARCHAR NOT NULL,
            principal DECIMAL(12, 2) NOT NULL,
            interest_rate DECIMAL(4, 2) NOT NULL,
            term_months INTEGER NOT NULL,
            origination_date DATE NOT NULL,
            status VARCHAR NOT NULL,
            monthly_payment DECIMAL(10, 2) NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE daily_rates (
            rate_date DATE PRIMARY KEY,
            fed_funds_rate DECIMAL(4, 2) NOT NULL,
            prime_rate DECIMAL(4, 2) NOT NULL,
            mortgage_30y DECIMAL(4, 2) NOT NULL,
            savings_apy DECIMAL(4, 2) NOT NULL
        )
    """)


def seed_customers(con: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    """Generate 200 customers with segment-correlated credit scores."""
    base_scores = {"retail": 650, "business": 700, "premium": 750}
    customers: list[dict[str, object]] = []

    for i in range(1, 201):
        segment = random.choices(SEGMENTS, weights=SEGMENT_WEIGHTS, k=1)[0]
        credit_score = max(580, min(850, base_scores[segment] + random.randint(-70, 100)))
        join_date = date(2020, 1, 1) + timedelta(days=random.randint(0, 2190))
        is_active = random.random() < 0.9

        customer: dict[str, object] = {
            "customer_id": i,
            "name": fake.name(),
            "segment": segment,
            "region": random.choice(REGIONS),
            "join_date": join_date,
            "credit_score": credit_score,
            "is_active": is_active,
        }
        customers.append(customer)
        con.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)",
            [i, customer["name"], segment, customer["region"],
             join_date, credit_score, is_active],
        )
    return customers


def seed_accounts(
    con: duckdb.DuckDBPyConnection,
    customers: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Generate ~400 accounts linked to customers."""
    balance_ranges = {
        "retail": (500, 15_000),
        "business": (5_000, 100_000),
        "premium": (20_000, 500_000),
    }
    accounts: list[dict[str, object]] = []
    account_id = 1

    for cust in customers:
        num = random.choices([1, 2, 3], weights=[0.25, 0.50, 0.25], k=1)[0]
        for _ in range(num):
            acct_type = random.choice(ACCOUNT_TYPES)
            seg = str(cust["segment"])
            lo, hi = balance_ranges[seg]
            balance = round(random.uniform(lo, hi), 2)
            join = cust["join_date"]
            assert isinstance(join, date)
            opened = join + timedelta(days=random.randint(0, 365))
            status = random.choices(
                ["active", "dormant", "closed"],
                weights=[0.85, 0.10, 0.05],
                k=1,
            )[0]

            account: dict[str, object] = {
                "account_id": account_id,
                "customer_id": cust["customer_id"],
                "account_type": acct_type,
                "opened_date": opened,
                "balance": balance,
                "status": status,
            }
            accounts.append(account)
            con.execute(
                "INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?)",
                [account_id, cust["customer_id"], acct_type, opened, balance, status],
            )
            account_id += 1
    return accounts


def _plant_anomalies(
    con: duckdb.DuckDBPyConnection,
    accounts: list[dict[str, object]],
    start_txn_id: int,
) -> int:
    """Plant 6 anomaly groups (3 true + 3 false positive) in Q3 2025.

    Returns the next available txn_id.
    """
    txn_id = start_txn_id
    dormant = [a for a in accounts if a["status"] == "dormant"]
    active = [a for a in accounts if a["status"] == "active"]

    # A1: $47,000 wire from dormant account — stolen credentials
    a1_acct = dormant[0] if dormant else active[0]
    con.execute(
        "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [txn_id, a1_acct["account_id"], date(2025, 7, 14), -47_000.00,
         "wire", "Unknown Entity LLC", "Wire transfer — urgent request", True],
    )
    txn_id += 1

    # A2: 12 ATM withdrawals in 2 hours across 3 cities — card cloning
    a2_acct = active[0]
    cities = ["New York ATM #4412", "Chicago ATM #7891", "Miami ATM #2234"]
    for j in range(12):
        amt = round(random.uniform(200, 500), 2)
        con.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [txn_id, a2_acct["account_id"], date(2025, 8, 3), -amt,
             "atm", cities[j % 3], f"ATM withdrawal #{j + 1}", True],
        )
        txn_id += 1

    # A3: Series of transfers to shell company — never seen before
    a3_acct = active[1]
    for j in range(4):
        amt = round(random.uniform(5_000, 15_000), 2)
        d = date(2025, 8, 10) + timedelta(days=j * 7)
        con.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [txn_id, a3_acct["account_id"], d, -amt,
             "transfer", "Oceanic Holdings Ltd",
             f"Transfer to Oceanic Holdings — invoice {1000 + j}", True],
        )
        txn_id += 1

    # A4: $15,000 deposit — annual bonus (FALSE POSITIVE)
    a4_acct = active[2]
    con.execute(
        "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [txn_id, a4_acct["account_id"], date(2025, 7, 7), 15_000.00,
         "payroll", "Acme Corporation", "Annual Performance Bonus 2025", True],
    )
    txn_id += 1

    # A5: $50,000 savings→checking — house purchase (FALSE POSITIVE)
    a5_acct = active[3]
    con.execute(
        "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [txn_id, a5_acct["account_id"], date(2025, 8, 20), 50_000.00,
         "transfer", "Self — savings closure",
         "Transfer from savings — home purchase down payment", True],
    )
    txn_id += 1

    # A6: 8 small merchant charges on Saturday — shopping trip (FALSE POSITIVE)
    a6_acct = active[4]
    merchants = [
        "Target", "Whole Foods", "Home Depot", "Starbucks",
        "Best Buy", "CVS Pharmacy", "Trader Joe's", "Shell Gas",
    ]
    for j in range(8):
        amt = round(random.uniform(8, 120), 2)
        con.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [txn_id, a6_acct["account_id"], date(2025, 9, 6), -amt,
             "merchant", merchants[j], f"Purchase at {merchants[j]}", True],
        )
        txn_id += 1

    return txn_id


def seed_transactions(
    con: duckdb.DuckDBPyConnection,
    accounts: list[dict[str, object]],
) -> None:
    """Generate ~5000 transactions for 2025 with planted anomalies."""
    txn_id = 1
    txn_id = _plant_anomalies(con, accounts, txn_id)

    active_accounts = [a for a in accounts if a["status"] != "closed"]
    target_normal = 5000 - (txn_id - 1)
    counterparties: dict[str, list[str]] = {
        "payroll": ["Acme Corp", "TechCo Inc", "Global Services LLC"],
        "utilities": ["City Electric", "Water Authority", "Internet Plus"],
        "transfer": ["Chase Bank", "Wells Fargo", "Internal Transfer"],
        "merchant": ["Amazon", "Walmart", "Target", "Costco", "Best Buy"],
        "atm": ["Bank ATM #101", "Bank ATM #202", "Partner ATM #303"],
        "wire": ["First National Wire", "International Wire Svc"],
    }
    cat_weights = [0.20, 0.15, 0.15, 0.30, 0.10, 0.10]

    for _ in range(target_normal):
        acct = random.choice(active_accounts)
        category = random.choices(TXN_CATEGORIES, weights=cat_weights, k=1)[0]
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        txn_date = date(2025, month, day)

        if category == "payroll":
            amount = round(random.uniform(2_000, 8_000), 2)
        elif category == "utilities":
            amount = -round(random.uniform(50, 300), 2)
        elif category == "transfer":
            amount = round(random.uniform(-5_000, 5_000), 2)
        elif category == "merchant":
            base = random.uniform(10, 500)
            if month in (11, 12):
                base *= 1.5  # holiday spending spike
            amount = -round(base, 2)
        elif category == "atm":
            amount = -round(random.uniform(20, 500), 2)
        else:  # wire
            amount = round(random.uniform(-10_000, 10_000), 2)

        cp = random.choice(counterparties[category])
        con.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [txn_id, acct["account_id"], txn_date, amount,
             category, cp, f"{category.title()} — {cp}", False],
        )
        txn_id += 1


def seed_loans(
    con: duckdb.DuckDBPyConnection,
    customers: list[dict[str, object]],
) -> None:
    """Generate 80 loans with credit-score-correlated rates and default patterns."""
    loan_customers = random.sample(customers, 80)
    principal_ranges = {
        "personal": (5_000, 30_000),
        "auto": (10_000, 50_000),
        "mortgage": (100_000, 500_000),
        "business": (25_000, 200_000),
    }
    term_ranges = {
        "personal": (12, 60),
        "auto": (24, 72),
        "mortgage": (180, 360),
        "business": (12, 120),
    }
    region_risk = {"southeast": 1.5, "midwest": 1.2, "northeast": 1.0, "west": 0.8}

    for i, cust in enumerate(loan_customers):
        loan_type = random.choices(
            LOAN_TYPES, weights=[0.30, 0.25, 0.25, 0.20], k=1,
        )[0]
        lo, hi = principal_ranges[loan_type]
        principal = round(random.uniform(lo, hi), 2)

        score = int(cust["credit_score"])  # type: ignore[arg-type]
        base_rate = 18.0 - (score - 580) * (14.5 / 270)
        interest_rate = round(max(3.5, min(18.0, base_rate + random.uniform(-1, 1))), 2)

        term = random.randint(*term_ranges[loan_type])
        orig_date = date(2021, 1, 1) + timedelta(days=random.randint(0, 1460))

        monthly_rate = interest_rate / 100 / 12
        if monthly_rate > 0:
            payment = principal * monthly_rate / (1 - (1 + monthly_rate) ** -term)
        else:
            payment = principal / term
        monthly_payment = round(payment, 2)

        region = str(cust["region"])
        default_prob = max(0.02, 0.35 - (score - 580) * 0.001)
        default_prob *= region_risk.get(region, 1.0)
        roll = random.random()
        if roll < default_prob * 0.4:
            status = "default"
        elif roll < default_prob:
            status = "delinquent"
        elif roll < 0.85:
            status = "current"
        else:
            status = "paid_off"

        con.execute(
            "INSERT INTO loans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [i + 1, cust["customer_id"], loan_type, principal,
             interest_rate, term, orig_date, status, monthly_payment],
        )


def seed_daily_rates(con: duckdb.DuckDBPyConnection) -> None:
    """Generate 365 daily rate records for 2025 with two fed rate cuts."""
    fed_rate = 5.25
    for day_offset in range(365):
        d = date(2025, 1, 1) + timedelta(days=day_offset)
        if d == date(2025, 6, 15):
            fed_rate = 5.00
        elif d == date(2025, 9, 15):
            fed_rate = 4.75
        prime = round(fed_rate + 3.0, 2)
        mortgage = round(prime + 0.5 + random.uniform(0, 1.0), 2)
        savings = round(4.0 + random.uniform(-0.5, 0.5), 2)
        con.execute(
            "INSERT INTO daily_rates VALUES (?, ?, ?, ?, ?)",
            [d, fed_rate, prime, mortgage, savings],
        )


def get_row_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Return row counts for all eval tables."""
    tables = ["customers", "accounts", "transactions", "loans", "daily_rates"]
    counts: dict[str, int] = {}
    for table in tables:
        result = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        counts[table] = result[0] if result else 0
    return counts


def seed_all(db_path: Path) -> dict[str, int]:
    """Seed all eval tables into the given database path. Returns row counts."""
    # Reset seeds for determinism on every call (idempotency)
    Faker.seed(SEED)
    random.seed(SEED)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        create_tables(con)
        customers = seed_customers(con)
        accounts = seed_accounts(con, customers)
        seed_transactions(con, accounts)
        seed_loans(con, customers)
        seed_daily_rates(con)
        return get_row_counts(con)
    finally:
        con.close()


if __name__ == "__main__":
    counts = seed_all(DB_PATH)
    print("Eval dataset seeded successfully:")
    for table, count in counts.items():
        print(f"  {table}: {count} rows")
    con = duckdb.connect(str(DB_PATH))
    flagged = con.execute("SELECT COUNT(*) FROM transactions WHERE is_flagged").fetchone()
    con.close()
    print(f"  flagged anomalies: {flagged[0] if flagged else 0} transactions")
