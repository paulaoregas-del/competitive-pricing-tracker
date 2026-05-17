import requests
import gspread
import json
import time
import os
import re
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil import parser
from bs4 import BeautifulSoup

# -----------------------------
# CONFIGURATION
# -----------------------------
SUBDOMAIN = "satorisupport"
EMAIL = "paula.oregas@nhcps.com"
API_TOKEN = "lH7KUCaNytrHEz3vyTrZFgh19tEAmzkBOSj5cDy8"
auth = (f"{EMAIL}/token", API_TOKEN)

BASE_PATH = "/Users/pausantos/Desktop"
SERVICE_ACCOUNT_FILE = os.path.join(BASE_PATH, "service_account.json")
STATE_FILE = os.path.join(BASE_PATH, "zendesk_last_run.json")
SPREADSHEET_ID = "1hiw2ALS9-eD5DSzu1VCbOcHaohyfbrOfWqFTWXA6jEE"
TAB_NAME = "Replies"

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
    sheet = spreadsheet.add_worksheet(title=TAB_NAME, rows="5000", cols="7")
    sheet.append_row(["Ticket ID", "Agent", "Customer Contact", "First Reply Time", "Status", "Tags", "Thread"])

def remove_duplicates_from_sheet(worksheet):
    """Deep cleans the sheet by removing any rows with duplicate Ticket IDs."""
    print("\n--- Running Auto-Cleanup of Duplicates ---")
    data = worksheet.get_all_values()
    if not data: return
    
    header = data[0]
    rows = data[1:]
    
    seen_ids = set()
    unique_rows = []
    duplicate_count = 0
    
    for row in rows:
        t_id = row[0]
        if t_id not in seen_ids:
            unique_rows.append(row)
            seen_ids.add(t_id)
        else:
            duplicate_count += 1
            
    if duplicate_count > 0:
        print(f"Detected {duplicate_count} duplicate rows. Cleaning up...")
        # Clear sheet and re-upload only unique data
        worksheet.clear()
        worksheet.append_rows([header] + unique_rows)
        print("Sheet is now 100% unique.")
    else:
        print("No duplicates found. Sheet is clean.")

# Get existing IDs to prevent adding more during this run
existing_ids = set(sheet.col_values(1))

def safe_request(url):
    while True:
        r = requests.get(url, auth=auth)
        if r.status_code == 429:
            retry = int(r.headers.get("Retry-After", 25))
            time.sleep(retry + 2)
            continue
        return r

def clean_html_with_links(html_body):
    if not html_body: return ""
    soup = BeautifulSoup(html_body, "html.parser")
    for a in soup.find_all('a', href=True):
        link_text, href = a.get_text(strip=True), a['href']
        if href and href not in link_text:
            a.replace_with(f"{link_text} ({href})")
    return soup.get_text(separator="\n")

def calculate_reply_time(created, reply):
    try:
        c_time, r_time = parser.parse(created), parser.parse(reply)
        minutes = int((r_time - c_time).total_seconds() / 60)
        return f"{minutes} min" if minutes < 60 else f"{round(minutes/60, 1)} hr"
    except: return "N/A"

# -----------------------------
# MAIN PROCESS
# -----------------------------
user_cache = {}
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        start_time = json.load(f).get("last_run", int(datetime(2026, 4, 1).timestamp()))
else:
    start_time = int(datetime(2026, 4, 1).timestamp())

url = f"https://{SUBDOMAIN}.zendesk.com/api/v2/incremental/tickets.json?start_time={start_time}&include=users"

print(f"--- Starting Enriched Export ---")

while url:
    print(f"\nFetching Page: {url}")
    response = safe_request(url)
    if response.status_code != 200: break
    
    data = response.json()
    tickets = data.get("tickets", [])
    if not tickets: break

    if "users" in data:
        for u in data["users"]:
            user_cache[u["id"]] = {"name": u["name"], "contact": u.get("email") or u.get("phone") or "No Contact"}

    rows_to_add = []
    print(f"Scanning {len(tickets)} updates...", end="")

    for i, ticket in enumerate(tickets):
        t_id = str(ticket["id"])
        if i % 50 == 0: print(".", end="", flush=True)

        if t_id in existing_ids: continue
        
        c_resp = safe_request(f"https://{SUBDOMAIN}.zendesk.com/api/v2/tickets/{t_id}/comments.json")
        if c_resp.status_code != 200: continue
        comments = c_resp.json().get("comments", [])

        req_id = ticket["requester_id"]
        if req_id not in user_cache:
            u_resp = safe_request(f"https://{SUBDOMAIN}.zendesk.com/api/v2/users/{req_id}.json")
            if u_resp.status_code == 200:
                u = u_resp.json()["user"]
                user_cache[req_id] = {"name": u["name"], "contact": u.get("email") or u.get("phone") or "N/A"}

        cust_info = user_cache.get(req_id, {}).get("contact", "Unknown")
        agent_name, first_reply_time, thread_parts = None, None, []

        for comment in comments:
            if not comment["public"]: continue
            author_id = comment["author_id"]
            if author_id not in user_cache:
                u_resp = safe_request(f"https://{SUBDOMAIN}.zendesk.com/api/v2/users/{author_id}.json")
                if u_resp.status_code == 200:
                    u = u_resp.json()["user"]
                    user_cache[author_id] = {"name": u["name"], "contact": u.get("email", "N/A")}

            author_name = user_cache.get(author_id, {"name": "Unknown"})["name"]
            readable_body = clean_html_with_links(comment.get("html_body", ""))
            role = "🔴 Customer" if author_id == req_id else f"🔵 Agent ({author_name})"
            
            if author_id != req_id and not agent_name:
                agent_name = author_name
                first_reply_time = calculate_reply_time(ticket["created_at"], comment["created_at"])

            thread_parts.append(f"[{comment['created_at']}]\n{role}:\n{readable_body}\n")

        if agent_name:
            thread_text = "\n" + "-"*40 + "\n" + "\n".join(thread_parts)
            if len(thread_text) > 49000:
                thread_text = thread_text[:49000] + "\n\n[!!! TICKET TRUNCATED !!!]"
            rows_to_add.append([t_id, agent_name, cust_info, first_reply_time, ticket["status"], ",".join(ticket.get("tags", [])), thread_text])
            existing_ids.add(t_id)

    if rows_to_add:
        print(f"\n  + Adding {len(rows_to_add)} tickets...")
        sheet.append_rows(rows_to_add)

    if data.get("end_of_stream") is True:
        with open(STATE_FILE, "w") as f:
            json.dump({"last_run": data.get("end_time")}, f)
        print("\n>>> Caught up!")
        break
    url = data.get("next_page")

# FINAL STEP: Scrub the entire sheet for any duplicates that snuck in
remove_duplicates_from_sheet(sheet)
print("\nRun complete.")