import os
import time
import json
import logging
import pandas as pd
import requests
from urllib.parse import urlparse
from ingestion_utils import (
    create_directories,
    get_domain_from_url,
    normalize_url,
    safe_domain_for_filename,
    fetch_whois,
    create_session
)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Konstante Pfade
BASE_PATH = "C:/Visual-Studio-Code/DATE"
RAW_HTML_DIR = os.path.join(BASE_PATH, "data/raw/html")
RAW_HEADER_DIR = os.path.join(BASE_PATH, "data/raw/headers")
DOCS_DIR = os.path.join(BASE_PATH, "docs")
SEED_CSV = os.path.join(BASE_PATH, "data/seed/URL_SEED.csv")
OUTPUT_CSV = os.path.join(DOCS_DIR, "ingestion_report.csv")
LOG_DIR = os.path.join(BASE_PATH, "logs")

# Logging Setup
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "ingestion.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Verzeichnisse anlegen
create_directories()

# Seed CSV einlesen
try:
    df = pd.read_csv(SEED_CSV)
    assert "url" in df.columns
except Exception as e:
    logging.error(f"Fehler beim Einlesen der URL_SEED.csv: {e}")
    raise SystemExit("Abbruch: Seed-CSV nicht gefunden oder ungültig")

logging.info(f"{len(df)} URLs geladen.")
#print(f"[INFO] {len(df)} URLs geladen.")

# Ergebnisse sammeln
results = []
session = create_session()

# Haupt-Loop
for i, row in df.iterrows():
    url_raw = row["url"]
    url = normalize_url(url_raw)
    domain = get_domain_from_url(url)
    domain_safe = safe_domain_for_filename(domain)

    logging.info(f"[INGEST] {domain}")
    #print(f"[INGEST] {domain}")

    meta = {
        "url": url,
        "domain": domain,
        "tld": domain.split(".")[-1],
        "ingestion_timestamp": pd.Timestamp.now()
    }

    try:
        start = time.time()
        r = session.get(url, timeout=15, verify=False, allow_redirects=True)
        duration = int((time.time() - start) * 1000)

        meta.update({
            "http_status": r.status_code,
            "final_url": r.url,
            "redirected": int(r.url != url),
            "response_time_ms": duration,
            "content_type": r.headers.get("Content-Type", ""),
            "server_header": r.headers.get("Server", ""),
            "html_size": len(r.text),
            "has_https": int(r.url.startswith("https")),
            "ssl_error": 0,
            "html_status": "OK"
        })

        # HTML speichern
        html_path = os.path.join(RAW_HTML_DIR, f"{domain_safe}.html")
        with open(html_path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(r.text)

        # Header speichern
        header_path = os.path.join(RAW_HEADER_DIR, f"{domain_safe}.json")
        with open(header_path, "w") as f:
            json.dump(dict(r.headers), f, indent=2)

    except Exception as e:
        logging.error(f"Fehler bei {url}: {e}")
        meta.update({
            "http_status": 0,
            "final_url": "",
            "redirected": 0,
            "response_time_ms": 0,
            "content_type": "",
            "server_header": "",
            "html_size": 0,
            "has_https": 0,
            "ssl_error": 1,
            "html_status": "FAIL",
            "error_msg": str(e)
        })

    # WHOIS-Abfrage
    creation_date = fetch_whois(domain)
    meta.update({
        "creation_date": creation_date,
        "whois_available": int(creation_date not in ["Unknown", None, ""])
    })

    results.append(meta)

    # Zwischenspeichern nach jedem 10. Eintrag
    if len(results) % 10 == 0:
        pd.DataFrame(results).to_csv(OUTPUT_CSV, index=False)

    time.sleep(1)

# Report abspeichern
pd.DataFrame(results).to_csv(OUTPUT_CSV, index=False)
logging.info("[SUCCESS] Ingestion abgeschlossen")
#print("[SUCCESS] Ingestion abgeschlossen")
print(f"Ingestion-Report: {OUTPUT_CSV}")