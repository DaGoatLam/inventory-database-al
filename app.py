from datetime import datetime
import sqlite3
import pandas as pd
import streamlit as st

# Configure the web page
st.set_page_config(page_title="Supply Manager", layout="wide")


# Initialize the database
def init_db():
    conn = sqlite3.connect("inventory.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            location TEXT,
            expiration_date TEXT
        )
    """)
    conn.commit()
    return conn


conn = init_db()


def add_item(name, qty, location, exp_date):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO inventory (name, quantity, location, expiration_date)
        VALUES (?, ?, ?, ?)
    """,
        (name, qty, location, exp_date),
    )
    conn.commit()


def delete_item(item_id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    conn.commit()


def get_items():
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, quantity, location, expiration_date FROM inventory"
    )
    return cursor.fetchall()


# --- WEB INTERFACE ---
st.title("📦 Supply & Inventory Manager")

# Sidebar for entering new items
st.sidebar.header("Add New Supply")
with st.sidebar.form("add_form", clear_on_submit=True):
    name = st.text_input("Item Name")
    qty = st.number_input("Quantity", min_value=1, step=1)
    location = st.text_input("Location")
    exp_date = st.date_input("Expiration Date", value=None)

    submit = st.form_submit_button("Add Item")
    if submit:
        if name:
            # Format the date if provided
            exp_date_str = exp_date.strftime("%Y-%m-%d") if exp_date else ""
            add_item(name, qty, location, exp_date_str)
            st.sidebar.success(f"Added {name} successfully!")
        else:
            st.sidebar.error("Item Name is required.")

# Main page layout
st.subheader("Current Inventory")
items = get_items()

if items:
    # Load items into a pandas table for clean web presentation
    df = pd.DataFrame(
        items,
        columns=["ID", "Item Name", "Quantity", "Location", "Expiration Date"],
    )

    # Highlight expired or expiring soon
    today = datetime.now().date()

    def highlight_row(row):
        exp_str = row["Expiration Date"]
        if exp_str:
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                days_left = (exp_date - today).days
                if days_left < 0:
                    # Expired -> Light Red
                    return ["background-color: #ffcccc"] * len(row)
                elif days_left <= 30:
                    # Expiring Soon -> Light Yellow
                    return ["background-color: #ffe0b2"] * len(row)
            except ValueError:
                pass
        return [""] * len(row)

    styled_df = df.style.apply(highlight_row, axis=1)

    # Render table on web page
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # Deletion Section
    st.subheader("Manage Inventory")
    delete_id = st.selectbox(
        "Select an Item ID to Delete",
        df["ID"].tolist(),
        format_func=lambda x: f"ID {x}",
    )
    if st.button("Delete Selected", type="primary"):
        delete_item(delete_id)
        st.success(f"Deleted Item ID {delete_id}!")
        st.rerun()
else:
    st.info("No items in inventory yet. Use the sidebar to add some!")