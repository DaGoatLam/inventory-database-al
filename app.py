from datetime import datetime
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# 1. Page Config
st.set_page_config(page_title="Supply Manager (Sheets)", layout="wide")

# 2. Inject Custom CSS to expand layout width and reduce margins
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            max-width: 96% !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)


# --- PASSWORD PROTECTION ---
def check_password():
    """Returns True if the user entered the correct password."""

    def password_entered():
        if st.session_state["password_input"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input(
            "Please enter the password to access the Inventory:",
            type="password",
            on_change=password_entered,
            key="password_input",
        )
        return False
    elif not st.session_state["password_correct"]:
        st.text_input(
            "Please enter the password to access the Inventory:",
            type="password",
            on_change=password_entered,
            key="password_input",
        )
        st.error("😕 Password incorrect. Please try again.")
        return False
    else:
        return True


if not check_password():
    st.stop()

# --- SHEET CONNECTION & CACHING ---
conn = st.connection("gsheets", type=GSheetsConnection)

if "inventory_df" not in st.session_state:
    with st.spinner("Connecting to Google Sheets..."):
        raw_df = conn.read(ttl="1h")

        expected_cols = ["ID", "Item Name", "Quantity", "Location", "Expiration Date"]
        if raw_df.empty or len(raw_df.columns) == 0:
            raw_df = pd.DataFrame(columns=expected_cols)
        else:
            raw_df.columns = [str(c).strip() for c in raw_df.columns]

        # Convert numerical columns to integers
        raw_df["ID"] = pd.to_numeric(raw_df["ID"], errors="coerce").fillna(0).astype(int)
        raw_df["Quantity"] = (
            pd.to_numeric(raw_df["Quantity"], errors="coerce").fillna(0).astype(int)
        )

        st.session_state["inventory_df"] = raw_df

df = st.session_state["inventory_df"]

st.title("📦 Supply & Inventory Manager")

# --- SIDEBAR: ADD SUPPLY FORM ---
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
                        "ID": int(new_id),
                        "Item Name": name,
                        "Quantity": int(qty),
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

# --- METRIC CARDS SECTION ---
today = datetime.now().date()
total_items = len(df)
expired_count = 0
low_stock_count = 0

if not df.empty:
    for idx, row in df.iterrows():
        # Count expired items
        exp_str = str(row["Expiration Date"]).strip()
        if exp_str and exp_str != "nan" and exp_str != "":
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                if (exp_date - today).days < 0:
                    expired_count += 1
            except ValueError:
                pass
        # Count low stock items (quantity of 5 or fewer)
        try:
            if int(row["Quantity"]) <= 5:
                low_stock_count += 1
        except ValueError:
            pass

m_col1, m_col2, m_col3 = st.columns(3)
m_col1.metric("Total Unique Supplies", f"{total_items} items")
m_col2.metric("Expired Supplies 🚨", f"{expired_count} items")
m_col3.metric("Low Stock Items ⚠️", f"{low_stock_count} items")

st.markdown("---")

# --- CURRENT INVENTORY SECTION ---
st.subheader("Current Inventory")

if not df.empty:
    # Search & Location Filters
    f_col1, f_col2 = st.columns([2, 1])
    with f_col1:
        search_query = st.text_input("🔍 Search by Item Name:", value="")
    with f_col2:
        locations = ["All"] + sorted(list(df["Location"].dropna().unique()))
        selected_location = st.selectbox("📍 Filter by Location:", options=locations)

    # Apply filtering
    filtered_df = df.copy()
    if search_query:
        filtered_df = filtered_df[
            filtered_df["Item Name"].str.contains(search_query, case=False, na=False)
        ]
    if selected_location != "All":
        filtered_df = filtered_df[filtered_df["Location"] == selected_location]

    # Dynamic Expiration and Low Stock Highlighting
    def highlight_row(row):
        exp_str = str(row["Expiration Date"]).strip()
        qty = int(row["Quantity"])

        days_left = None
        if exp_str and exp_str != "nan" and exp_str != "":
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                days_left = (exp_date - today).days
            except ValueError:
                pass

        # Priority 1: Expired (Red Alert)
        if days_left is not None and days_left < 0:
            return [
                "background-color: #f8d7da; color: #721c24; font-weight: bold;"
            ] * len(row)
        # Priority 2: Expiring soon (Yellow warning)
        elif days_left is not None and days_left <= 30:
            return [
                "background-color: #fff3cd; color: #856404; font-weight: bold;"
            ] * len(row)
        # Priority 3: Low stock (Light Blue warning)
        elif qty <= 5:
            return [
                "background-color: #d1ecf1; color: #0c5460; font-weight: bold;"
            ] * len(row)

        return [""] * len(row)

    # Format numbers to hide decimals
    styled_df = filtered_df.style.format(
        {"ID": "{:.0f}", "Quantity": "{:.0f}"}
    ).apply(highlight_row, axis=1)

    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # Download Button
    csv_data = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Export Current Filtered List to CSV",
        data=csv_data,
        file_name=f"inventory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.markdown("---")

    # --- MANAGE INVENTORY (QUICK ADJUST & DELETE) ---
    st.subheader("Manage Inventory")
    action_col1, action_col2 = st.columns(2)

    with action_col1:
        st.markdown("##### ✏️ Quick Quantity Adjuster")
        adjust_id = st.selectbox(
            "Select an Item to Adjust Qty",
            df["ID"].tolist(),
            format_func=lambda x: f"ID {int(x)} - {df[df['ID'] == x]['Item Name'].values[0] if not df[df['ID'] == x].empty else ''}",
            key="adjust_select",
        )

        adj_btn_col1, adj_btn_col2 = st.columns(2)
        with adj_btn_col1:
            if st.button("➕ Add 1", use_container_width=True):
                # Update stock in memory
                df.loc[df["ID"] == adjust_id, "Quantity"] += 1
                # Save to Google Sheets
                conn.update(data=df)
                st.session_state["inventory_df"] = df
                st.cache_data.clear()
                st.success("Quantity increased!")
                st.rerun()

        with adj_btn_col2:
            if st.button("➖ Subtract 1", use_container_width=True):
                current_qty = df.loc[df["ID"] == adjust_id, "Quantity"].values[0]
                if current_qty > 0:
                    df.loc[df["ID"] == adjust_id, "Quantity"] -= 1
                    conn.update(data=df)
                    st.session_state["inventory_df"] = df
                    st.cache_data.clear()
                    st.success("Quantity decreased!")
                    st.rerun()
                else:
                    st.warning("Quantity is already at 0!")

    with action_col2:
        st.markdown("##### 🗑️ Delete Supply Record")
        delete_id = st.selectbox(
            "Select an Item to Permanently Delete",
            df["ID"].tolist(),
            format_func=lambda x: f"ID {int(x)} - {df[df['ID'] == x]['Item Name'].values[0] if not df[df['ID'] == x].empty else ''}",
            key="delete_select",
        )
        if st.button("Delete Selected Record", type="primary", use_container_width=True):
            updated_df = df[df["ID"] != delete_id]
            conn.update(data=updated_df)
            st.session_state["inventory_df"] = updated_df
            st.cache_data.clear()
            st.success(f"Deleted Item ID {delete_id}!")
            st.rerun()

else:
    st.info("No items in inventory yet. Use the sidebar to add some!")
