import os
import sys
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.environ.get("CREDS_FILE_PATH", os.path.join(BASE_DIR, "pricing-tracker-499202-a9f7e625814b.json"))

SPREADSHEET_ID = "1V2pnwBe4qJj65BBrEc-PQP07SNczMmqI9oNeeGtwedM"
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

TARGET_WORKSHEETS = [
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

def col_to_letter(col_idx):
    """Converts 1-based column index to Excel letter (e.g., 3 -> 'C')."""
    result = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result

def main():
    target_month = os.environ.get("TARGET_MONTH_OVERRIDE") or (sys.argv[1] if len(sys.argv) > 1 else "July 2026")

    print(f"Starting AI Formula Population for month: '{target_month}'")
    print(f"Using credentials file at: {CREDS_FILE}")

    if not os.path.exists(CREDS_FILE):
        raise FileNotFoundError(f"Credentials file missing at: '{CREDS_FILE}'")

    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    for sheet_name in TARGET_WORKSHEETS:
        try:
            ws = spreadsheet.worksheet(sheet_name)
            all_values = ws.get_all_values(value_render_option='FORMULA')

            if not all_values or len(all_values) < 2:
                print(f"Skipping empty sheet: '{sheet_name}'")
                continue

            headers = all_values[0]
            num_cols = len(headers)

            if num_cols < 3:
                continue

            # Find matching rows for target month
            updates = []
            for row_idx, row_data in enumerate(all_values[1:], start=2):
                if not row_data:
                    continue
                
                row_month = row_data[0].strip().lower() if len(row_data) > 0 else ""
                
                if row_month == target_month.strip().lower():
                    course_name = row_data[1].strip() if len(row_data) > 1 else "Course"
                    
                    for col_idx in range(3, num_cols + 1):  # Columns C onwards
                        col_letter = col_to_letter(col_idx)
                        # Formula string referencing course name and header cell
                        ai_formula = f'=AI("what is the current price of {course_name} on " & {col_letter}$1 & " website?")'
                        
                        cell_address = f"{col_letter}{row_idx}"
                        updates.append({
                            'range': cell_address,
                            'values': [[ai_formula]]
                        })

            if updates:
                ws.batch_update(updates, value_input_option='USER_ENTERED')
                print(f"✅ Populated {len(updates)} AI formulas in worksheet '{sheet_name}' for '{target_month}'")
            else:
                print(f"No placeholder rows found for '{target_month}' in sheet '{sheet_name}'. Run Layout Append first.")

        except Exception as e:
            print(f"Error processing worksheet '{sheet_name}': {str(e)}")

    print("🎉 AI Formula population completed across all tabs!")

if __name__ == "__main__":
    main()
