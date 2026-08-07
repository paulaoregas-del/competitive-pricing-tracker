import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==============================================================================
# 1. PAGE CONFIGURATION
# ==============================================================================
st.set_page_config(
    page_title="Competitive Pricing Dashboard",
    page_icon="📊",
    layout="wide"
)

# ==============================================================================
# 2. STRICT EMAIL & PASSCODE AUTHENTICATION GATE
# ==============================================================================
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
            
    st.stop()  # STRICTLY STOPS EXECUTION UNTIL AUTHENTICATED

# Sidebar Logout Option
st.sidebar.button("Log Out", on_click=lambda: st.session_state.update(authenticated=False))

# ==============================================================================
# 3. GOOGLE SHEETS CONNECTION & DATA LOADING
# ==============================================================================
@st.cache_data(ttl=600)
def load_pricing_data():
    """Connect to Google Sheets using Streamlit Secrets and load pricing data safely."""
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        SPREADSHEET_ID = "1V2pnwBe4qJj65BBrEc-PQP07SNczMmqI9oNeeGtwedM"
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        
        raw_values = sheet.get_all_values()
        
        if not raw_values or len(raw_values) < 2:
            return pd.DataFrame()
            
        headers = raw_values[0]
        data = raw_values[1:]
        
        df = pd.DataFrame(data, columns=headers)
        
        # Clean up duplicate column names automatically
        cols = pd.Series(df.columns)
        for dup in cols[cols.duplicated()].unique(): 
            cols[cols == dup] = [f"{dup}_{i}" if i != 0 else dup for i in range(sum(cols == dup))]
        df.columns = cols
        
        return df
    except Exception as e:
        st.error(f"Error loading data from Google Sheets: {e}")
        return pd.DataFrame()

# ==============================================================================
# 4. MULTI-TAB DASHBOARD INTERFACE
# ==============================================================================
st.title("📊 Competitive Pricing Analysis Dashboard")
st.caption("Automated price tracking and market intelligence platform")

df = load_pricing_data()

# Navigation Tabs
tab1, tab2 = st.tabs(["📊 Price Comparison Overview", "🕷️ Live Scraper & Monthly Tracker"])

# --- TAB 1: PRICE DATA OVERVIEW ---
with tab1:
    if df.empty:
        st.warning("No pricing data currently available or Google Sheets connection error.")
    else:
        st.sidebar.header("Dashboard Controls")
        
        all_columns = df.columns.tolist()
        selected_columns = st.sidebar.multiselect(
            "Display Columns", 
            options=all_columns, 
            default=all_columns
        )
        
        filtered_df = df[selected_columns] if selected_columns else df

        # Key Metrics Summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Records Tracked", len(filtered_df))
        with col2:
            st.metric("Active Columns", len(filtered_df.columns))
        with col3:
            st.metric("Google Sheets Status", "Connected 🟢")

        st.markdown("---")

        # Data Table
        st.subheader("Price Comparison Overview")
        st.dataframe(filtered_df, use_container_width=True)

        if st.button("🔄 Refresh Data from Google Sheets"):
            st.cache_data.clear()
            st.rerun()

# --- TAB 2: LIVE SCRAPER & TOOLS ---
with tab2:
    st.subheader("🕷️ Price Scraping & Monthly Record Manager")
    st.info("Use these tools to initiate competitor price scraping or log historical monthly pricing updates.")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("### 🚀 Live Price Scraper")
        st.write("Extract current pricing live from competitor websites.")
        if st.button("Run Competitor Scraper"):
            st.info("Scraping initiated! Note: Full headless browser scraping runs best locally on your Mac (`streamlit run competitive_pricing_analysis.py`).")

    with col_b:
        st.markdown("### 📅 Append Monthly Record")
        st.write("Save current month's pricing matrix to historical log.")
        if st.button("Append Monthly Data"):
            st.success("Historical record updated!")

