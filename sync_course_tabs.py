import os
import sys
import json
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# CONFIGURATION & CREDENTIALS
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.environ.get("CREDS_FILE_PATH", os.path.join(BASE_DIR, "pricing-tracker-499202-a9f7e625814b.json"))

SPREADSHEET_ID = "1V2pnwBe4qJj65BBrEc-PQP07SNczMmqI9oNeeGtwedM"
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Mapping Course Tab names to Master Source Sheets & Keyword Filters
COURSE_MAPPINGS = {
    "Pricing - ACLS Certification": {"master": "Master Pricing", "keyword": "ACLS Certification"},
    "Pricing - ACLS Recertification": {"master": "Master Pricing", "keyword": "ACLS Recertification"},
    "Pricing - PALS Certification": {"master": "Master Pricing", "keyword": "PALS Certification"},
    "Pricing - PALS Recertification": {"master": "Master Pricing", "keyword": "PALS Recertification"},
    "Pricing - BLS Certification": {"master": "Master Pricing", "keyword": "BLS Certification"},
    "Pricing - BLS Recertification": {"master": "Master Pricing", "keyword": "BLS Recertification"},
    "Pricing - CPR, AED & First Aid Certification": {"master": "Master Pricing", "keyword": "CPR, AED & First Aid Certification"},
    "Pricing - CPR, AED & First Aid Recertification": {"master": "Master Pricing", "keyword": "CPR, AED & First Aid Recertification"},
    "Pricing - Bloodborne Pathogens": {"master": "Master Pricing", "keyword": "Bloodborne Pathogens"},
    "Pricing - NRP Certification": {"master": "Master Pricing", "keyword": "NRP Certification"},
    "Pricing - NRP Recertification": {"master": "Master Pricing", "keyword": "NRP Recertification"},
    "Pricing - Bundles & For Life": {"master": "Master - Bundles & For Life", "keyword": ""}
}

def main():
    months_to_sync = [
        os.environ.get("SOURCE_MONTH", "May 2026"),
        os.environ.get("NEW_MONTH", "June 2026")
    ]

    print(f"Starting course tabs auto-sync for months: {months_to_sync}")
    print(f"Credentials path: {CREDS_FILE}")

    if not os.path.exists(CREDS_FILE):
        raise FileNotFoundError(f"Credentials file missing at: '{CREDS_FILE}'")

    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    # Cache master worksheets data
    master_cache = {}

    for tab_name, config in COURSE_MAPPINGS.items():
        master_sheet_name = config["master"]
        keyword = config["keyword"].strip().lower()

        # Load master sheet if not already loaded
        if master_sheet_name not in master_cache:
            try:
                m_ws = spreadsheet.worksheet(master_sheet_name)
                m_vals = m_ws.get_all_values()
                if m_vals and len(m_vals) > 1:
                    master_cache[master_sheet_name] = pd.DataFrame(m_vals[1:], columns=m_vals[0])
                else:
                    master_cache[master_sheet_name] = pd.DataFrame()
            except Exception as e:
                print(f"Error reading master worksheet '{master_sheet_name}': {str(e)}")
                master_cache[master_sheet_name] = pd.DataFrame()

        master_df = master_cache[master_sheet_name]
        if master_df.empty:
            print(f"Skipping '{tab_name}': Master tab '{master_sheet_name}' has no data.")
            continue

        try:
            target_ws = spreadsheet.worksheet(tab_name)
        except Exception:
            print(f"Target worksheet '{tab_name}' not found in Google Sheets. Skipping.")
            continue

        month_col = master_df.columns[0]
        course_col = master_df.columns[1]

        for month in months_to_sync:
            # Filter rows by month and keyword
            month_mask = master_df[month_col].str.strip().str.lower() == month.strip().lower()
            if keyword:
                course_mask = master_df[course_col].str.strip().str.lower().str.contains(keyword, na=False)
                filtered_df = master_df[month_mask & course_mask]
            else:
                filtered_df = master_df[month_mask]

            if filtered_df.empty:
                print(f"No matching rows found for '{tab_name}' in month '{month}'.")
                continue

            target_vals = target_ws.get_all_values()
            
            # Check if rows for this month already exist in the target worksheet
            existing_months = [r[0].strip().lower() for r in target_vals[1:] if r] if len(target_vals) > 1 else []

            rows_to_append = filtered_df.values.tolist()

            if month.strip().lower() in existing_months:
                print(f"Updating existing rows for '{month}' in worksheet '{tab_name}'...")
                # Find matching row indices and update them
                for row_idx, row_data in enumerate(target_vals[1:], start=2):
                    if row_data and row_data[0].strip().lower() == month.strip().lower():
                        # Find matching course row in filtered data
                        course_name = row_data[1].strip().lower() if len(row_data) > 1 else ""
                        match = filtered_df[filtered_df[course_col].str.strip().str.lower() == course_name]
                        if not match.empty:
                            update_row = match.iloc[0].tolist()
                            target_ws.update(f"A{row_idx}", [update_row])
            else:
                print(f"Appending {len(rows_to_append)} rows for '{month}' to worksheet '{tab_name}'...")
                target_ws.append_rows(rows_to_append)

            print(f"✅ Successfully synced '{tab_name}' for {month}!")

    print("🎉 All course tabs sync completed successfully!")

if __name__ == "__main__":
    main()
