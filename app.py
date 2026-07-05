
from datetime import datetime
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Supply Manager (Sheets)", layout="wide")

# Establish connection to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)


# Read data from the Google Sheet
def get_data():
    return conn.read(ttl="10m")  # Keeps cache for 10 minutes unless cleared


df = get_data()

# Ensure standard columns are present
expected_cols = ["ID", "Item Name", "Quantity", "Location", "Expiration Date"]
if df.empty or len(df.columns) == 0:
    df = pd.DataFrame(columns=expected_cols)
else:
    # Clean up column names to avoid trailing spaces
    df.columns = [str(c).strip() for c in df.columns]

st.title("📦 Supply & Inventory Manager (Google Sheets)")

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
            exp_date_str = exp_date.strftime("%Y-%m-%d") if exp_date else ""

            # Generate a new unique numerical ID
            new_id = (
                int(df["ID"].max() + 1)
                if not df.empty and pd.notna(df["ID"].max())
                else 1
            )

            # Create new row DataFrame
            new_row = pd.DataFrame(
                [
                    {
                        "ID": new_id,
                        "Item Name": name,
                        "Quantity": qty,
                        "Location": location,
                        "Expiration Date": exp_date_str,
                    }
                ]
            )

            # Append the new row to existing DataFrame
            updated_df = pd.concat([df, new_row], ignore_index=True)

            # Write the updated DataFrame back to Google Sheets
            conn.update(data=updated_df)

            # --- THE FIX: Clear Streamlit's cache to force a fresh reload ---
            st.cache_data.clear()

            st.sidebar.success(f"Added {name} successfully!")
            st.rerun()
        else:
            st.sidebar.error("Item Name is required.")

# Main page: Display Inventory
st.subheader("Current Inventory")

if not df.empty:
    today = datetime.now().date()

    def highlight_row(row):
        exp_str = str(row["Expiration Date"]).strip()
        # Skip empty rows or null values
        if exp_str and exp_str != "nan" and exp_str != "":
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                days_left = (exp_date - today).days
                if days_left < 0:
                    return ["background-color: #ffcccc"] * len(row)  # Red
                elif days_left <= 30:
                    return ["background-color: #ffe0b2"] * len(row)  # Yellow
            except ValueError:
                pass
        return [""] * len(row)

    styled_df = df.style.apply(highlight_row, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # Deletion Section
    st.subheader("Manage Inventory")
    delete_id = st.selectbox(
        "Select an Item ID to Delete",
        df["ID"].tolist(),
        format_func=lambda x: f"ID {x}",
    )
    if st.button("Delete Selected", type="primary"):
        # Filter out the deleted row
        updated_df = df[df["ID"] != delete_id]

        # Write the updated DataFrame back to Google Sheets
        conn.update(data=updated_df)

        # --- THE FIX: Clear Streamlit's cache to force a fresh reload ---
        st.cache_data.clear()

        st.success(f"Deleted Item ID {delete_id}!")
        st.rerun()
else:
    st.info("No items in inventory yet. Use the sidebar to add some!")
