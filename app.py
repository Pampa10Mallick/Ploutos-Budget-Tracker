

import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import date, timedelta

# ---------------- PAGE SETUP ----------------
st.set_page_config(
    page_title="Ploutos",
    page_icon="💸",
    layout="wide"
)

DB_PATH = Path(__file__).parent / "broke_no_more.db"

CATEGORIES = [
    "Food & Drinks", "Transport", "Shopping",
    "Education", "Entertainment", "Bills",
    "Subscriptions", "Health", "Other"
]


# ---------------- DATABASE ----------------
def setup_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                txn_date TEXT NOT NULL,
                txn_type TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                note TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            )
        """)

        conn.execute("""
            INSERT OR IGNORE INTO settings
            (setting_key, setting_value)
            VALUES ('monthly_budget', '10000')
        """)


def add_transaction(txn_date, txn_type, category, amount, note):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO transactions
            (txn_date, txn_type, category, amount, note)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(txn_date), txn_type, category,
            float(amount), note.strip()
        ))


def load_transactions():
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("""
            SELECT * FROM transactions
            ORDER BY txn_date DESC, id DESC
        """, conn)


def get_budget():
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("""
            SELECT setting_value FROM settings
            WHERE setting_key = 'monthly_budget'
        """).fetchone()

    return float(row[0]) if row else 10000.0


def save_budget(amount):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO settings (setting_key, setting_value)
            VALUES ('monthly_budget', ?)
            ON CONFLICT(setting_key)
            DO UPDATE SET setting_value = excluded.setting_value
        """, (str(float(amount)),))


def delete_transaction(transaction_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM transactions WHERE id = ?",
            (int(transaction_id),)
        )


setup_database()


# ---------------- DESIGN ----------------
st.markdown("""
<style>

.stApp {
    background-color: #0B1020;
    color: #F3F4F6;
}

.block-container {
    padding-top: 2rem;
    max-width: 1200px;
}
[data-testid="stMetric"] {
    background: #151C30;
    border: 1px solid #E4E7EC;
    padding: 20px;
    border-radius: 14px;
}
</style>
""", unsafe_allow_html=True)


# ---------------- SIDEBAR ----------------
st.sidebar.title("💸 Ploutos")
st.sidebar.caption("Your money. Your rules.")

page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Transactions", "Smart Tools"]
)


# ---------------- DATA ----------------
df = load_transactions()
today = date.today()
month_start = today.replace(day=1)
budget = get_budget()

if not df.empty:
    df["txn_date"] = pd.to_datetime(
        df["txn_date"], errors="coerce"
    ).dt.date

    df["amount"] = pd.to_numeric(
        df["amount"], errors="coerce"
    ).fillna(0)

    current_month = df[
        (df["txn_date"] >= month_start) &
        (df["txn_date"] <= today)
    ].copy()

    income = current_month.loc[
        current_month["txn_type"] == "Income", "amount"
    ].sum()

    spending = current_month.loc[
        current_month["txn_type"] == "Expense", "amount"
    ].sum()

    total_income = df.loc[
        df["txn_type"] == "Income", "amount"
    ].sum()

    total_expenses = df.loc[
        df["txn_type"] == "Expense", "amount"
    ].sum()
else:
    current_month = pd.DataFrame()
    income = spending = total_income = total_expenses = 0.0

remaining = budget - spending

# Number of calendar days remaining in this month,
# including today.
next_month = today.replace(day=28) + timedelta(days=4)
month_end = next_month.replace(day=1) - timedelta(days=1)
days_left = max((month_end - today).days + 1, 1)

safe_daily = max(remaining, 0) / days_left
balance = total_income - total_expenses


# ---------------- DASHBOARD ----------------
if page == "Dashboard":
    st.title("Good day! Here's your money snapshot.")
    st.caption(today.strftime("%A, %d %B %Y"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Balance", f"₹{balance:,.0f}")
    c2.metric("Spent This Month", f"₹{spending:,.0f}")
    c3.metric("Safe to Spend / Day", f"₹{safe_daily:,.0f}")
    c4.metric(
        "Budget Remaining",
        f"₹{remaining:,.0f}",
        delta=f"{remaining / budget:.0%} left" if budget else None
    )

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("Spending by category")

        if not current_month.empty:
            expenses = current_month[
                current_month["txn_type"] == "Expense"
            ]

            if not expenses.empty:
                category_totals = expenses.groupby(
                    "category"
                )["amount"].sum().sort_values(ascending=False)

                st.bar_chart(category_totals)
            else:
                st.info("No expenses recorded this month yet.")
        else:
            st.info("Add a transaction to see your chart.")

    with right:
        st.subheader("Budget progress")

        spent_ratio = (
            min(max(spending / budget, 0), 1)
            if budget > 0 else 0
        )
        st.progress(spent_ratio)
        st.write(f"You have used **{spending / budget:.0%}** of your budget."
                 if budget else "Set a budget to see progress.")

        if remaining < 0:
            st.error("You've exceeded your monthly budget.")
        elif budget > 0 and spending / budget >= 0.8:
            st.warning("You're getting close to your budget limit.")
        else:
            st.success("Your budget is looking manageable.")

        st.subheader("This month's summary")
        st.write(f"Income: ₹{income:,.2f}")
        st.write(f"Expenses: ₹{spending:,.2f}")
        st.write(f"Days remaining this month: {days_left}")

    st.divider()
    st.subheader("Latest transactions")

    if df.empty:
        st.info("No transactions yet. Add your first one in Transactions.")
    else:
        recent = df.head(5).copy()
        recent["txn_date"] = recent["txn_date"].astype(str)

        st.dataframe(
            recent[
                ["txn_date", "txn_type", "category", "amount", "note"]
            ],
            use_container_width=True,
            hide_index=True
        )


# ---------------- TRANSACTIONS ----------------
elif page == "Transactions":
    st.title("Transactions")
    st.write("Record your income and expenses.")

    with st.form("transaction_form", clear_on_submit=True):
        txn_type = st.selectbox(
            "Transaction type", ["Expense", "Income"]
        )

        txn_date = st.date_input(
            "Date", value=today, max_value=today
        )

        amount = st.number_input(
            "Amount (₹)", min_value=1.0,
            value=100.0, step=50.0
        )

        category = st.selectbox("Category", CATEGORIES)

        note = st.text_input(
            "Description",
            placeholder="e.g. Lunch with friends"
        )

        submitted = st.form_submit_button("Save transaction")

        if submitted:
            add_transaction(
                txn_date, txn_type, category, amount, note
            )
            st.success("Transaction saved!")
            st.rerun()

    st.divider()
    st.subheader("Transaction history")

    df = load_transactions()

    if df.empty:
        st.info("No transactions recorded yet.")
    else:
        filter_type = st.selectbox(
            "Show transactions", ["All", "Income", "Expense"]
        )

        shown = (
            df if filter_type == "All"
            else df[df["txn_type"] == filter_type]
        )

        st.dataframe(
            shown, use_container_width=True, hide_index=True
        )

        st.download_button(
            "Download transaction history (CSV)",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="ploutos_transactions.csv",
            mime="text/csv"
        )

        st.divider()
        st.subheader("Delete an incorrect transaction")
        st.caption("Deletion is permanent. Check the ID before proceeding.")

        transaction_ids = shown["id"].astype(int).tolist()

        if transaction_ids:
            selected_id = st.selectbox(
                "Select transaction ID to delete",
                transaction_ids
            )

            confirm_delete = st.checkbox(
                f"I confirm I want to permanently delete transaction #{selected_id}"
            )

            if st.button("Delete selected transaction", type="secondary"):
                if confirm_delete:
                    delete_transaction(selected_id)
                    st.success("Transaction deleted.")
                    st.rerun()
                else:
                    st.warning("Please confirm the deletion first.")


# ---------------- SMART TOOLS ----------------
elif page == "Smart Tools":
    st.title("Smart Money Tools")
    st.caption("Make a plan before you spend.")

    st.subheader("1. Can I afford this?")

    purchase = st.text_input(
        "What do you want to buy?", "New headphones"
    )

    price = st.number_input(
        "Purchase price (₹)", min_value=0.0,
        value=1500.0, step=100.0
    )

    essential = st.checkbox("This is an essential purchase")

    if st.button("Check affordability", type="primary"):
        after_purchase = balance - price

        st.metric(
            "Balance after purchase",
            f"₹{after_purchase:,.2f}"
        )

        if after_purchase < 0:
            st.error(
                f"Buying {purchase} would put your recorded balance below zero."
            )
        elif price > remaining and not essential:
            st.warning(
                "This purchase exceeds your remaining monthly budget."
            )
        elif price > safe_daily * 7 and not essential:
            st.warning(
                "This costs more than a week's safe-to-spend amount. "
                "Consider waiting."
            )
        else:
            st.success(
                "This purchase looks manageable based on your recorded numbers."
            )

    st.divider()
    st.subheader("2. Set your monthly budget")

    st.write(f"Your saved monthly budget is **₹{budget:,.2f}**.")

    with st.form("budget_form"):
        new_budget = st.number_input(
            "New monthly budget (₹)",
            min_value=100.0,
            value=float(budget),
            step=500.0
        )

        update_budget = st.form_submit_button("Save monthly budget")

        if update_budget:
            save_budget(new_budget)
            st.success("Budget saved permanently to your database.")
            st.rerun()

    st.divider()
    st.subheader("3. No-spend challenge")

    challenge_days = st.slider(
        "Challenge duration (days)", 3, 30, 7
    )

    daily_spend = st.number_input(
        "Usual non-essential daily spending (₹)",
        min_value=0.0, value=150.0, step=50.0
    )

    st.metric(
        "Potential savings",
        f"₹{challenge_days * daily_spend:,.0f}"
    )

    st.caption(
        "Estimate assumes you avoid this spending every day during the challenge."
    )


# ---------------- FOOTER ----------------
st.sidebar.divider()
st.sidebar.caption("Built with Python, Streamlit, Pandas & SQLite.")
st.sidebar.caption("Your data is stored locally on this computer.")
