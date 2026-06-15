import re
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pytz
import time
import os

# -----------------------------
# CONFIG
# -----------------------------
# DYNAMIC PATH: Works on your Mac Desktop AND automatically works on the Cloud server!
if os.path.exists("service_account.json"):
    SERVICE_ACCOUNT_FILE = "service_account.json"
else:
    SERVICE_ACCOUNT_FILE = "/Users/pausantos/Desktop/service_account.json"

FOLDER_IDS = [
    "10GNhCuyDMKrS7tkgdZVIhuQdF0Ad2r2M",
    "1tu0HWUhN7aOMvyjsiZmKmBEzSaQsrZBq",
    "1Nc9Er0J561K-xfsAHkCAq9IlwE8aim-P"
]
EXTRA_FILE_IDS = [
    "1CDXtpKm9EB--W7hdCpSjLRSWTKmK9BP-qQ8HSF3Tzr8",
    "1E9vsbiAkg_tauaHJIHm2YYwnswfMm8Ba1TSTc4VtFxU"
]
MASTER_TRACKER_ID = "1paxXX57Mry-aL6wpqVAPoUjiMkM4suYw2VCUtDqrrS8"
TRACKER_TAB = "Comment Tracker"
SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]

# -----------------------------
# AUTH & ACCESS
# -----------------------------
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
drive_service = build("drive", "v3", credentials=creds)

master_sheet = gc.open_by_key(MASTER_TRACKER_ID)

try:
    tracker = master_sheet.worksheet(TRACKER_TAB)
except gspread.exceptions.WorksheetNotFound:
    print(f"Tab '{TRACKER_TAB}' not found. Creating it now...")
    tracker = master_sheet.add_worksheet(title=TRACKER_TAB, rows="1000", cols="8")
    tracker.append_row(["Sheet", "Cell/Link", "Comment", "Assignee", "Status", "Last Updated", "CommentID", "Status Check"])
    time.sleep(2)

# -----------------------------
# HELPERS
# -----------------------------
def get_fresh_comment_map():
    data = tracker.get_all_values()
    return {str(row[6]).strip(): i+1 for i, row in enumerate(data) if len(row) > 6 and i > 0}

def get_sticky_assignee(thread_history):
    current_assignee = thread_history[0].get("author", {}).get("displayName", "Unknown")
    for message in thread_history:
        text = message.get("content", "")
        match = re.search(r'@([\w\.-]+)', text)
        if match: current_assignee = match.group(1)
    return current_assignee

def flatten_comment_thread(comment):
    all_comments = [comment]
    for reply in comment.get("replies", []):
        all_comments.extend(flatten_comment_thread(reply))
    return all_comments

def list_sheets_in_folder(folder_id):
    sheets = []
    query = f"'{folder_id}' in parents and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id,name,mimeType)").execute()
    
    for f in results.get("files", []):
        file_name = f["name"]
        name_up = file_name.upper()
        
        # 1. Skip Archive/Copies
        if "OLD" in name_up or "COPY OF" in name_up:
            print(f"⏩ SKIPPED (Archive/Copy): {file_name}")
            continue 
            
        # 2. Skip years 2012-2023
        years_found = re.findall(r'\b(20\d{2})\b', file_name)
        is_old_year = any(2012 <= int(y) <= 2023 for y in years_found)
        if is_old_year:
            print(f"⏩ SKIPPED (Old Year 2012-2023): {file_name}")
            continue

        if f["mimeType"] == "application/vnd.google-apps.folder":
            sheets.extend(list_sheets_in_folder(f["id"]))
        elif f["mimeType"] in ["application/vnd.google-apps.spreadsheet", "application/vnd.google-apps.document"]:
            sheets.append({"id": f["id"], "name": f["name"]})
    return sheets

# -----------------------------
# MAIN SYNC
# -----------------------------
print("\n--- INITIATING SYSTEM PULSE ---")

raw_file_list = []
for fid in FOLDER_IDS:
    raw_file_list.extend(list_sheets_in_folder(fid))

for eid in EXTRA_FILE_IDS:
    try:
        f_meta = drive_service.files().get(fileId=eid, fields="id,name").execute()
        raw_file_list.append({"id": f_meta["id"], "name": f_meta["name"]})
    except: pass

seen_file_ids = set()
unique_files = []
for f in raw_file_list:
    if f["id"] not in seen_file_ids:
        unique_files.append(f)
        seen_file_ids.add(f["id"])

print(f"\n✅ Queue Verified: {len(unique_files)} unique files to scan.\n")

comment_map = get_fresh_comment_map()
new_rows = []

for idx, f in enumerate(unique_files, start=1):
    file_id, file_name = f["id"], f["name"]
    print(f"[{idx}/{len(unique_files)}] Pulsing: {file_name}")
    
    time.sleep(1.5)  # Slightly increased spacing between API reads
    comments = []
    page_token = None
    while True:
        try:
            res = drive_service.comments().list(
                fileId=file_id,
                fields="nextPageToken, comments(id,resolved,content,createdTime,modifiedTime,author,replies)",
                pageSize=100, pageToken=page_token, includeDeleted=True 
            ).execute()
            comments.extend(res.get("comments", []))
            page_token = res.get("nextPageToken")
            if not page_token: break
        except: break

    for c in comments:
        cid = str(c["id"]).strip()
        thread = sorted(flatten_comment_thread(c), key=lambda x: x.get('createdTime', ''))
        latest = thread[-1]
        text = (latest.get("content") or "").replace("\n", " ").strip()
        is_resolved = c.get("resolved", False)
        status = "Resolved" if is_resolved else "Open"
        updated = latest.get("modifiedTime", latest.get("createdTime"))
        link = f"https://docs.google.com/open?id={file_id}&disco={cid}"

        if cid in comment_map:
            row_num = comment_map[cid]
            if is_resolved:
                tracker.delete_rows(row_num)
                time.sleep(2.0)  # Safe delay after deletion
                comment_map = get_fresh_comment_map()
            else:
                assignee = get_sticky_assignee(thread)
                tracker.update(range_name=f"C{row_num}:F{row_num}", values=[[text, assignee, status, updated]])
                time.sleep(1.0)  # Safe delay after row update
        elif not is_resolved and text:
            if not any(cid == r[6] for r in new_rows):
                assignee = get_sticky_assignee(thread)
                new_rows.append([file_name, link, text, assignee, status, updated, cid, ""])

if new_rows:
    tracker.append_rows(new_rows, value_input_option="USER_ENTERED")
    time.sleep(2.0)

# --- RE-CALC OVERDUE ---
all_data = tracker.get_all_records()
manila = pytz.timezone("Asia/Manila")
now = datetime.now(manila)
status_updates = []
for row in all_data:
    try:
        ts_str = row.get("Last Updated", "").replace("Z", "+00:00")
        updated_time = datetime.fromisoformat(ts_str).astimezone(manila)
        status_updates.append(["Overdue"] if now - updated_time > timedelta(days=2) else ["On Track"])
    except:
        status_updates.append(["On Track"])

if status_updates:
    tracker.update(range_name=f"H2:H{len(status_updates)+1}", values=status_updates)
    time.sleep(2.0)

# --- PERSONAL TAB SYNC (ANTI-QUOTA SAFETY ENABLED) ---
print("\nRefreshing Personal Tabs...")
all_data_final = tracker.get_all_records()

groups = {}
for r in all_data_final:
    raw_assignee = r.get('Assignee', 'Unknown')
    if not raw_assignee or raw_assignee == "Unknown": 
        continue
    
    name = raw_assignee.lower().strip()
    tab_name = ".".join(name.split())
    
    if tab_name not in groups: 
        groups[tab_name] = []
    
    groups[tab_name].append([
        f'=HYPERLINK("{r["Cell/Link"]}", "{r["Sheet"]}")', 
        r['Comment'], r['Status'], r['Last Updated'], r['Status Check']
    ])

all_worksheets = master_sheet.worksheets()
existing_tab_names = [ws.title for ws in all_worksheets]
tabs_to_process = set(list(groups.keys()) + [t for t in existing_tab_names if "." in t])

for tab_name in tabs_to_process:
    if tab_name in [TRACKER_TAB, "Instructions", "Dashboard", "Master Tracker"]:
        continue

    try:
        try: 
            pt = master_sheet.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            if tab_name in groups:
                print(f"➕ Creating New Tab: {tab_name}")
                pt = master_sheet.add_worksheet(title=tab_name, rows="1000", cols="5")
                pt.append_row(["Source File (Link)", "Comment", "Status", "Last Updated", "Status Check"])
                time.sleep(2.5)
            else:
                continue
            
        pt.batch_clear(["A2:E1000"])
        time.sleep(2.0)  # CRITICAL: Added extra breath after clearing sheet

        if tab_name in groups:
            rows = groups[tab_name]
            pt.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"✅ Updated: {tab_name} ({len(rows)} comments)")
        else:
            print(f"🧹 Cleared: {tab_name} (No pending comments)")
            
        time.sleep(2.5)  # CRITICAL: Breathe 2.5 seconds before hitting the next user tab!
    except Exception as e:
        print(f"❌ Error with {tab_name}: {e}")
        time.sleep(5.0)  # If it hits an error, wait 5 full seconds to cool off the API quota

print("\n✅ Pulse Complete. All tabs synchronized.")
