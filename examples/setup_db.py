"""
CloudMetrics Database Setup & Synthetic Data Generator

Creates an SQLite database with 5 tables and populates them with
realistic synthetic data for a B2B SaaS subscription analytics demo.

Usage: python setup_db.py
"""

import sqlite3
import random
import os
from datetime import datetime, timedelta
from faker import Faker

# Reproducible data
random.seed(42)
fake = Faker()
Faker.seed(42)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloudmetrics.db")

# --- Configuration ---

INDUSTRIES = ["Technology", "Healthcare", "Finance", "Retail", "Education", "Manufacturing"]
INDUSTRY_WEIGHTS = [30, 15, 20, 15, 10, 10]

COMPANY_SIZES = ["Startup", "SMB", "Mid-Market", "Enterprise"]
SIZE_WEIGHTS = [40, 30, 20, 10]

COUNTRIES = ["United States", "United Kingdom", "Canada", "Germany", "Australia",
             "France", "India", "Brazil", "Japan", "Netherlands"]
COUNTRY_WEIGHTS = [40, 12, 8, 8, 6, 6, 6, 5, 5, 4]

ACCOUNT_OWNERS = ["Alice Johnson", "Bob Smith", "Carol Williams", "David Brown",
                  "Eva Martinez", "Frank Lee", "Grace Chen", "Henry Wilson"]

PLANS = [
    (1, "Starter", 29.0, 5, "task_mgmt,basic_reports"),
    (2, "Professional", 79.0, 20, "task_mgmt,advanced_reports,integrations"),
    (3, "Business", 149.0, 50, "task_mgmt,advanced_reports,integrations,api_access,sso"),
    (4, "Enterprise", 299.0, 200, "task_mgmt,advanced_reports,integrations,api_access,sso,custom_branding,dedicated_support"),
]

# Plan selection weights by company size
PLAN_WEIGHTS_BY_SIZE = {
    "Startup":    [50, 30, 15, 5],
    "SMB":        [20, 40, 30, 10],
    "Mid-Market": [5, 20, 45, 30],
    "Enterprise": [2, 8, 30, 60],
}

TICKET_SUBJECTS = {
    "billing": [
        "Invoice discrepancy for {month}",
        "Unable to update payment method",
        "Question about pricing for annual plan",
        "Refund request for double charge",
        "Need updated billing address",
    ],
    "technical": [
        "Cannot export report to PDF",
        "Dashboard loading slowly",
        "API timeout errors on bulk requests",
        "SSO login not working with Okta",
        "Data sync delay with Salesforce integration",
    ],
    "feature_request": [
        "Add Gantt chart view for projects",
        "Support for custom fields in tasks",
        "Dark mode for the web interface",
        "Mobile app notifications for deadlines",
        "Bulk task import from CSV",
    ],
    "onboarding": [
        "Need help setting up team workspace",
        "How to configure user roles and permissions",
        "Migration assistance from Asana",
        "Training session request for our team",
        "Help importing existing project data",
    ],
    "bug": [
        "Task status not updating after drag-and-drop",
        "Email notifications sent to wrong recipients",
        "Calendar view shows incorrect dates",
        "File attachments lost after page refresh",
        "Search results not returning recent items",
    ],
}

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


def create_tables(conn):
    """Create all 5 tables with proper schema."""
    conn.executescript("""
        DROP TABLE IF EXISTS support_tickets;
        DROP TABLE IF EXISTS invoices;
        DROP TABLE IF EXISTS subscriptions;
        DROP TABLE IF EXISTS plans;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            company_name TEXT NOT NULL,
            industry TEXT NOT NULL,
            company_size TEXT NOT NULL,
            country TEXT NOT NULL,
            signup_date DATE NOT NULL,
            account_owner TEXT NOT NULL
        );

        CREATE TABLE plans (
            plan_id INTEGER PRIMARY KEY,
            plan_name TEXT NOT NULL,
            monthly_price REAL NOT NULL,
            max_users INTEGER NOT NULL,
            features TEXT NOT NULL
        );

        CREATE TABLE subscriptions (
            subscription_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            plan_id INTEGER NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE,
            status TEXT NOT NULL,
            billing_cycle TEXT NOT NULL,
            mrr REAL NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (plan_id) REFERENCES plans(plan_id)
        );

        CREATE TABLE invoices (
            invoice_id INTEGER PRIMARY KEY,
            subscription_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            invoice_date DATE NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            FOREIGN KEY (subscription_id) REFERENCES subscriptions(subscription_id),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE support_tickets (
            ticket_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            created_at DATETIME NOT NULL,
            resolved_at DATETIME,
            priority TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL,
            subject TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );
    """)


def generate_plans(conn):
    """Insert the 4 fixed plan tiers."""
    conn.executemany(
        "INSERT INTO plans VALUES (?, ?, ?, ?, ?)",
        PLANS
    )
    return {p[0]: p for p in PLANS}


def generate_customers(conn, n=200):
    """Generate n customer records."""
    customers = []
    # Signup dates weighted toward more recent (2022-01 to 2025-10)
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2025, 10, 31)
    total_days = (end_date - start_date).days

    for i in range(1, n + 1):
        # Weight toward recent dates using a power distribution
        day_offset = int(total_days * (random.random() ** 0.6))
        signup = start_date + timedelta(days=day_offset)

        customer = (
            i,
            fake.company(),
            random.choices(INDUSTRIES, weights=INDUSTRY_WEIGHTS)[0],
            random.choices(COMPANY_SIZES, weights=SIZE_WEIGHTS)[0],
            random.choices(COUNTRIES, weights=COUNTRY_WEIGHTS)[0],
            signup.strftime("%Y-%m-%d"),
            random.choice(ACCOUNT_OWNERS),
        )
        customers.append(customer)

    conn.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)",
        customers
    )
    return customers


def generate_subscriptions(conn, customers, plans):
    """Generate subscriptions for each customer (1-3 per customer)."""
    subscriptions = []
    sub_id = 1
    today = datetime(2025, 11, 15)

    for cust in customers:
        cust_id = cust[0]
        company_size = cust[3]
        signup_date = datetime.strptime(cust[5], "%Y-%m-%d")

        # Number of subscriptions: 70% have 1, 20% have 2, 10% have 3
        r = random.random()
        if r < 0.70:
            num_subs = 1
        elif r < 0.90:
            num_subs = 2
        else:
            num_subs = 3

        plan_weights = PLAN_WEIGHTS_BY_SIZE[company_size]
        current_start = signup_date

        for j in range(num_subs):
            plan_id = random.choices([1, 2, 3, 4], weights=plan_weights)[0]
            plan_price = plans[plan_id][2]

            # MRR with +/-10% variance for discounts/add-ons
            mrr = round(plan_price * random.uniform(0.90, 1.10), 2)

            # Billing cycle: Enterprise skews annual
            if company_size == "Enterprise":
                billing_cycle = random.choices(["monthly", "annual"], weights=[30, 70])[0]
            else:
                billing_cycle = random.choices(["monthly", "annual"], weights=[60, 40])[0]

            is_last_sub = (j == num_subs - 1)

            if is_last_sub:
                # Latest subscription: mostly active
                r2 = random.random()
                if r2 < 0.80:
                    status = "active"
                    end_date = None
                elif r2 < 0.85:
                    status = "trial"
                    end_date = None
                elif r2 < 0.90:
                    status = "paused"
                    end_date = None
                else:
                    status = "churned"
                    days_active = random.randint(30, 365)
                    end_date = min(current_start + timedelta(days=days_active), today)
            else:
                # Older subscriptions are always churned
                status = "churned"
                days_active = random.randint(60, 540)
                end_date = min(current_start + timedelta(days=days_active), today - timedelta(days=30))

            sub = (
                sub_id,
                cust_id,
                plan_id,
                current_start.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d") if end_date else None,
                status,
                billing_cycle,
                mrr,
            )
            subscriptions.append(sub)
            sub_id += 1

            # Next subscription starts after this one ends
            if end_date:
                current_start = end_date + timedelta(days=random.randint(1, 30))
                if current_start > today:
                    break
            # Shift plan weights toward higher tiers for upgrades
            plan_weights = [max(0, w - 10) for w in plan_weights[:2]] + \
                           [min(60, w + 10) for w in plan_weights[2:]]

    conn.executemany(
        "INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        subscriptions
    )
    return subscriptions


def generate_invoices(conn, subscriptions):
    """Generate invoices for each subscription (one per billing period)."""
    invoices = []
    inv_id = 1
    today = datetime(2025, 11, 15)

    for sub in subscriptions:
        sub_id, cust_id, _, start_str, end_str, status, billing_cycle, mrr = sub
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d") if end_str else today

        if billing_cycle == "annual":
            # One invoice per year
            current = start
            while current <= end:
                amount = round(mrr * 12, 2)
                days_ago = (today - current).days

                # Status: recent invoices can be pending
                if days_ago < 30:
                    inv_status = random.choices(
                        ["paid", "pending", "overdue", "refunded"],
                        weights=[70, 20, 5, 5]
                    )[0]
                else:
                    inv_status = random.choices(
                        ["paid", "pending", "overdue", "refunded"],
                        weights=[92, 2, 3, 3]
                    )[0]

                payment = random.choices(
                    ["credit_card", "bank_transfer", "paypal"],
                    weights=[60, 25, 15]
                )[0]

                invoices.append((
                    inv_id, sub_id, cust_id,
                    current.strftime("%Y-%m-%d"),
                    amount, inv_status, payment
                ))
                inv_id += 1
                current = datetime(current.year + 1, current.month, current.day)
        else:
            # One invoice per month
            current = start
            while current <= end:
                amount = round(mrr, 2)
                days_ago = (today - current).days

                if days_ago < 30:
                    inv_status = random.choices(
                        ["paid", "pending", "overdue", "refunded"],
                        weights=[70, 20, 5, 5]
                    )[0]
                else:
                    inv_status = random.choices(
                        ["paid", "pending", "overdue", "refunded"],
                        weights=[92, 2, 3, 3]
                    )[0]

                payment = random.choices(
                    ["credit_card", "bank_transfer", "paypal"],
                    weights=[60, 25, 15]
                )[0]

                invoices.append((
                    inv_id, sub_id, cust_id,
                    current.strftime("%Y-%m-%d"),
                    amount, inv_status, payment
                ))
                inv_id += 1

                # Move to next month
                if current.month == 12:
                    current = datetime(current.year + 1, 1, current.day)
                else:
                    try:
                        current = datetime(current.year, current.month + 1, current.day)
                    except ValueError:
                        current = datetime(current.year, current.month + 1, 28)

    conn.executemany(
        "INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?)",
        invoices
    )
    return invoices


def generate_support_tickets(conn, customers):
    """Generate support tickets for each customer."""
    tickets = []
    ticket_id = 1
    today = datetime(2025, 11, 15)

    categories = ["billing", "technical", "feature_request", "onboarding", "bug"]
    category_weights = [20, 30, 15, 20, 15]
    priorities = ["low", "medium", "high", "critical"]
    priority_weights = [30, 40, 20, 10]

    for cust in customers:
        cust_id = cust[0]
        signup_date = datetime.strptime(cust[5], "%Y-%m-%d")

        # 0-12 tickets per customer
        num_tickets = max(0, int(random.gauss(4, 2.5)))
        num_tickets = min(num_tickets, 12)

        for _ in range(num_tickets):
            # Created after signup
            days_since_signup = (today - signup_date).days
            if days_since_signup <= 0:
                continue
            created_offset = random.randint(0, days_since_signup)
            created_at = signup_date + timedelta(
                days=created_offset,
                hours=random.randint(8, 18),
                minutes=random.randint(0, 59)
            )

            category = random.choices(categories, weights=category_weights)[0]
            priority = random.choices(priorities, weights=priority_weights)[0]

            # 85% resolved
            if random.random() < 0.85:
                # Log-normal resolution time (median ~2 days)
                resolution_hours = random.lognormvariate(3.5, 1.0)
                resolution_hours = min(resolution_hours, 720)  # cap at 30 days
                resolved_at = created_at + timedelta(hours=resolution_hours)
                if resolved_at > today:
                    resolved_at = None
                    ticket_status = random.choice(["open", "in_progress"])
                else:
                    ticket_status = random.choice(["resolved", "closed"])
            else:
                resolved_at = None
                ticket_status = random.choice(["open", "in_progress"])

            # Generate subject from templates
            subject_template = random.choice(TICKET_SUBJECTS[category])
            subject = subject_template.format(month=random.choice(MONTHS))

            tickets.append((
                ticket_id, cust_id,
                created_at.strftime("%Y-%m-%d %H:%M:%S"),
                resolved_at.strftime("%Y-%m-%d %H:%M:%S") if resolved_at else None,
                priority, category, ticket_status, subject
            ))
            ticket_id += 1

    conn.executemany(
        "INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        tickets
    )
    return tickets


def main():
    # Remove existing DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    print("Creating CloudMetrics database...")
    print(f"Database path: {DB_PATH}\n")

    create_tables(conn)

    plans = generate_plans(conn)
    print(f"  plans:            {len(plans)} rows")

    customers = generate_customers(conn, n=200)
    print(f"  customers:        {len(customers)} rows")

    subscriptions = generate_subscriptions(conn, customers, plans)
    print(f"  subscriptions:    {len(subscriptions)} rows")

    invoices = generate_invoices(conn, subscriptions)
    print(f"  invoices:         {len(invoices)} rows")

    tickets = generate_support_tickets(conn, customers)
    print(f"  support_tickets:  {len(tickets)} rows")

    conn.commit()

    # Verify foreign key integrity
    cursor = conn.execute("PRAGMA foreign_key_check")
    fk_errors = cursor.fetchall()
    if fk_errors:
        print(f"\nWARNING: {len(fk_errors)} foreign key violations found!")
    else:
        print("\nForeign key integrity: OK")

    total = len(plans) + len(customers) + len(subscriptions) + len(invoices) + len(tickets)
    print(f"\nTotal rows generated: {total}")
    print("Database setup complete!")

    conn.close()


if __name__ == "__main__":
    main()
