import os
import sys
import json
import re
import urllib.request
import time
import datetime
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

def extract_course_specific_price(page_text, course_name):
    clean_text = re.sub(r'\s+', ' ', page_text)
    c_name_lower = course_name.lower().strip()
    
    if "acls" in c_name_lower:
        match = re.search(r'acls(?:[^\$]*?)(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
    elif "pals" in c_name_lower:
        match = re.search(r'pals(?:[^\$]*?)(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
    elif "bls" in c_name_lower:
        match = re.search(r'bls(?:[^\$]*?)(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
            
    match = re.search(r'(\$\d+(?:\.\d{2})?)', clean_text)
    if match: return match.group(1)
    return None

def fetch_page_text_clean(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            clean_text = re.sub(r'<(script|style).*?>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r'<.*?>', ' ', clean_text)
            return re.sub(r'\s+', ' ', clean_text)
    except Exception:
        return ""

def main():
    target_month = os.environ.get("TARGET_MONTH_OVERRIDE") or (sys.argv[1] if len(sys.argv) > 1 else "August 2026")
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    print(f"--- STARTING HTTP PRICE SCRAPER FOR TARGET PERIOD: {target_month.upper()} ---")
    
    if not os.path.exists(CREDS_FILE):
        raise FileNotFoundError(f"Credentials file missing at '{CREDS_FILE}'.")

    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    client = gspread.authorize(creds)
    workbook = client.open_by_key(SPREADSHEET_ID)

    existing_tabs = [ws.title for ws in workbook.worksheets()]

    for tab_name in COURSE_WORKSHEETS:
        if tab_name not in existing_tabs:
            continue

        print(f"Scanning Course Tab: '{tab_name}'...")
        ws = workbook.worksheet(tab_name)
        all_values = ws.get_all_values()

        if not all_values or len(all_values) < 2:
            continue

        headers = all_values[0]
        
        target_row_idx = None
        for r_idx, row in enumerate(all_values[1:], start=2):
            if row and row[0].strip().lower() == target_month.lower():
                target_row_idx = r_idx
                break

        if not target_row_idx:
            print(f"  -> No target row found for '{target_month}' in '{tab_name}'. Skipping.")
            continue

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

            page_text = fetch_page_text_clean(url)
            if page_text:
                course_name = tab_name.replace("Pricing - ", "")
                found_price = extract_course_specific_price(page_text, course_name)
                
                if found_price:
                    ws.update_cell(target_row_idx, col_idx + 1, found_price)
                    print(f"  -> Updated Column {col_idx+1} with price: {found_price}")

            time.sleep(0.5)

    print("\n--- ALL COURSE WORKSHEETS SCRAPED & UPDATED SUCCESSFULLY ---")

if __name__ == "__main__":
    main()
