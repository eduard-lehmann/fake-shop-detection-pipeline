import os
import requests
import whois
from urllib.parse import urlparse, urlunparse

BASE_PATH = "C:/Visual-Studio-Code/DATE"
RAW_DATA_DIR = os.path.join(BASE_PATH, "data", "raw")
RAW_HTML_DIR = os.path.join(RAW_DATA_DIR, "html")
RAW_HEADER_DIR = os.path.join(RAW_DATA_DIR, "headers")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
}

def create_directories():
    """Erstellt die Verzeichnisse für HTML und Header"""
    for path in [RAW_DATA_DIR, RAW_HTML_DIR, RAW_HEADER_DIR]:
        os.makedirs(path, exist_ok=True)

def normalize_url(url):
    """Normalisiert URLs, um sie konsistent zu verarbeiten"""
    parsed = urlparse(url)
    if not parsed.scheme:
        parsed = parsed._replace(scheme='http')
    return urlunparse(parsed)

def get_domain_from_url(url):
    parsed_uri = urlparse(url)
    domain = parsed_uri.netloc.replace("www.", "")
    return domain

def safe_domain_for_filename(domain):
    """Entfernt potenziell problematische zeichen für dateinamen"""
    return domain.replace("/", "_").replace(":", "_")

def create_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session

def fetch_html(url, domain):
    try:
        session = create_session()
        response = session.get(
            url,
            timeout=15,
            verify=False,
            allow_redirects=True
        )
        response.raise_for_status()

        if len(response.text) < 2000:
            return False, "HTML zu kurz / möglicherweise blockiert"

        filename = os.path.join(RAW_HTML_DIR, f"{safe_domain_for_filename(domain)}.html")
        with open(filename, "w", encoding="utf-8", errors="ignore") as f:
            f.write(response.text)

        return True, "HTML gespeichert"

    except Exception as e:
        return False, str(e)

def save_headers(domain, headers):
    try:
        filename = os.path.join(RAW_HEADER_DIR, f"{safe_domain_for_filename(domain)}.json")
        with open(filename, "w", encoding="utf-8") as f:
            import json
            json.dump(dict(headers), f, indent=2)
        return True
    except Exception as e:
        print(f"[WARN] Header-Speicherung fehlgeschlagen für {domain}: {e}")
        return False

def fetch_whois(domain):
    try:
        w = whois.whois(domain)
        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
        return str(creation_date) if creation_date else "Unknown"
    except Exception:
        return "Unknown/Error"