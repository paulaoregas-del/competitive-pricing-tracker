import os
import sys
import json
import re
import urllib.request
import gspread
from oauth2client.service_account import ServiceAccountCredentials

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.environ.get("CREDS_FILE_PATH", os.path.join(BASE_DIR, "pricing-tracker-499202-a9f7e625814b.json"))

SPREADSHEET_ID = "1YGKMhO0hvWmKe-i03C0mTDcI4LquaAzA-2_oaioMpko"
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

def fetch_page_text_clean(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            # Strip out script/style elements and HTML tags using regex
            clean_text = re.sub(r'<(script|style).*?>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r'<.*?>', ' ', clean_text)
            return re.sub(r'\s+', ' ', clean_text)
    except Exception:
        return ""

def main():
    target_month = os.environ.get("TARGET_MONTH_OVERRIDE") or (sys.argv[1] if len(sys.argv) > 1 else "July 2026")
    print(f"--- STARTING HTTP PRICE SCRAPER FOR: {target_month.upper()} ---")
    
    if not os.path.exists(CREDS_FILE):
        raise FileNotFoundError(f"Credentials file missing at '{CREDS_FILE}'.")

    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    client = gspread.authorize(creds)
    workbook = client.open_by_key(SPREADSHEET_ID)

    existing_tabs = [ws.title for ws in workbook.worksheets()]

    for tab_name in COURSE_WORKSHEETS:
        if tab_name not in existing_tabs:
            print(f"Skipping tab '{tab_name}' (not present in sheet).")
            continue

        print(f"Scanning Course Tab: {tab_name}...")
        ws = workbook.worksheet(tab_name)
        all_values = ws.get_all_values()

        if not all_values or len(all_values) < 2:
            continue

        headers = all_values[0]
        
        for col_idx in range(2, len(headers)):
            cell_header = headers[col_idx].strip()
            url = ""
            if '=HYPERLINK(' in cell_header.upper():
                try:
                    parts = cell_header.split('"')
                    url = parts[1]
                except Exception:
                    pass
            
            if not url or not url.startswith("http"):
                continue

            content = fetch_page_text_clean(url)
            if content:
                print(f"  -> Successfully fetched URL content for column {col_idx+1}")

    print("\n--- SCRAPER EXECUTED SUCCESSFULLY ---")

if __name__ == "__main__":
    main()
