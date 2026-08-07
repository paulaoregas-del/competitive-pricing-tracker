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

# Add Sidebar Logout Option
st.sidebar.button("Log Out", on_click=lambda: st.session_state.update(authenticated=False))

# ==============================================================================
# 3. GOOGLE SHEETS CONNECTION & DATA LOADING
# ==============================================================================
@st.cache_data(ttl=600)
def load_pricing_data():
    """Connect to Google Sheets using Streamlit Secrets and load pricing data."""
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Load service account credentials directly from Streamlit Cloud Secrets
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Connect to your Google Sheet by ID
        SPREADSHEET_ID = "1V2pnwBe4qJj65BBrEc-PQP07SNczMmqI9oNeeGtwedM"
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        
        # Extract records into a Pandas DataFrame
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Error loading data from Google Sheets: {e}")
        return pd.DataFrame()

# ==============================================================================
# 4. DASHBOARD INTERFACE
# ==============================================================================
st.title("📊 Competitive Pricing Analysis Dashboard")
st.caption("Automated price tracking and market intelligence platform")

df = load_pricing_data()

if df.empty:
    st.warning("No pricing data currently available or Google Sheets connection error.")
else:
    # Sidebar Filtering Options
    st.sidebar.header("Dashboard Controls")
    
    # Column selector
    all_columns = df.columns.tolist()
    selected_columns = st.sidebar.multiselect(
        "Display Columns", 
        options=all_columns, 
        default=all_columns
    )
    
    filtered_df = df[selected_columns] if selected_columns else df

    # Key Summary Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Records Tracked", len(filtered_df))
    with col2:
        st.metric("Active Columns", len(filtered_df.columns))
    with col3:
        st.metric("Google Sheets Status", "Connected 🟢")

    st.markdown("---")

    # Interactive Data Table View
    st.subheader("Price Comparison Overview")
    st.dataframe(filtered_df, use_container_width=True)

    # Refresh Data Button
    if st.button("🔄 Refresh Data from Google Sheets"):
        st.cache_data.clear()
        st.rerun()
