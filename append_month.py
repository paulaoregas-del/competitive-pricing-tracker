import os
import sys
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# CREDENTIALS & GOOGLE SHEETS CONFIGURATION
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CREDS_FILE = os.environ.get("CREDS_FILE_PATH", os.path.join(BASE_DIR, "pricing-tracker-499202-a9f7e625814b.json"))

SPREADSHEET_ID = "1V2pnwBe4qJj65BBrEc-PQP07SNczMmqI9oNeeGtwedM"
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

ALL_WORKSHEETS = [
    "Master Pricing", 
    "Master Amazon", 
    "Master - Bundles & For Life", 
    "Master Handbooks",
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

def main():
    source_month = os.environ.get("SOURCE_MONTH") or (sys.argv[1] if len(sys.argv) > 1 else "June 2026")
    new_month = os.environ.get("NEW_MONTH") or (sys.argv[2] if len(sys.argv) > 2 else "July 2026")

    print(f"Starting layout rollover across ALL sheets: '{source_month}' -> '{new_month}'")
    print(f"Using credentials file at: {CREDS_FILE}")

    if not os.path.exists(CREDS_FILE):
        raise FileNotFoundError(f"Credentials file not found at '{CREDS_FILE}'. Please verify Streamlit Secrets configuration.")

    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    for sheet_name in ALL_WORKSHEETS:
        try:
            ws = spreadsheet.worksheet(sheet_name)
            all_values = ws.get_all_values()
            
            if not all_values:
                print(f"Skipping empty sheet: {sheet_name}")
                continue

            headers = all_values[0]
            rows = all_values[1:]

            # Filter rows belonging to source month
            source_rows = [r for r in rows if r and str(r[0]).strip().lower() == source_month.strip().lower()]

            if not source_rows:
                print(f"No source rows found for '{source_month}' in sheet '{sheet_name}'. Skipping.")
                continue

            # Check if new month rows already exist
            existing_new_rows = [r for r in rows if r and str(r[0]).strip().lower() == new_month.strip().lower()]
            if existing_new_rows:
                print(f"Rows for '{new_month}' already exist in '{sheet_name}'. Skipping duplicate creation.")
                continue

            # Create duplicate template rows with the new month name
            new_rows = []
            for row in source_rows:
                new_row = list(row)
                new_row[0] = new_month  # Set Month column to new month
                for i in range(2, len(new_row)):
                    new_row[i] = ""
                new_rows.append(new_row)

            ws.append_rows(new_rows)
            print(f"✅ Appended {len(new_rows)} rows for '{new_month}' in '{sheet_name}'.")

        except Exception as e:
            print(f"Error processing worksheet '{sheet_name}': {str(e)}")

    print("🎉 Append month rollover operation completed across ALL 16 sheets!")

if __name__ == "__main__":
    main()
