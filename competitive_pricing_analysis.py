import os
import sys
import subprocess
import streamlit as st

# --- STRICT EMAIL AUTHENTICATION GATE ---
try:
    ALLOWED_EMAILS = [e.strip().lower() for e in st.secrets["auth"]["allowed_emails"]]
    APP_PASSCODE = str(st.secrets["auth"]["passcode"])
except Exception as e:
    st.error("🔒 Security Config Missing: Please configure [auth] in Streamlit Cloud Secrets.")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Restricted Pricing Dashboard")
    st.caption("Save A Life / NHCPS Internal Tool")
    st.write("Please sign in with an authorized email and passcode to view dashboard metrics.")
    
    user_email = st.text_input("Email Address")
    user_passcode = st.text_input("Passcode", type="password")
    
    if st.button("Sign In"):
        if user_email.strip().lower() in ALLOWED_EMAILS and user_passcode == APP_PASSCODE:
            st.session_state.authenticated = True
            st.success("Access granted!")
            st.rerun()
        else:
            st.error("Access denied. Unauthorized email address or incorrect passcode.")
            
    st.stop()

st.sidebar.button("Log Out", on_click=lambda: st.session_state.update(authenticated=False))

import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 1. DIRECTORY & GOOGLE SHEETS CONFIGURATION
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APPEND_SCRIPT = os.path.join(BASE_DIR, "append_month.py")
PRICING_SCRIPT = os.path.join(BASE_DIR, "pricing.py")

SPREADSHEET_ID = "1V2pnwBe4qJj65BBrEc-PQP07SNczMmqI9oNeeGtwedM"
CREDS_FILE = os.path.join(BASE_DIR, dict(st.secrets["gcp_service_account"]))
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ==========================================
# 2. STREAMLIT PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Competitive Pricing Analysis", 
    page_icon="📊", 
    layout="wide"
)

st.title("📊 Competitive Pricing Analysis Center")

# Create Main Tabs
tab_control, tab_analytics = st.tabs(["⚡ Automation Controls", "📈 Price Comparison Analytics"])

# ==========================================
# TAB 1: AUTOMATION CONTROLS
# ==========================================
with tab_control:
    st.write("Manage monthly layout rollovers and live price web scraping directly from your browser.")
    st.divider()

    col1, col2 = st.columns(2)

    # --- 1. MONTHLY LAYOUT ROLLOVER ---
    with col1:
        st.subheader("1. Monthly Layout Rollover")
        st.caption("Generates new monthly placeholder rows in Google Sheets.")
        
        source_month = st.text_input("Source Month (Copy baseline from):", value="May 2026")
        new_month = st.text_input("New Month (To create):", value="June 2026")
        
        if st.button("🚀 Run Layout Append", use_container_width=True):
            if not source_month or not new_month:
                st.error("Please provide both Source Month and New Month.")
            elif not os.path.exists(APPEND_SCRIPT):
                st.error(f"File not found: `append_month.py` inside `{BASE_DIR}`")
            else:
                with st.spinner(f"Appending '{new_month}' based on '{source_month}'..."):
                    try:
                        env = os.environ.copy()
                        env["SOURCE_MONTH"] = source_month
                        env["NEW_MONTH"] = new_month
                        
                        result = subprocess.run(
                            [sys.executable, APPEND_SCRIPT, source_month, new_month], 
                            capture_output=True, text=True, check=True, env=env, cwd=BASE_DIR
                        )
                        st.success(f"Successfully generated rows for {new_month}!")
                        with st.expander("View Output Logs"):
                            st.code(result.stdout)
                    except subprocess.CalledProcessError as e:
                        st.error("Error executing append_month.py")
                        st.code(e.stderr if e.stderr else e.stdout)

    # --- 2. LIVE PRICE SCRAPER ---
    with col2:
        st.subheader("2. Live Price Scraper")
        st.caption("Crawls competitor pages and populates live prices into Google Sheets.")
        
        target_month = st.text_input("Target Month to Scrape & Update:", value="June 2026")
        
        if st.button("🔍 Run Live Scraper", use_container_width=True):
            if not target_month:
                st.error("Please enter a Target Month.")
            elif not os.path.exists(PRICING_SCRIPT):
                st.error(f"File not found: `pricing.py` inside `{BASE_DIR}`")
            else:
                with st.status(f"Scraper running for {target_month}...", expanded=True) as status:
                    try:
                        env = os.environ.copy()
                        env["TARGET_MONTH_OVERRIDE"] = target_month
                        
                        process = subprocess.Popen(
                            [sys.executable, "-u", PRICING_SCRIPT, target_month], 
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, cwd=BASE_DIR
                        )
                        
                        log_container = st.empty()
                        logs = ""
                        
                        for line in iter(process.stdout.readline, ''):
                            logs += line
                            log_container.code(logs[-2000:])
                            
                        process.stdout.close()
                        process.wait()
                        
                        if process.returncode == 0:
                            status.update(label=f"Scraping complete for {target_month}!", state="complete")
                            st.balloons()
                        else:
                            status.update(label="Scraper encountered an error during execution.", state="error")
                    except Exception as e:
                        st.error(f"Execution failed: {str(e)}")


# ==========================================
# TAB 2: PRICE COMPARISON ANALYTICS
# ==========================================
with tab_analytics:
    st.subheader("🔍 Historical Price Movement & Multi-Month Comparison")
    st.caption("Analyze month-over-month price fluctuations directly from your Google Sheet data.")
    
    col_workspace, col_btn = st.columns([3, 1])
    
    with col_workspace:
        selected_tab = st.selectbox(
            "Select Worksheet Tab to Analyze:", 
            ["Master Pricing", "Master Amazon", "Master - Bundles & For Life", "Master Handbooks"]
        )
        
    with col_btn:
        st.write(" ")
        st.write(" ")
        refresh_data = st.button("🔄 Fetch / Refresh Sheet Data", use_container_width=True)

    if refresh_data or "sheet_df" not in st.session_state:
        if not os.path.exists(CREDS_FILE):
            st.error(f"Credentials JSON not found at `{CREDS_FILE}`")
        else:
            with st.spinner(f"Loading '{selected_tab}' from Google Sheets..."):
                try:
                    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
                    client = gspread.authorize(creds)
                    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(selected_tab)
                    
                    data = sheet.get_all_values()
                    if data:
                        headers = data[0]
                        df = pd.DataFrame(data[1:], columns=headers)
                        st.session_state["sheet_df"] = df
                        st.session_state["loaded_tab"] = selected_tab
                        st.success(f"Data updated from '{selected_tab}'!")
                except Exception as e:
                    st.error(f"Failed to load sheet data: {str(e)}")

    if "sheet_df" in st.session_state and st.session_state.get("loaded_tab") == selected_tab:
        df = st.session_state["sheet_df"].copy()
        
        # Identify available months in Column 0
        month_col = df.columns[0]
        course_col = df.columns[1]
        available_months = list(df[month_col].str.strip().unique())
        available_months = [m for m in available_months if m]
        
        if len(available_months) < 2:
            st.warning("Need at least 2 distinct months of data in this worksheet to perform comparison.")
        else:
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                baseline_month = st.selectbox("Baseline Month (Previous):", available_months, index=0)
            with m_col2:
                comparison_month = st.selectbox("Comparison Month (New):", available_months, index=min(1, len(available_months)-1))

            competitor_cols = [c for c in df.columns[2:] if c.strip()]
            
            # Slice Data for comparison
            df_base = df[df[month_col].str.strip().str.lower() == baseline_month.lower()][[course_col] + competitor_cols]
            df_comp = df[df[month_col].str.strip().str.lower() == comparison_month.lower()][[course_col] + competitor_cols]
            
            comparison_rows = []

            for course in df_base[course_col].unique():
                if not str(course).strip(): continue
                
                row_base = df_base[df_base[course_col] == course]
                row_comp = df_comp[df_comp[course_col] == course]
                
                if row_base.empty or row_comp.empty: continue
                
                for comp in competitor_cols:
                    if comp not in row_base.columns or comp not in row_comp.columns:
                        continue

                    # Safely extract scalar array elements without evaluating truth value of Series
                    base_vals = row_base[comp].values.ravel()
                    comp_vals = row_comp[comp].values.ravel()

                    raw_base_val = base_vals[0] if len(base_vals) > 0 else ""
                    raw_comp_val = comp_vals[0] if len(comp_vals) > 0 else ""

                    s_base = str(raw_base_val).replace("$", "").strip() if pd.notna(raw_base_val) else ""
                    s_comp = str(raw_comp_val).replace("$", "").strip() if pd.notna(raw_comp_val) else ""

                    try:
                        p_base = float(s_base) if s_base and s_base.lower() not in ["nan", "none", ""] else None
                        p_comp = float(s_comp) if s_comp and s_comp.lower() not in ["nan", "none", ""] else None
                        
                        if p_base is not None and p_comp is not None:
                            diff = p_comp - p_base
                            if diff < -0.001:
                                status = "🟢 Price Cut"
                            elif diff > 0.001:
                                status = "🔴 Price Hike"
                            else:
                                status = "⚪ Unchanged"
                                
                            comparison_rows.append({
                                "Course / Product": course,
                                "Competitor": comp,
                                f"{baseline_month} Price": f"${p_base:.2f}",
                                f"{comparison_month} Price": f"${p_comp:.2f}",
                                "Change ($)": f"${diff:+.2f}",
                                "Status": status
                            })
                    except ValueError:
                        continue

            st.divider()
            
            if comparison_rows:
                res_df = pd.DataFrame(comparison_rows)
                
                # --- DEDUPLICATION STEP ---
                res_df = res_df.drop_duplicates(subset=["Course / Product", "Competitor"], keep="first")
                
                # Recalculate metrics based on deduplicated data
                price_drops = int((res_df["Status"] == "🟢 Price Cut").sum())
                price_hikes = int((res_df["Status"] == "🔴 Price Hike").sum())
                unchanged = int((res_df["Status"] == "⚪ Unchanged").sum())

                # Summary Metrics
                met1, met2, met3 = st.columns(3)
                met1.metric("🟢 Price Cuts Detected", price_drops)
                met2.metric("🔴 Price Hikes Detected", price_hikes)
                met3.metric("⚪ Unchanged Listings", unchanged)
                
                st.divider()

                # Filter Controls
                filter_status = st.multiselect(
                    "Filter by Price Movement:", 
                    ["🟢 Price Cut", "🔴 Price Hike", "⚪ Unchanged"],
                    default=["🟢 Price Cut", "🔴 Price Hike", "⚪ Unchanged"]
                )
                
                filtered_df = res_df[res_df["Status"].isin(filter_status)]
                
                st.dataframe(
                    filtered_df, 
                    use_container_width=True, 
                    hide_index=True,
                    height=450
                )
            else:
                st.info("No matching numeric price data found to compare between these two selected months.")