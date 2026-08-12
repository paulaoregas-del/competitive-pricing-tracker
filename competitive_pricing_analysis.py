import os
import sys
import json
import tempfile
import subprocess
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st

# ==========================================
# 1. STREAMLIT PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Competitive Pricing Analysis", 
    page_icon="📊", 
    layout="wide"
)

# ==========================================
# 2. CREDENTIALS & DIRECTORY SETUP
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMP_CREDS_FILE = os.path.join(tempfile.gettempdir(), "gcp_service_account.json")

try:
    if "gcp_service_account" in st.secrets:
        with open(TEMP_CREDS_FILE, "w") as _f:
            json.dump(dict(st.secrets["gcp_service_account"]), _f)
except Exception as e:
    st.error(f"Error initializing GCP Secrets: {e}")

LOCAL_CREDS_FILE = os.path.join(BASE_DIR, "pricing-tracker-499202-a9f7e625814b.json")
CREDS_FILE = TEMP_CREDS_FILE if os.path.exists(TEMP_CREDS_FILE) else LOCAL_CREDS_FILE

# ==========================================
# 3. STRICT EMAIL AUTHENTICATION GATE
# ==========================================
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

# ==========================================
# 4. SPREADSHEET & SCRIPT CONFIGURATION
# ==========================================
APPEND_SCRIPT = os.path.join(BASE_DIR, "append_month.py")
PRICING_SCRIPT = os.path.join(BASE_DIR, "pricing.py")
SYNC_SCRIPT = os.path.join(BASE_DIR, "sync_course_tabs.py")
AI_FORMULA_SCRIPT = os.path.join(BASE_DIR, "run_ai_formula.py")

SPREADSHEET_ID = "1V2pnwBe4qJj65BBrEc-PQP07SNczMmqI9oNeeGtwedM"
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

COURSE_WORKSHEETS = [
    "Pricing - ACLS Certification", 
    "Pricing - ACLS Recertification",
    "Pricing - PALS Certification", 
    "Pricing - PALS Recertification",
    "Pricing - BLS Certification", 
    "Pricing - BLS Recertification",
    "Pricing - CPR, AED & First Aid Certification", 
    "Pricing - CPR, AED & First Aid Recertification",
    "Pricing - Bloodborne Pathogens", 
    "Pricing - NRP Certification", 
    "Pricing - NRP Recertification",
    "Pricing - Bundles & For Life"
]

def deduplicate_columns(df):
    """Ensure all column headers are unique to prevent PyArrow st.dataframe errors."""
    cols = []
    counts = {}
    for col in df.columns:
        c_str = str(col).strip() if str(col).strip() else "Unnamed"
        if c_str in counts:
            counts[c_str] += 1
            cols.append(f"{c_str}_{counts[c_str]}")
        else:
            counts[c_str] = 0
            cols.append(c_str)
    df.columns = cols
    return df

@st.cache_data(ttl=120)
def fetch_worksheet_df(tab_name):
    if not os.path.exists(CREDS_FILE):
        return None, f"Credentials file not found at `{CREDS_FILE}`"
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(tab_name)
        # Fetch FORMATTED_VALUE to receive evaluated numeric values ($65) instead of formula strings (=AI(...))
        data = sheet.get_all_values(value_render_option='FORMATTED_VALUE')
        if data:
            headers = data[0]
            df = pd.DataFrame(data[1:], columns=headers)
            df = deduplicate_columns(df)
            return df, None
        return pd.DataFrame(), None
    except Exception as e:
        return None, str(e)

st.title("📊 Competitive Pricing Analysis Center")

tab_control, tab_viewer, tab_analytics = st.tabs([
    "⚡ Automation Controls", 
    "📋 Live Sheet Viewer", 
    "📈 Price Comparison Analytics"
])

# ==========================================
# TAB 1: AUTOMATION CONTROLS
# ==========================================
with tab_control:
    st.subheader("🚀 Primary AI Formula Workflow")
    st.caption("Standard monthly process: Generate new month rows and populate =AI(...) formulas directly across all 12 Course Pricing tabs.")
    
    col1, col2 = st.columns(2)

    # --- 1. MONTHLY LAYOUT ROLLOVER ---
    with col1:
        st.markdown("### 1. Monthly Layout Rollover")
        st.caption("Generates new monthly placeholder rows directly in the 12 Course Pricing tabs.")
        
        source_month = st.text_input("Source Month:", value="June 2026")
        new_month = st.text_input("New Month to Create:", value="July 2026")
        
        if st.button("🚀 Run Layout Append", use_container_width=True):
            if not source_month or not new_month:
                st.error("Please provide both Source Month and New Month.")
            elif not os.path.exists(APPEND_SCRIPT):
                st.error("File not found: `append_month.py`")
            else:
                with st.spinner(f"Appending '{new_month}' based on '{source_month}'..."):
                    try:
                        env = os.environ.copy()
                        env["SOURCE_MONTH"] = source_month
                        env["NEW_MONTH"] = new_month
                        env["CREDS_FILE_PATH"] = CREDS_FILE
                        
                        result = subprocess.run(
                            [sys.executable, APPEND_SCRIPT, source_month, new_month], 
                            capture_output=True, text=True, check=True, env=env, cwd=BASE_DIR
                        )
                        st.success(f"Successfully generated rows for {new_month}!")
                        st.cache_data.clear()
                        with st.expander("View Output Logs"):
                            st.code(result.stdout)
                    except subprocess.CalledProcessError as e:
                        st.error("Error executing append_month.py")
                        st.code(e.stderr if e.stderr else e.stdout)

    # --- 2. AI FORMULA POPULATOR ---
    with col2:
        st.markdown("### 2. Google Sheets AI Formula Populator")
        st.caption("Inserts =AI(...) formulas directly into target month cells across all 12 Course Pricing tabs.")
        
        target_month_ai = st.text_input("Target Month for AI Formulas:", value="July 2026", key="ai_month_in")
        
        if st.button("🤖 Populate AI Formulas", use_container_width=True):
            if not target_month_ai:
                st.error("Please enter a Target Month.")
            elif not os.path.exists(AI_FORMULA_SCRIPT):
                st.error("File not found: `run_ai_formula.py`")
            else:
                with st.spinner(f"Populating AI formulas for '{target_month_ai}' across course tabs..."):
                    try:
                        env = os.environ.copy()
                        env["TARGET_MONTH_OVERRIDE"] = target_month_ai
                        env["CREDS_FILE_PATH"] = CREDS_FILE
                        
                        result = subprocess.run(
                            [sys.executable, AI_FORMULA_SCRIPT, target_month_ai], 
                            capture_output=True, text=True, check=True, env=env, cwd=BASE_DIR
                        )
                        st.success(f"Successfully populated AI formulas for {target_month_ai}!")
                        st.cache_data.clear()
                        st.balloons()
                        with st.expander("View Execution Logs"):
                            st.code(result.stdout)
                    except subprocess.CalledProcessError as e:
                        st.error("Error executing run_ai_formula.py")
                        st.code(e.stderr if e.stderr else e.stdout)

    st.divider()

    st.subheader("🛠️ Alternative Data Retrieval & Workaround Tools")
    st.caption("Alternative options if you prefer to run Python web scraping directly or perform manual sheet syncs.")

    col3, col4 = st.columns(2)

    # --- 3. LIVE PRICE SCRAPER ---
    with col3:
        st.markdown("### 3. Live Web Scraper (Python)")
        st.caption("Crawls competitor pages and populates live prices directly into the 12 Course Pricing tabs.")
        
        target_month_scrape = st.text_input("Target Month to Scrape:", value="July 2026", key="scrape_month_in")
        
        if st.button("🔍 Run Web Scraper", use_container_width=True):
            if not target_month_scrape:
                st.error("Please enter a Target Month.")
            elif not os.path.exists(PRICING_SCRIPT):
                st.error("File not found: `pricing.py`")
            else:
                with st.status(f"Scraper running for {target_month_scrape}...", expanded=True) as status:
                    try:
                        env = os.environ.copy()
                        env["TARGET_MONTH_OVERRIDE"] = target_month_scrape
                        env["CREDS_FILE_PATH"] = CREDS_FILE
                        
                        process = subprocess.Popen(
                            [sys.executable, "-u", PRICING_SCRIPT, target_month_scrape], 
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
                            status.update(label=f"Scraping complete for {target_month_scrape}!", state="complete")
                            st.cache_data.clear()
                            st.balloons()
                        else:
                            status.update(label="Scraper encountered an error during execution.", state="error")
                    except Exception as e:
                        st.error(f"Execution failed: {str(e)}")

    # --- 4. COURSE TABS AUTO-SYNC ---
    with col4:
        st.markdown("### 4. Course Tabs Auto-Sync")
        st.caption("Workaround sync tool to refresh individual Course Pricing tabs if data was edited externally.")
        
        if st.button("🔄 Sync Course Tabs Now", use_container_width=True):
            if not os.path.exists(SYNC_SCRIPT):
                st.error("File not found: `sync_course_tabs.py`")
            else:
                with st.spinner("Syncing course tabs in Google Sheets..."):
                    try:
                        env = os.environ.copy()
                        env["CREDS_FILE_PATH"] = CREDS_FILE
                        env["SOURCE_MONTH"] = source_month
                        env["NEW_MONTH"] = new_month
                        
                        result = subprocess.run(
                            [sys.executable, SYNC_SCRIPT], 
                            capture_output=True, text=True, check=True, env=env, cwd=BASE_DIR
                        )
                        st.success("Successfully synced all course tabs!")
                        st.cache_data.clear()
                        st.balloons()
                        with st.expander("View Sync Logs"):
                            st.code(result.stdout)
                    except subprocess.CalledProcessError as e:
                        st.error("Error executing sync_course_tabs.py")
                        st.code(e.stderr if e.stderr else e.stdout)


# ==========================================
# TAB 2: LIVE SHEET VIEWER
# ==========================================
with tab_viewer:
    st.subheader("📋 Google Sheets Live Tab Viewer")
    st.caption("Inspect real-time data from any course pricing worksheet tab.")

    col_sheet_sel, col_refresh = st.columns([3, 1])

    with col_sheet_sel:
        view_tab_name = st.selectbox("Select Course Tab to Display:", COURSE_WORKSHEETS, key="view_tab_select")

    with col_refresh:
        st.write(" ")
        st.write(" ")
        if st.button("🔄 Clear Cache & Reload", use_container_width=True, key="reload_view_btn"):
            st.cache_data.clear()
            st.rerun()

    df_view, err = fetch_worksheet_df(view_tab_name)

    if err:
        st.error(f"Failed to load worksheet '{view_tab_name}': {err}")
    elif df_view is not None and not df_view.empty:
        month_col = df_view.columns[0]
        all_months = [m.strip() for m in df_view[month_col].dropna().unique() if m.strip()]

        f_col1, f_col2 = st.columns([1, 2])
        with f_col1:
            selected_months = st.multiselect("Filter by Month:", all_months, default=all_months)
        with f_col2:
            search_query = st.text_input("Search Competitor / Product:", "")

        filtered_view = df_view.copy()

        if selected_months:
            filtered_view = filtered_view[filtered_view[month_col].str.strip().isin(selected_months)]

        if search_query:
            query_lower = search_query.lower()
            mask = filtered_view.apply(lambda row: row.astype(str).str.lower().str.contains(query_lower).any(), axis=1)
            filtered_view = filtered_view[mask]

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Rows Displayed", len(filtered_view))
        m2.metric("Total Competitor Columns", max(0, len(filtered_view.columns) - 2))
        m3.metric("Selected Worksheet", view_tab_name)

        st.divider()

        st.dataframe(filtered_view, use_container_width=True, hide_index=True, height=500)

        csv_data = filtered_view.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=f"📥 Download '{view_tab_name}' CSV",
            data=csv_data,
            file_name=f"{view_tab_name.replace(' ', '_')}.csv",
            mime="text/csv"
        )
    else:
        st.info(f"Worksheet '{view_tab_name}' is currently empty or has no header row.")


# ==========================================
# TAB 3: PRICE COMPARISON ANALYTICS
# ==========================================
with tab_analytics:
    st.subheader("🔍 Historical Price Movement & Multi-Month Comparison")
    st.caption("Analyze month-over-month price fluctuations across all competitor course tabs.")

    col_workspace, col_btn = st.columns([3, 1])

    with col_workspace:
        selected_tab = st.selectbox("Select Course Tab to Analyze:", COURSE_WORKSHEETS, key="analytics_tab_select")

    with col_btn:
        st.write(" ")
        st.write(" ")
        refresh_data = st.button("🔄 Fetch / Refresh Analytics", use_container_width=True, key="analytics_ref_btn")

    df_analytics, err = fetch_worksheet_df(selected_tab)

    if err:
        st.error(f"Failed to load worksheet '{selected_tab}': {err}")
    elif df_analytics is not None and not df_analytics.empty:
        df = df_analytics.copy()

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
                comparison_month = st.selectbox("Comparison Month (New):", available_months, index=min(1, len(available_months) - 1))

            competitor_cols = [c for c in df.columns[2:] if c.strip()]

            df_base = df[df[month_col].str.strip().str.lower() == baseline_month.lower()][[course_col] + competitor_cols]
            df_comp = df[df[month_col].str.strip().str.lower() == comparison_month.lower()][[course_col] + competitor_cols]

            comparison_rows = []

            for course in df_base[course_col].unique():
                row_base = df_base[df_base[course_col] == course]
                row_comp = df_comp[df_comp[course_col] == course]

                if row_base.empty or row_comp.empty:
                    continue

                for comp in competitor_cols:
                    if comp not in row_base.columns or comp not in row_comp.columns:
                        continue

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
                                "Course / Product": course if str(course).strip() else selected_tab.replace("Pricing - ", ""),
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
                res_df = res_df.drop_duplicates(subset=["Course / Product", "Competitor"], keep="first")

                price_drops = int((res_df["Status"] == "🟢 Price Cut").sum())
                price_hikes = int((res_df["Status"] == "🔴 Price Hike").sum())
                unchanged = int((res_df["Status"] == "⚪ Unchanged").sum())

                met1, met2, met3 = st.columns(3)
                met1.metric("🟢 Price Cuts Detected", price_drops)
                met2.metric("🔴 Price Hikes Detected", price_hikes)
                met3.metric("⚪ Unchanged Listings", unchanged)

                st.divider()

                filter_status = st.multiselect(
                    "Filter by Price Movement:", 
                    ["🟢 Price Cut", "🔴 Price Hike", "⚪ Unchanged"],
                    default=["🟢 Price Cut", "🔴 Price Hike", "⚪ Unchanged"]
                )

                filtered_df = res_df[res_df["Status"].isin(filter_status)]

                st.dataframe(filtered_df, use_container_width=True, hide_index=True, height=450)
            else:
                st.info("No matching numeric price data found to compare between these two selected months.")
    else:
        st.info("Select a valid course tab with data to begin comparison.")
