from datetime import datetime
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection


# --- PASSWORD PROTECTION FUNCTION ---
def check_password():
    """Returns True if the user entered the correct password."""

    def password_entered():
        """Checks whether the entered password is correct."""
        if st.session_state["password_input"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]  # Clean up memory
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Show input field if first-time load
        st.text_input(
            "Please enter the password to access the Inventory:",
            type="password",
            on_change=password_entered,
            key="password_input",
        )
        return False
    elif not st.session_state["password_correct"]:
        # Show input field + error if password was wrong
        st.text_input(
            "Please enter the password to access the Inventory:",
            type="password",
            on_change=password_entered,
            key="password_input",
        )
        st.error("😕 Password incorrect. Please try again.")
        return False
    else:
        # Password was correct, proceed to app
        return True


# Run the password check. If it fails, stop execution here.
if not check_password():
    st.stop()

# --- IF PASSWORD IS CORRECT, RENDER THE REST OF THE APP ---

# Establish connection to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Load data into local memory
if "inventory_df" not in st.session_state:
    with st.spinner("Connecting to Google Sheets..."):
        raw_df = conn.read(ttl="1h")

        expected_cols = ["ID", "Item Name", "Quantity", "Location", "Expiration Date"]
        if raw_df.empty or len(raw_df.columns) == 0:
            raw_df = pd.DataFrame(columns=expected_cols)
        else:
            raw_df.columns = [str(c).strip() for c in raw_df.columns]

        st.session_state["inventory_df"] = raw_df

df = st.session_state["inventory_df"]

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

            new_id = (
                int(df["ID"].max() + 1)
                if not df.empty and pd.notna(df["ID"].max())
                else 1
            )

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

            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(data=updated_df)
            st.session_state["inventory_df"] = updated_df
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
        if exp_str and exp_str != "nan" and exp_str != "":
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                days_left = (exp_date - today).days
                if days_left < 0:
                    return ["background-color: #ffcccc"] * len(row)
                elif days_left <= 30:
                    return ["background-color: #ffe0b2"] * len(row)
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
        updated_df = df[df["ID"] != delete_id]
        conn.update(data=updated_df)
        st.session_state["inventory_df"] = updated_df
        st.cache_data.clear()

        st.success(f"Deleted Item ID {delete_id}!")
        st.rerun()
else:
    st.info("No items in inventory yet. Use the sidebar to add some!")
