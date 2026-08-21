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
    c_lower = course_name.lower().strip()
    
    # 1. Look for explicit Course + Tier (Recertification vs Initial/Certification)
    if "recertification" in c_lower or "renewal" in c_lower:
        match = re.search(r'(?:recertification|renewal|renew)[^\$]{1,100}?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
    elif "certification" in c_lower or "initial" in c_lower:
        match = re.search(r'(?:certification|initial|course)[^\$]{1,100}?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)

    # 2. Look for Keyword + Price proximity (ACLS / PALS / BLS / CPR / NRP)
    acronyms = ["acls", "pals", "bls", "cpr", "nrp", "bloodborne"]
    for ac in acronyms:
        if ac in c_lower:
            match = re.search(rf'{ac}[^\$]{{1,120}}?(\$\d+(?:\.\d{{2}})?)', clean_text, re.IGNORECASE)
            if match: return match.group(1)

    # 3. Strict fallback: standard price regex requiring a non-generic context
    prices = re.findall(r'(\$\d+(?:\.\d{2})?)', clean_text)
    if prices:
        # Filter out obvious false positives like $0.00, $0, or $19.95 handbook add-ons
        valid = [p for p in prices if p not in ["$0.00", "$0", "$0.0", "$19.95"]]
        if valid:
            return valid[0]
            
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
        
        all_values_formula = ws.get_all_values(value_render_option='FORMULA')

        if not all_values_formula or len(all_values_formula) < 2:
            continue

        headers = all_values_formula[0]
        
        target_row_idx = None
        for r_idx, row in enumerate(all_values_formula[1:], start=2):
            if row and str(row[0]).strip().lower() == target_month.lower():
                target_row_idx = r_idx
                break

        if not target_row_idx:
            print(f"  -> No placeholder row found for '{target_month}' in '{tab_name}'. Skipping.")
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
            elif cell_header.startswith("http"):
                url = cell_header

            if not url or not url.startswith("http"):
                continue

            page_text = fetch_page_text_clean(url)
            if page_text:
                course_name = tab_name.replace("Pricing - ", "")
                found_price = extract_course_specific_price(page_text, course_name)
                
                if found_price:
                    ws.update_cell(target_row_idx, col_idx + 1, found_price)
                    print(f"  -> Updated Column {col_idx+1} ({course_name}) with price: {found_price}")

            time.sleep(0.3)

    print("\n--- ALL COURSE WORKSHEETS PROCESSED SUCCESSFULLY ---")

if __name__ == "__main__":
    main()
