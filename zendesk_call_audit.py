import requests
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials

# -----------------------------
# CONFIGURATION
# -----------------------------
SUBDOMAIN = "satorisupport"
EMAIL = "paula.oregas@nhcps.com"
API_TOKEN = "lH7KUCaNytrHEz3vyTrZFgh19tEAmzkBOSj5cDy8"
auth = (f"{EMAIL}/token", API_TOKEN)

BASE_PATH = "/Users/pausantos/Desktop"
SERVICE_ACCOUNT_FILE = os.path.join(BASE_PATH, "service_account.json")
SPREADSHEET_ID = "1hiw2ALS9-eD5DSzu1VCbOcHaohyfbrOfWqFTWXA6jEE"
TAB_NAME = "Call_Audit"

# -----------------------------
# SETUP
# -----------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SPREADSHEET_ID)

try:
    sheet = spreadsheet.worksheet(TAB_NAME)
except:
    sheet = spreadsheet.add_worksheet(title=TAB_NAME, rows="2000", cols="7")
    sheet.append_row(["Ticket ID", "Date", "Agent", "Call Type", "Customer Phone", "Our Number (Dialed)", "Ticket Link"])

def safe_request(url):
    return requests.get(url, auth=auth)

# -----------------------------
# PROCESS
# -----------------------------
# Searching for all voice tickets from April 1st
query = "type:ticket via:voice created>2026-04-01"
url = f"https://{SUBDOMAIN}.zendesk.com/api/v2/search.json?query={query}"

rows = []
user_cache = {}

print("--- Starting Deep-Sync Call Audit ---")

response = safe_request(url)
if response.status_code == 200:
    tickets = response.json().get("results", [])
    
    for ticket in tickets:
        t_id = ticket["id"]
        t_link = f"https://{SUBDOMAIN}.zendesk.com/agent/tickets/{t_id}"
        clean_date = ticket["created_at"].replace("T", " ").replace("Z", "")[:16]

        # Get Agent Name
        assignee_id = ticket.get("assignee_id")
        agent_name = "Unassigned"
        if assignee_id:
            if assignee_id not in user_cache:
                u_resp = safe_request(f"https://{SUBDOMAIN}.zendesk.com/api/v2/users/{assignee_id}.json")
                if u_resp.status_code == 200:
                    user_cache[assignee_id] = u_resp.json()["user"]["name"]
            agent_name = user_cache.get(assignee_id, "Unknown")

        # FETCH COMMENTS TO GET VOICE METADATA
        c_url = f"https://{SUBDOMAIN}.zendesk.com/api/v2/tickets/{t_id}/comments.json"
        comments_data = safe_request(c_url).json().get("comments", [])
        
        call_type = "Voice Call"
        customer_no = "N/A"
        dialed_no = "N/A"

        for c in comments_data:
            # Check if it's a Voice Comment
            if c.get("type") == "VoiceComment" or "call_id" in str(c.get("data", {})):
                data = c.get("data", {})
                
                # Extract 'to' (Our Number) and 'from' (Customer)
                customer_no = data.get("from", customer_no)
                dialed_no = data.get("to", dialed_no)
                
                # Determine Call Type
                body = c.get("body", "").lower()
                if "voicemail" in body: call_type = "Voicemail"
                elif "outbound" in body: call_type = "Outbound"
                elif "inbound" in body: call_type = "Inbound"
                break

        rows.append([t_id, clean_date, agent_name, call_type, customer_no, dialed_no, t_link])
        print(f"  + Logged {call_type} for Ticket {t_id}")

if rows:
    # Append the clean data
    sheet.append_rows(rows)
    print(f"\nSuccess! Check your '{TAB_NAME}' tab.")