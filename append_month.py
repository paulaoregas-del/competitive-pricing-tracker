import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- CONFIGURATION ---
SPREADSHEET_ID = "1V2pnwBe4qJj65BBrEc-PQP07SNczMmqI9oNeeGtwedM"
CREDS_FILE = "pricing-tracker-499202-a9f7e625814b.json"

SOURCE_MONTH = "May 2026"
NEW_MONTH = "June 2026"

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def append_new_month_block(workbook, tab_name):
    try:
        sheet = workbook.worksheet(tab_name)
    except Exception:
        print(f"⚠️ Tab '{tab_name}' not found. Skipping.")
        return

    print(f"Scanning '{tab_name}' to copy structural items...")
    all_rows = sheet.get_all_values()
    row1_headers = sheet.get_values("1:1", value_render_option="FORMULA")[0]

    active_items = []
    for row in all_rows:
        if row[0].strip().lower() == SOURCE_MONTH.lower():
            if row[1].strip():
                active_items.append(row[1].strip())

    if not active_items:
        print(f"   ❌ No items found for {SOURCE_MONTH} inside '{tab_name}'.")
        return

    already_exists = any(row[0].strip().lower() == NEW_MONTH.lower() for row in all_rows)
    if already_exists:
        print(f"   ℹ️ Block for {NEW_MONTH} already exists in '{tab_name}'. Skipping append.")
        return

    append_payload = []
    for item_name in active_items:
        new_row = [NEW_MONTH, item_name] + [""] * (len(row1_headers) - 2)
        append_payload.append(new_row)

    sheet.append_rows(append_payload, value_input_option="USER_ENTERED")
    print(f"   ✅ Successfully added {len(append_payload)} clean matching rows for {NEW_MONTH}!")
    time.sleep(1)

def main():
    print(f"Connecting to Google Sheets to expand timeline: {SOURCE_MONTH} -> {NEW_MONTH}...")
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    client = gspread.authorize(creds)
    workbook = client.open_by_key(SPREADSHEET_ID)

    workspaces = ["Master Pricing", "Master Amazon", "Master - Bundles & For Life", "Master Handbooks"]
    for workspace in workspaces:
        append_new_month_block(workbook, workspace)

    print(f"\n--- SUCCESS: ALL BLANK TIMELINE ROWS FOR {NEW_MONTH.upper()} GENERATED MIGRATION-READY ---")

if __name__ == "__main__":
    main()