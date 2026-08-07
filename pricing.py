import os
import sys
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import datetime
import re

# ==========================================
# 1. GOOGLE SHEETS & CONFIGURATION SETUP
# ==========================================
SPREADSHEET_ID = "1V2pnwBe4qJj65BBrEc-PQP07SNczMmqI9oNeeGtwedM" 
CREDS_FILE = "pricing-tracker-499202-a9f7e625814b.json" 

# Dynamic month selector: Accepts target month from Streamlit UI, defaulting to "June 2026" if run directly
TARGET_MONTH_OVERRIDE = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TARGET_MONTH_OVERRIDE", "June 2026")

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# ==========================================
# 2. CONTEXT-AWARE SMART SEARCH ENGINE
# ==========================================
def extract_course_specific_price(page_text, course_name):
    clean_text = re.sub(r'\s+', ' ', page_text)
    c_name_lower = course_name.lower().strip()
    
    if "handbook" in c_name_lower or "manual" in c_name_lower:
        kw = c_name_lower.replace("provider", "").replace("handbook", "").replace("pdf", "").replace("manual", "").strip()
        match = re.search(rf'{kw}[^\$]*?(?:handbook|manual|pdf|ebook)[^\$]*?(\$\d+(?:\.\d{{2}})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
        
    if "wall certificate" in c_name_lower:
        kw = c_name_lower.split(" ")[0]
        match = re.search(rf'{kw}[^\$]*?(?:wall\s+certificate|certificate\s+print|physical\s+copy)[^\$]*?(\$\d+(?:\.\d{{2}})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
        
    if "pin" in c_name_lower:
        kw = c_name_lower.split(" ")[0]
        match = re.search(rf'{kw}[^\$]*?(?:pin|lapel\s+pin)[^\$]*?(\$\d+(?:\.\d{{2}})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)

    if "retake" in c_name_lower:
        match = re.search(r'(?:retake|exam\s+insurance|re-test)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)

    if "heartcode" in c_name_lower or "heartsaver" in c_name_lower:
        clean_kw = c_name_lower.replace("®", "").replace("™", "").strip()
        match = re.search(rf'{clean_kw}[^\$]*?(\$\d+(?:\.\d{{2}})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)

    if "bls + cpr recertification" in c_name_lower:
        match = re.search(r'(?:bls\s*\+\s*cpr|bls\s+and\s+cpr)(?:[^\$]*?)(?:recertification|renewal|refresh)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
    elif "free bls for life" in c_name_lower or "acls & pals fo life" in c_name_lower:
        match = re.search(r'(?:free\s+bls|acls\s*(?:\+|&)\s*pals)[^\$]*?(?:life|lifetime)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
    elif "acls for life" in c_name_lower or "acls training course" in c_name_lower:
        match = re.search(r'acls[^\$]*?(?:for\s+life|lifetime|training)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
    elif "bls for life" in c_name_lower:
        match = re.search(r'bls[^\$]*?(?:for\s+life|lifetime)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
    elif "pals for life" in c_name_lower or "pals training course" in c_name_lower:
        match = re.search(r'pals[^\$]*?(?:for\s+life|lifetime|training)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
    elif "cpr for life" in c_name_lower:
        match = re.search(r'(?:cpr|first\s+aid)[^\$]*?(?:for\s+life|lifetime)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
    elif "nrp for life" in c_name_lower:
        match = re.search(r'nrp[^\$]*?(?:for\s+life|lifetime)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
        if match: return match.group(1)
    elif "acls" in c_name_lower:
        if "recertification" in c_name_lower:
            match = re.search(r'acls(?:[^\$]*?)(?:recertification|renewal|refresh)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
            if match: return match.group(1)
        else:
            match = re.search(r'acls(?:[^\$]*?)(?:certification|initial|course)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
            if match: return match.group(1)
    elif "pals" in c_name_lower:
        if "recertification" in c_name_lower:
            match = re.search(r'pals(?:[^\$]*?)(?:recertification|renewal|refresh)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
            if match: return match.group(1)
        else:
            match = re.search(r'pals(?:[^\$]*?)(?:certification|initial|course)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
            if match: return match.group(1)
    elif "bls" in c_name_lower:
        if "recertification" in c_name_lower:
            match = re.search(r'bls(?:[^\$]*?)(?:recertification|renewal|refresh)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
            if match: return match.group(1)
        else:
            match = re.search(r'bls(?:[^\$]*?)(?:certification|initial|course)[^\$]*?(\$\d+(?:\.\d{2})?)', clean_text, re.IGNORECASE)
            if match: return match.group(1)
            
    match = re.search(rf'{re.escape(c_name_lower)}[^\$]*?(\$\d+(?:\.\d{{2}})?)', clean_text, re.IGNORECASE)
    if match: return match.group(1)
    return None

def fetch_page_content(driver, url):
    try:
        driver.get(url)
        time.sleep(4.5)
        if "amazon.com" in url.lower(): return driver, True
        return driver.find_element(By.TAG_NAME, "body").text, False
    except Exception: return None, False

def safe_update(sheet, r, c, val, action="cell", label=None):
    for attempt in range(4):
        try:
            if action == "cell": sheet.update_cell(r, c, val)
            elif action == "note": sheet.update_note(label, val)
            elif action == "format": sheet.format(label, val)
            return
        except gspread.exceptions.APIError:
            print(f"      ⏳ [RATE LIMIT TRIGGERED] Google request limit touched. Cooling down for 12 seconds...")
            time.sleep(12)
        except Exception:
            time.sleep(5)

# ==========================================
# 3. ANTI-QUOTA LOCAL CORE TIMELINE PROCESSOR
# ==========================================
def process_tab_vertically(workbook, tab_name, target_month, driver, today_str):
    print(f"\nScanning Work Area: {tab_name}...")
    sheet = workbook.worksheet(tab_name)
    
    row1_elements = sheet.get_values("1:1", value_render_option="FORMULA")[0]
    all_rows = sheet.get_all_values()
    
    may_rows = []
    april_price_memory = {}
    
    for idx, row in enumerate(all_rows):
        m_label = row[0].strip().lower()
        c_label = row[1].strip()
        if m_label == target_month.lower():
            may_rows.append({'row_num': idx + 1, 'course_name': c_label})
        elif m_label == "may 2026":  # Historical safety memory points back to May!
            for col_idx in range(2, len(row)):
                if row[col_idx].strip(): 
                    april_price_memory[(c_label.lower().strip(), col_idx)] = row[col_idx].strip()

    for col_idx in range(2, len(row1_elements)):
        cell_header = row1_elements[col_idx].strip()
        url = ""
        comp_name = cell_header
        if '=HYPERLINK(' in cell_header.upper():
            try:
                parts = cell_header.split('"')
                url = parts[1]
                comp_name = parts[3]
            except Exception: pass
        if not url or not url.startswith("http"): continue
        
        print(f" -> Accessing [{comp_name}] column values...")
        page_content, is_amazon = fetch_page_content(driver, url)
        if not page_content: continue
            
        for item in may_rows:
            g_row = item['row_num']
            g_col = col_idx + 1
            course_name = item['course_name']
            g_cell = f"{gspread.utils.rowcol_to_a1(g_row, g_col)}"
            
            live_price = None
            if is_amazon:
                amazon_selectors = ["#printPrice", "[for='mediaMatrix_paperback_unselected'] .a-color-price", ".slot-price span", "#price", ".a-price .a-offscreen"]
                for selector in amazon_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            text_val = elements[0].get_attribute("textContent").strip()
                            if "$" in text_val and "0.99" not in text_val:
                                live_price = text_val
                                break
                    except Exception: pass
            else:
                live_price = extract_course_specific_price(page_content, course_name)
                
            historical_baseline = april_price_memory.get((course_name.lower().strip(), col_idx), None)
            
            if not live_price:
                continue
                
            if not historical_baseline:
                safe_update(sheet, g_row, g_col, live_price, "cell")
                safe_update(sheet, None, None, f"First Logged: {today_str}", "note", g_cell)
                safe_update(sheet, None, None, {"backgroundColor": {"red": 1.0, "green": 1.0, "blue": 0.0}, "textFormat": {"bold": True}}, "format", g_cell)
            elif live_price != historical_baseline:
                safe_update(sheet, g_row, g_col, live_price, "cell")
                safe_update(sheet, None, None, f"Previous (May): {historical_baseline} | Changed: {today_str}", "note", g_cell)
                safe_update(sheet, None, None, {"backgroundColor": {"red": 1.0, "green": 1.0, "blue": 0.0}, "textFormat": {"bold": True}}, "format", g_cell)
            else:
                safe_update(sheet, g_row, g_col, live_price, "cell")
                safe_update(sheet, None, None, f"Unchanged from May | Verified: {today_str}", "note", g_cell)
                safe_update(sheet, None, None, {"backgroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "textFormat": {"bold": False}}, "format", g_cell)
        
        time.sleep(1.5)

def main():
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    print(f"--- STARTING PRODUCTION-WIDE 4-TAB QUOTA-SAFE RUN FOR {TARGET_MONTH_OVERRIDE.upper()} ---")
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    client = gspread.authorize(creds)
    workbook = client.open_by_key(SPREADSHEET_ID)
    
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--incognito")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    for target_workspace in ["Master Pricing", "Master Amazon", "Master - Bundles & For Life", "Master Handbooks"]:
        process_tab_vertically(workbook, target_workspace, TARGET_MONTH_OVERRIDE, driver, today_str)
        
    driver.quit()
    print("\n--- ALL TARGET MASTER WORKSPACES EXTRACTED COMPLETELY ---")

if __name__ == "__main__":
    main()