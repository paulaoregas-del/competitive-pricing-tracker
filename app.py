import re
import datetime
import pandas as pd
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from ddgs import DDGS
import streamlit as st

st.set_page_config(
    page_title="ORM: Stolen Content & Image Review Dashboard",
    page_icon="🛡️",
    layout="wide"
)

# ==========================================
# CONSTANTS & SAFE DOMAINS
# ==========================================
OWNED_DOMAINS = [
    "advancedmedicalcertification.com",
    "nhcps.com",
    "disquefoundation.org",
    "hcpcertifications.com",
    "apps.apple.com",
    "play.google.com",
    "facebook.com",
    "linkedin.com",
    "youtube.com",
    "twitter.com",
    "instagram.com"
]

SKIP_URL_PATTERNS = [
    "/terms-conditions", "/privacy-policy", "/terms-of-service", "/disclaimer", "/faq"
]

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def is_legal_or_utility_page(url):
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in SKIP_URL_PATTERNS)


def parse_url_components(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        path = parsed.path if parsed.path else "/"
        return domain, path
    except Exception:
        return "", ""


def extract_page_text_and_images(url):
    """Scrapes clean paragraph text and all image URLs from target page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        title = soup.title.string.strip() if soup.title and soup.title.string else "N/A"

        for element in soup(["header", "footer", "nav", "script", "style", "aside", "form"]):
            element.decompose()

        paragraphs = []
        for p in soup.find_all(["p", "article"]):
            txt = p.get_text().strip()
            if len(txt.split()) >= 10:
                paragraphs.append(txt)

        full_text = " ".join(paragraphs)

        images = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and src.startswith("http"):
                images.append(src)

        return title, full_text, list(set(images))
    except Exception:
        return "Failed to fetch page", "", []


def extract_exact_sentence_fingerprints(text, max_phrases=5, phrase_length=10):
    """Extracts exact verbatim sentences for strict quote search."""
    raw_sentences = re.split(r'[.!?]+', text)
    fingerprints = []

    for s in raw_sentences:
        words = s.strip().split()
        if len(words) >= phrase_length:
            exact_phrase = " ".join(words[:phrase_length])
            fingerprints.append(f'"{exact_phrase}"')

    if len(fingerprints) <= max_phrases:
        return fingerprints

    step = len(fingerprints) // max_phrases
    sampled_phrases = [fingerprints[i * step] for i in range(max_phrases)]
    return sampled_phrases


def find_matching_snippet(orig_phrase, stolen_text):
    clean_phrase = orig_phrase.replace('"', '')
    if clean_phrase.lower() in stolen_text.lower():
        return f"... {clean_phrase} ..."
    return f"Exact stolen phrase found: {clean_phrase}"


# ==========================================
# SIDEBAR CONFIGURATION
# ==========================================
st.sidebar.title("👤 Session Info")
username = st.sidebar.text_input("Username:", value="mirchurc")
batch_number = st.sidebar.text_input("Batch Number:", value="44")
batch_date = st.sidebar.text_input("Batch Date:", value=datetime.date.today().strftime("%m/%d/%Y"))


# ==========================================
# USER INTERFACE (STREAMLIT)
# ==========================================

st.title("🛡️ ORM: Exact Stolen Content & Image Review Dashboard")
st.caption("Verbatim Plagiarism & Reverse Image Search Tool")

tabs = st.tabs([
    "🔍 Exact Stolen Content Checker", 
    "🖼️ Reverse Image Search Generator", 
    "📄 DMCA / C&D Generator", 
    "🛍️ eBay VeRO Notice"
])

# ------------------------------------------
# TAB 1: EXACT STOLEN CONTENT CHECKER
# ------------------------------------------
with tabs[0]:
    st.subheader("1. Enter Original Webpage URLs to Check for Copy-Pasted Content")
    
    url_input = st.text_area(
        "Paste your page URLs below (one per line):",
        placeholder="https://advancedmedicalcertification.com/about/\nhttps://nhcps.com/life-saving-acls-mobile-apps/",
        height=180
    )

    ignore_legal = st.checkbox("Ignore standard legal pages (Terms & Conditions, Privacy Policy)", value=True)

    if st.button("🚀 Find Webpages Copy-Pasting Our Text"):
        if not url_input.strip():
            st.warning("Please paste at least one URL.")
        else:
            urls = [u.strip() for u in url_input.split("\n") if u.strip()]
            results = []

            progress_bar = st.progress(0)
            status_text = st.empty()

            source_num_counter = 1

            for idx, target_url in enumerate(urls):
                status_text.text(f"Scanning page ({idx+1}/{len(urls)}): {target_url}")
                
                if ignore_legal and is_legal_or_utility_page(target_url):
                    progress_bar.progress((idx + 1) / len(urls))
                    continue

                source_title, orig_text, _ = extract_page_text_and_images(target_url)
                source_domain, source_path = parse_url_components(target_url)
                source_words = len(re.findall(r'\b\w+\b', orig_text))

                if source_words < 20:
                    progress_bar.progress((idx + 1) / len(urls))
                    continue

                fingerprints = extract_exact_sentence_fingerprints(orig_text, max_phrases=5, phrase_length=10)
                found_matches = {}

                with DDGS() as ddgs:
                    for phrase in fingerprints:
                        try:
                            search_results = list(ddgs.text(phrase, max_results=5))
                            for res in search_results:
                                match_url = res.get("href", "")
                                if match_url and not any(domain in match_url for domain in OWNED_DOMAINS):
                                    if not (ignore_legal and is_legal_or_utility_page(match_url)):
                                        if match_url not in found_matches:
                                            found_matches[match_url] = []
                                        found_matches[match_url].append(phrase)
                        except Exception:
                            pass

                found_num_counter = 1

                for match_url, matched_phrases in found_matches.items():
                    found_title, stolen_text, _ = extract_page_text_and_images(match_url)
                    found_domain, found_path = parse_url_components(match_url)

                    relative_risk = len(matched_phrases)
                    snippet = find_matching_snippet(matched_phrases[0], stolen_text)

                    view_url = f"http://www.copyscape.com/probrowse.php?u={username}&c=custom&batch={batch_number}&l={source_num_counter}#{found_num_counter}"

                    results.append({
                        "Username": username,
                        "Batch_Num": batch_number,
                        "Batch_Date": batch_date,
                        "Source_Num": source_num_counter,
                        "Found_Num": found_num_counter,
                        "Source_URL": target_url,
                        "Source_Domain": source_domain,
                        "Source_Path": source_path,
                        "Source_Title": source_title,
                        "Source_Words": source_words,
                        "Found_URL": match_url,
                        "Found_Domain": found_domain,
                        "Found_Path": found_path,
                        "Found_Title": found_title,
                        "Relative_Risk": relative_risk,
                        "Snippet": snippet,
                        "View_URL": view_url
                    })
                    found_num_counter += 1

                source_num_counter += 1
                progress_bar.progress((idx + 1) / len(urls))

            status_text.text("Scan complete!")

            if results:
                df = pd.DataFrame(results)
                df = df.sort_values(by=["Relative_Risk", "Source_Num"], ascending=[False, True])

                st.subheader("Stolen Content Results")
                
                # Display table with clickable links
                st.dataframe(
                    df,
                    column_config={
                        "Found_URL": st.column_config.LinkColumn(
                            "Found_URL", 
                            help="Click to view the site using your content",
                            display_text="🔗 Open Page"
                        ),
                        "Source_URL": st.column_config.LinkColumn(
                            "Source_URL",
                            display_text="🌐 Source Page"
                        ),
                        "View_URL": st.column_config.LinkColumn(
                            "View_URL",
                            display_text="🔍 Copyscape View"
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )

                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Export Results for Google Sheets",
                    data=csv,
                    file_name=f"Dup_Content_{batch_number}.csv",
                    mime="text/csv",
                )
            else:
                st.success("🎉 No external websites were found copy-pasting your exact content!")

# ------------------------------------------
# TAB 2: REVERSE IMAGE SEARCH
# ------------------------------------------
with tabs[1]:
    st.subheader("2. Search for Websites Using Your Stolen Images")
    st.write("Paste a URL from your website. The app will extract all images on that page and generate direct Google Reverse Image links.")

    img_page_url = st.text_input("Enter Page URL to check images:")

    if st.button("🚀 Find Websites Using Our Images"):
        if img_page_url:
            with st.spinner("Scraping page images..."):
                _, _, images = extract_page_text_and_images(img_page_url)
                if images:
                    st.success(f"Extracted {len(images)} images from page. Click links below to inspect stolen uses:")
                    for idx, img in enumerate(images, 1):
                        lens_link = f"https://lens.google.com/uploadbyurl?url={img}"
                        
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            st.image(img, width=120)
                        with col2:
                            st.markdown(f"**Image #{idx}**")
                            st.markdown(f"🔍 [Click Here to Search Google Lens for Stolen Uses]({lens_link})")
                            st.caption(f"Source URL: `{img}`")
                        st.divider()
                else:
                    st.info("No public image URLs found on this page.")

# ------------------------------------------
# TAB 3: DMCA / C&D GENERATOR
# ------------------------------------------
with tabs[2]:
    st.subheader("3. Cease & Desist / DMCA Takedown Generator")
    col1, col2 = st.columns(2)
    with col1:
        infringer_domain = st.text_input("Infringing Domain:", "stolen-site-example.com")
        infringing_content_url = st.text_input("Infringing Webpage URL:", "https://stolen-site-example.com/stolen-page")
    with col2:
        original_page_url = st.text_input("Your Original URL:", "https://advancedmedicalcertification.com/about/")
        brand_name = st.text_input("Your Brand / Trademark Name:", "Advanced Medical Certification (AMC)")

    dmca_notice = f"""SUBJECT: DEMAND FOR IMMEDIATE REMOVAL OF COPYRIGHTED CONTENT - DMCA NOTICE

To Webmaster / Legal Team of {infringer_domain},

I am writing to notify you of illegal copyright infringement occurring on your website on behalf of {brand_name}.

1. Original Copyrighted Work:
Location: {original_page_url}
Owner: {brand_name}

2. Unauthorized Infringing Material:
Location: {infringing_content_url}

I have a good-faith belief that use of the material in the manner complained of is not authorized by the copyright owner, its agent, or the law.

I swear, under penalty of perjury, that the information in the notification is accurate and that I am the copyright owner or am authorized to act on behalf of the owner of an exclusive right that is allegedly infringed.

Please immediately remove or disable access to the infringing material by [Insert Date, e.g., 5 business days].

Sincerely,
{username}
Operations Manager, {brand_name}
[Your Contact Email]
"""
    st.text_area("Copy-Paste Legal Letter:", dmca_notice, height=300)

# ------------------------------------------
# TAB 4: EBAY VERO NOTICE
# ------------------------------------------
with tabs[3]:
    st.subheader("4. eBay VeRO Notice of Claimed Infringement (NOCI) Form")
    ebay_item_id = st.text_input("eBay Listing URL or Item ID:")
    ebay_work_desc = st.text_input("Description of Property Stolen:", "AMC Course Materials & Logo")

    vero_text = f"""To: copyright@ebay.com / vero@ebay.com

NOTICE OF CLAIMED INFRINGEMENT (NOCI)

I hereby state:
1. I am the owner or authorized agent of the intellectual property rights for: {ebay_work_desc}.
2. The following listing on eBay infringes on these rights without permission: {ebay_item_id}
3. Good Faith Statement: I have a good-faith belief that the use of the material in the manner complained of is not authorized by the copyright/trademark owner, its agent, or the law.
4. Accuracy Statement: I state, under penalty of perjury, that the information in this notice is accurate and that I am authorized to act on behalf of the owner.

Signature: {username}
Address: [Business Address]
Phone: [Phone Number]
Email: [Contact Email]
"""
    st.text_area("Copy-Paste Email for vero@ebay.com:", vero_text, height=280)