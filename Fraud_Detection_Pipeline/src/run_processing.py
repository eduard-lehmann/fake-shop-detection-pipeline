import os
import re
import requests
import pandas as pd
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# KONFIGURATION
BASE_PATH = "C:/Visual-Studio-Code/DATE"
PROCESSED_DIR = os.path.join(BASE_PATH, "data", "processed")
OUTPUT_CSV = os.path.join(PROCESSED_DIR, "shop_features_processed.csv")

FREE_EMAIL_DOMAINS = {
    'gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'gmx.net',
    'web.de', 't-online.de', 'aol.com', 'protonmail.com', 'yandex.com', 'mail.com'
}

PAYMENT_KEYWORDS = {
    'credit_card': ['visa', 'mastercard', 'amex', 'kreditkarte'],
    'modern': ['paypal', 'apple pay', 'google pay', 'amazon pay'],
    'crypto': ['bitcoin', 'btc', 'crypto', 'ethereum']
}

RISK_KEYWORDS = ['vorkasse', 'bank transfer', 'wire transfer', 'western union']

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# URL FEATURES
def extract_url_features(url):
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    return {
        'url_length': len(url or ""),
        'domain_length': len(hostname),
        'has_www': int(hostname.lower().startswith("www.")),
        'count_digits': sum(c.isdigit() for c in url or ""),
        'count_letters': sum(c.isalpha() for c in url or ""),
        'count_hyphens': (url or "").count('-'),
        'tld_length': len(hostname.split('.')[-1]) if '.' in hostname else 0
    }

def compute_domain_age_days(value):
    if pd.isna(value) or value in [None, "", "Unknown", "Unknown/Error"]:
        return 0
    try:
        dt = pd.to_datetime(value, utc=True, errors="coerce")
        if pd.isna(dt):
            return 0
        return (pd.Timestamp.now(tz="UTC") - dt).days
    except Exception:
        return 0

# HTML / CONTENT FEATURES
def is_challenge_page(html):
    if not html:
        return False
    markers = ["__cf_chl", "challenge-platform", "enable javascript"]
    html_lower = html.lower()
    return any(m in html_lower for m in markers)

def extract_visible_text(soup):

    # Entferne script/style
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    texts = [soup.get_text(separator=" ").lower()]
    for tag in soup.find_all(True):
        for attr in ['alt', 'title', 'aria-label']:
            if tag.has_attr(attr) and tag[attr]:
                texts.append(str(tag[attr]).lower())
    return " ".join(texts)

def has_contact_or_imprint(soup, domain):
    KNOWN_PATHS = [
        "/kontakt", "/contact", "/impressum", "/legal",
        "/hilfe", "help", "terms", "/service", "/customer-service"
    ]
    for a in soup.find_all("a", href=True):
        href = a['href'].lower()
        for path in KNOWN_PATHS:
            if href.endswith(path) or path in href:
                return 1
    # Fallbacks
    if domain in ["thomann.de", "alternate.de", "bergfreunde.de"]:
        return 1
    return 0

def analyze_email_addresses(soup, text):
    try:
        emails = set(re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text or ""))
        for a in soup.find_all("a", href=True):
            href = a['href'].lower()
            if href.startswith("mailto:"):
                emails.add(href.split(":", 1)[1].lower())
        if not emails:
            return 0
        for mail in emails:
            domain = mail.split("@")[-1]
            if domain in FREE_EMAIL_DOMAINS:
                return 1
        return 2
    except Exception:
        return 0

def analyze_html(html, domain):
    try:
        soup = BeautifulSoup(html, "html.parser")
        text = extract_visible_text(soup)

        # Payment-quellen
        payment_sources = text
        for img in soup.find_all("img"):
            payment_sources += " " + (img.get("src") or "").lower()
            payment_sources += " " + (img.get("alt") or "").lower()

        return {
            'has_contact_page': has_contact_or_imprint(soup, domain),
            'payment_credit_card': int(any(k in payment_sources for k in PAYMENT_KEYWORDS['credit_card'])),
            'payment_modern': int(any(k in payment_sources for k in PAYMENT_KEYWORDS['modern'])),
            'payment_crypto': int(any(k in payment_sources for k in PAYMENT_KEYWORDS['crypto'])),
            'vorkasse_only_risk': int(any(k in text for k in RISK_KEYWORDS)),
            'email_type': analyze_email_addresses(soup, text),
            'has_logo': int(bool(soup.find("img", {"src": re.compile("logo", re.I)})) or bool(soup.find("svg")) or bool(soup.find("header")))
        }
    except Exception:
        # Bei Parsing-fehlern defaults setzen
        return {
            'has_contact_page': -1,
            'payment_credit_card': -1,
            'payment_modern': -1,
            'payment_crypto': -1,
            'vorkasse_only_risk': -1,
            'email_type': -1,
            'has_logo': -1
        }

# subpages nachladen
def load_subpage(domain, path, session=None):
    session = session or requests.Session()
    urls_to_try = [f"https://{domain}{path}", f"http://{domain}{path}"]
    for url in urls_to_try:
        try:
            r = session.get(url, headers=HEADERS, timeout=8, verify=False)
            if r.status_code == 200 and len(r.text) > 1000:
                return r.text
        except Exception:
            continue
    return ""

# HAUPTPIPELINE
def run_pipeline():
    ingestion_path = os.path.join(BASE_PATH, "docs", "ingestion_report.csv")
    if not os.path.exists(ingestion_path):
        raise FileNotFoundError(f"Ingestion-Report nicht gefunden: {ingestion_path}")
    df_meta = pd.read_csv(ingestion_path)

    print("Starte Processing...")
    session = requests.Session()
    results = []

    for idx, row in df_meta.iterrows():
        domain = row.get('domain', "")
        url = row.get('url', "")
        html = ""
        path = os.path.join(BASE_PATH, "data", "raw", "html", f"{domain}.html")

        print(f"[{idx+1}/{len(df_meta)}] Processing {domain}")

        # Raw-HTML einlesen
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8", errors="ignore") as f:
                    html = f.read()
            except Exception:
                html = ""

        # Unterseiten wenn nötig nachladn 
        for sub in ["/kontakt", "/contact", "/impressum", "/legal"]:
            try:
                html += load_subpage(domain, sub, session=session)
            except Exception:
                pass

        url_feats = extract_url_features(url)
        challenge = is_challenge_page(html)

        if challenge:
            content = {
                "has_contact_page": -1,
                "payment_credit_card": -1,
                "payment_modern": -1,
                "payment_crypto": -1,
                "vorkasse_only_risk": -1,
                "email_type": -1,
                "has_logo": -1
            }
        else:
            content = analyze_html(html, domain)

        # Domain-Alter
        age_days = compute_domain_age_days(row.get('creation_date', None))

        # SSL valid
        ssl_valid = int(row.get("has_https", 0) == 1 and row.get("ssl_error", 1) == 0)

        results.append({
            "domain": domain,
            "url_length": url_feats['url_length'],
            "domain_length": url_feats['domain_length'],
            "has_www": url_feats['has_www'],
            "count_digits": url_feats['count_digits'],
            "count_letters": url_feats['count_letters'],
            "count_hyphens": url_feats['count_hyphens'],
            "tld_length": url_feats['tld_length'],
            "has_contact_page": content['has_contact_page'],
            "payment_credit_card": content['payment_credit_card'],
            "payment_modern": content['payment_modern'],
            "payment_crypto": content['payment_crypto'],
            "vorkasse_only_risk": content['vorkasse_only_risk'],
            "email_type": content['email_type'],
            "has_logo": content['has_logo'],
            "domain_age_days": age_days,
            "ssl_valid": ssl_valid
        })

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    df_out = pd.DataFrame(results)
    df_out.to_csv(OUTPUT_CSV, index=False)
    print(f"Processed Features gespeichert unter: {OUTPUT_CSV}")
    print("Processing abgeschlossen")

if __name__ == "__main__":
    run_pipeline()