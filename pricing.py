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

def extract_course_specific_price(page_text, course_name, comp_name):
    clean_text = re.sub(r'\s+', ' ', page_text)
    c_lower = course_name.lower().strip()
    
    if "recertification" in c_lower or "renewal" in c_lower:
        match = re.search(r'(?:recertification|recertified|renewal|renew)[^\$]{1,80}?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
    elif "certification" in c_lower or "initial" in c_lower:
        match = re.search(r'(?:certification|certified|initial|course)[^\$]{1,80}?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)

    acronyms = ["acls", "pals", "bls", "cpr", "nrp", "bloodborne"]
    for ac in acronyms:
        if ac in c_lower:
            match = re.search(rf'{ac}[^\$]{{1,100}}?(\$\d+(?:\.\d{{2}})?)', clean_text, re.IGNORECASE)
            if match: return match.group(1)

    match = re.search(r'(\$\d+(?:\.\d{2})?)', clean_text)
    if match: return match.group(1)
    return None

def fetch_page_text_clean(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            html = response.read().decode('utf-8', errors='ignore')
            clean_text = re.sub(r'<(script|style).*?>.*.*?/\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r'<.*?>', ' ', clean_text)
            return re.sub(r'\s+', ' ', clean_text)
    except Exception:
        return ""

def main():
    target_month = os.environ.get("TARGET_MONTH_OVERRIDE") or (sys.argv[1] if len(sys.argv) > 1 else "August 2026")
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

        print(f"\nScanning Course Tab: '{tab_name}'...")
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

        # Check all headers from Column 3 (C) through Column 45 (AS)
        max_col_to_check = min(len(headers), 45)

        for col_idx in range(2, max_col_to_check):
            cell_header = str(headers[col_idx]).strip()
            url = ""
            comp_name = f"Competitor Column {col_idx + 1}"

            # Universal regex to find http/https URLs inside single quotes, double quotes, or raw text
            url_match = re.search(r'https?://[^\s"\',)]+', cell_header, re.IGNORECASE)
            if url_match:
                url = url_match.group(0)

            # Extract label from HYPERLINK formula if present
            label_match = re.search(r'HYPERLINK\s*\(\s*["\'][^"\']+["\']\s*,\s*["\']([^"\']+)["\']\s*\)', cell_header, re.IGNORECASE)
            if label_match:
                comp_name = label_match.group(1)

            if not url:
                print(f"  -> Column {col_idx + 1} [{comp_name}]: Blank header or no URL in cell.")
                continue

            print(f"  -> Fetching live price for [{comp_name}] ({url})...")
            page_text = fetch_page_text_clean(url)
            
            if page_text:
                course_name = tab_name.replace("Pricing - ", "")
                found_price = extract_course_specific_price(page_text, course_name, comp_name)
                
                if found_price:
                    ws.update_cell(target_row_idx, col_idx + 1, found_price)
                    print(f"     ✅ Updated [{comp_name}] in Column {col_idx+1} with price: {found_price}")
                else:
                    print(f"     ⚠️ No price pattern matched on [{comp_name}] page.")
            else:
                print(f"     ⚠️ Empty/blocked response from [{comp_name}].")

            time.sleep(0.4)

    print("\n--- ALL COURSE WORKSHEETS PROCESSED SUCCESSFULLY ---")

if __name__ == "__main__":
    main()
