import streamlit as st
from supabase import create_client
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from datetime import date
import pandas as pd

#  Page config
st.set_page_config(
    page_title="Inventory Manager",
    page_icon="📦",
    layout="wide",
)

#  Custom CSS 
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
    background-color: #f5f5f0;
    color: #1a1a1a;
}
h1, h2, h3 { font-family: 'Syne', sans-serif; font-weight: 800; color: #1a1a1a; }
code, .mono { font-family: 'Space Mono', monospace; }

.stApp { background-color: #f5f5f0; }

section[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #ddd;
}

div[data-testid="metric-container"] {
    background-color: #ffffff;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 1rem;
}

.stButton > button {
    background-color: #1a1a1a;
    color: #ffffff;
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    border: none;
    border-radius: 4px;
    padding: 0.5rem 1.5rem;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    background-color: #333333;
    color: #ffffff;
    transform: translateY(-1px);
}

.stTextInput input, .stNumberInput input, .stDateInput input {
    background-color: #ffffff !important;
    color: #1a1a1a !important;
    border: 1px solid #ccc !important;
    border-radius: 4px;
    font-family: 'Space Mono', monospace;
}

.stDataFrame { border: 1px solid #ddd; border-radius: 8px; }

.card {
    background-color: #ffffff;
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.tag {
    display: inline-block;
    background: #c8ff00;
    color: #0f0f0f;
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 3px;
    margin-bottom: 0.5rem;
}
.found-tag { background: #00e5ff; }
.error-tag { background: #ff4444; color: #fff; }
</style>
""", unsafe_allow_html=True)


#  Supabase connection
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = get_supabase()
except Exception:
    st.error("⚠️ Could not connect to Supabase. Make sure SUPABASE_URL and SUPABASE_KEY are set in your secrets.")
    st.stop()


#  Helpers 
def generate_barcode_number():
    """Generate next barcode in FLY0001, FLY0002... sequence."""
    res = supabase.table("inventory").select("barcode_number").execute()
    existing = [r["barcode_number"] for r in res.data if r["barcode_number"].startswith("FLY")]
    if not existing:
        return "FLY0001"
    numbers = [int(b[3:]) for b in existing if b[3:].isdigit()]
    next_num = max(numbers) + 1 if numbers else 1
    return f"FLY{next_num:04d}"

def make_barcode_image(barcode_number: str) -> BytesIO:
    """Render a Code128 barcode to a PNG in memory."""
    code128 = barcode.get_barcode_class("code128")
    buf = BytesIO()
    code128(barcode_number, writer=ImageWriter()).write(buf)
    buf.seek(0)
    return buf

def lookup_item(barcode_number: str):
    res = supabase.table("inventory").select("*").eq("barcode_number", barcode_number).execute()
    return res.data[0] if res.data else None

def add_item(barcode_number, name, date_bought, buy_price):
    profit = None  # not sold yet
    supabase.table("inventory").insert({
        "barcode_number": barcode_number,
        "name": name,
        "date_bought": str(date_bought),
        "date_sold": None,
        "buy_price": float(buy_price),
        "sell_price": None,
        "profit": None,
    }).execute()

def update_sale(barcode_number, date_sold, sell_price, buy_price):
    profit = round(float(sell_price) - float(buy_price), 2)
    supabase.table("inventory").update({
        "date_sold": str(date_sold),
        "sell_price": float(sell_price),
        "profit": profit,
    }).eq("barcode_number", barcode_number).execute()

def get_all_items():
    res = supabase.table("inventory").select("*").order("id", desc=True).execute()
    return res.data


#  Sidebar nav 
st.sidebar.markdown("# 📦 Inventory\n### Manager")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    ["🔍 Check / Add Item", "💰 Record Sale", "📊 Dashboard"],
    label_visibility="collapsed",
)
st.sidebar.markdown("---")
st.sidebar.caption("Powered by Supabase + Streamlit")


# PAGE 1 – Check / Add Item

if page == "🔍 Check / Add Item":
    st.markdown("## 🔍 Check or Add an Item")

    col1, col2 = st.columns([2, 1])
    with col1:
        barcode_input = st.text_input(
            "Scan or enter barcode number",
            placeholder="e.g. 123456789012",
            help="Leave blank to auto-generate a new barcode",
        )

    with col2:
        auto_gen = st.checkbox("Auto-generate barcode", value=True)

    if auto_gen:
        barcode_input = generate_barcode_number()
        st.info(f"🎲 Auto-generated barcode: `{barcode_input}`")

    if barcode_input:
        existing = lookup_item(barcode_input)

        if existing:
            #  Item already exists
            st.markdown(f'<span class="tag found-tag">✅ FOUND IN DATABASE</span>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)

            # Full item name on its own line so it never gets truncated
            st.markdown(f"### {existing['name']}")
            st.markdown(f"`Barcode: {existing['barcode_number']}`")
            st.markdown("---")

            c1, c2, c3 = st.columns(3)
            c1.metric("Date Bought", existing["date_bought"] or "—")
            c2.metric("Date Sold", existing["date_sold"] or "Not sold")
            c3.metric("Buy Price", f"${existing['buy_price']:.2f}")
            c1.metric(
                "Sell Price",
                f"${existing['sell_price']:.2f}" if existing["sell_price"] is not None else "Not sold yet",
            )
            c2.metric(
                "Profit",
                f"${existing['profit']:.2f}" if existing["profit"] is not None else "Pending",
            )
            st.markdown("</div>", unsafe_allow_html=True)

        else:
            #  New item form 
            st.markdown(f'<span class="tag">➕ NEW ITEM — NOT IN DATABASE</span>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            with st.form("add_item_form"):
                name = st.text_input("Item name *", placeholder="e.g. Vintage Camera")
                date_bought = st.date_input("Date bought *", value=date.today())
                buy_price = st.number_input("Buy price ($) *", min_value=0.0, step=0.01, format="%.2f")
                submitted = st.form_submit_button("💾 Save & Generate Barcode")

            if submitted:
                if not name:
                    st.error("Item name is required.")
                else:
                    add_item(barcode_input, name, date_bought, buy_price)
                    st.success(f"✅ **{name}** added to inventory!")

                    # Show printable barcode
                    buf = make_barcode_image(barcode_input)
                    st.markdown("### 🖨️ Printable Barcode")
                    st.image(buf, caption=f"Barcode: {barcode_input}", use_container_width=False)
                    st.download_button(
                        "⬇️ Download Barcode PNG",
                        data=make_barcode_image(barcode_input),
                        file_name=f"barcode_{barcode_input}.png",
                        mime="image/png",
                    )
                    st.caption("💡 Tip: Open the downloaded PNG and use **Ctrl+P / Cmd+P** to print directly to your connected printer.")

            st.markdown("</div>", unsafe_allow_html=True)


# PAGE 2 – Record a Sale

elif page == "💰 Record Sale":
    st.markdown("## 💰 Record a Sale")

    barcode_sale = st.text_input("Scan or enter barcode number", placeholder="e.g. 123456789012")

    if barcode_sale:
        item = lookup_item(barcode_sale)
        if not item:
            st.markdown('<span class="tag error-tag">❌ ITEM NOT FOUND</span>', unsafe_allow_html=True)
            st.warning("This barcode doesn't exist in the database. Add it first on the Check / Add page.")
        elif item["date_sold"]:
            st.markdown('<span class="tag found-tag">ℹ️ ALREADY SOLD</span>', unsafe_allow_html=True)
            st.info(f"**{item['name']}** was sold on {item['date_sold']} for ${item['sell_price']:.2f}. Profit: ${item['profit']:.2f}")
        else:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f"**Item:** {item['name']}  |  **Barcode:** `{item['barcode_number']}`  |  **Bought for:** ${item['buy_price']:.2f}")
            with st.form("sale_form"):
                date_sold = st.date_input("Date sold *", value=date.today())
                sell_price = st.number_input("Sell price ($) *", min_value=0.0, step=0.01, format="%.2f")
                submitted = st.form_submit_button("✅ Record Sale")

            if submitted:
                update_sale(barcode_sale, date_sold, sell_price, item["buy_price"])
                profit = round(sell_price - item["buy_price"], 2)
                st.success(f"Sale recorded! Profit: **${profit:.2f}**")
                if profit < 0:
                    st.warning("⚠️ This sale resulted in a loss.")

            st.markdown("</div>", unsafe_allow_html=True)


# PAGE 3 – Dashboard

elif page == "📊 Dashboard":
    st.markdown("## 📊 Inventory Dashboard")

    items = get_all_items()
    if not items:
        st.info("No items in inventory yet. Start by adding one!")
        st.stop()

    df = pd.DataFrame(items)

    sold = df[df["date_sold"].notna()]
    unsold = df[df["date_sold"].isna()]

    #  KPI row 
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Items", len(df))
    k2.metric("Sold", len(sold))
    k3.metric("In Stock", len(unsold))
    total_profit = sold["profit"].sum() if not sold.empty else 0
    k4.metric("Total Profit", f"${total_profit:,.2f}")

    #  Profit/Loss by period 
    if not sold.empty:
        sold["date_sold"] = pd.to_datetime(sold["date_sold"])
        today = pd.Timestamp.today().normalize()

        daily  = sold[sold["date_sold"] == today]["profit"].sum()
        weekly = sold[sold["date_sold"] >= today - pd.Timedelta(weeks=1)]["profit"].sum()
        monthly= sold[sold["date_sold"] >= today - pd.Timedelta(days=30)]["profit"].sum()
        yearly = sold[sold["date_sold"] >= today - pd.Timedelta(days=365)]["profit"].sum()

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Today's P/L",  f"${daily:,.2f}")
        p2.metric("Weekly P/L",   f"${weekly:,.2f}")
        p3.metric("Monthly P/L",  f"${monthly:,.2f}")
        p4.metric("Yearly P/L",   f"${yearly:,.2f}")

    st.markdown("---")

    #  Filter 
    filter_opt = st.selectbox("Filter", ["All Items", "In Stock", "Sold"])
    if filter_opt == "In Stock":
        view_df = unsold
    elif filter_opt == "Sold":
        view_df = sold
    else:
        view_df = df

    s1, s2 = st.columns(2)
    search_name = s1.text_input("🔍 Search by name", placeholder="e.g. Vintage Camera")
    search_barcode = s2.text_input("🔍 Search by barcode", placeholder="e.g. 123456789012")

    if search_name:
        view_df = view_df[view_df["name"].str.contains(search_name, case=False, na=False)]
    if search_barcode:
        view_df = view_df[view_df["barcode_number"].str.contains(search_barcode, case=False, na=False)]

    display_cols = ["barcode_number", "name", "date_bought", "buy_price", "date_sold", "sell_price", "profit"]
    rename_map = {
        "barcode_number": "Barcode",
        "name": "Item",
        "date_bought": "Bought On",
        "buy_price": "Buy ($)",
        "date_sold": "Sold On",
        "sell_price": "Sell ($)",
        "profit": "Profit ($)",
    }
    edited_df = st.data_editor(
        view_df[display_cols].rename(columns=rename_map),
        use_container_width=True,
        hide_index=True,
        disabled=["Barcode"],
    )

    if st.button("💾 Save Changes"):
        for _, row in edited_df.iterrows():
            buy = row["Buy ($)"] or 0
            sell = row["Sell ($)"]
            profit = round(float(sell) - float(buy), 2) if pd.notna(sell) and sell else None

            def fmt_date(d):
                if pd.isna(d) or d == "" or d is None:
                    return None
                return pd.Timestamp(d).strftime("%Y-%m-%d")

            supabase.table("inventory").update({
                "name": row["Item"] if pd.notna(row["Item"]) and row["Item"] != "" else "Unknown",
                "date_bought": fmt_date(row["Bought On"]),
                "date_sold": fmt_date(row["Sold On"]),
                "buy_price": float(row["Buy ($)"]) if pd.notna(row["Buy ($)"]) else 0.0,
                "sell_price": float(sell) if pd.notna(sell) and sell else None,
                "profit": profit,
            }).eq("barcode_number", row["Barcode"]).execute()
        st.success("✅ Changes saved!")
        st.rerun()

    #  Download CSV
    csv = view_df[display_cols].rename(columns=rename_map).to_csv(index=False)
    st.download_button("⬇️ Export CSV", data=csv, file_name="inventory.csv", mime="text/csv")
