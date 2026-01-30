import os
import sqlite3
import pandas as pd

# KONFIGURATION
BASE_PATH = "C:/Visual-Studio-Code/DATE"

PROCESSED_CSV = os.path.join(
    BASE_PATH, "data", "processed", "shop_features_processed.csv"
)

ANALYTICS_DIR = os.path.join(BASE_PATH, "data", "analytics")
ANALYTICS_CSV = os.path.join(ANALYTICS_DIR, "feature_matrix_corpus.csv")

DB_PATH = os.path.join(BASE_PATH, "date_fraud_detection.db")

# STORAGE PIPELINE
def run_storage():
    print("Starte Data Storage...")

    if not os.path.exists(PROCESSED_CSV):
        print("[ERROR] Processed CSV nicht gefunden.")
        return

    df = pd.read_csv(PROCESSED_CSV)

    if df.empty:
        print("[WARN] Keine Daten zum Speichern.")
        return

    os.makedirs(ANALYTICS_DIR, exist_ok=True)


    # SQLite Storage
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS shop_features (
            domain TEXT PRIMARY KEY,
            url_length INTEGER,
            domain_length INTEGER,
            has_www INTEGER,
            count_digits INTEGER,
            count_letters INTEGER,
            count_hyphens INTEGER,
            tld_length INTEGER,
            has_contact_page INTEGER,
            payment_credit_card INTEGER,
            payment_modern INTEGER,
            payment_crypto INTEGER,
            vorkasse_only_risk INTEGER,
            email_type INTEGER,
            has_logo INTEGER,
            domain_age_days INTEGER,
            ssl_valid INTEGER
        )
    """)

    df.to_sql(
        "shop_features",
        conn,
        if_exists="replace",
        index=False
    )

    conn.commit()
    conn.close()

    print("[SUCCESS] Features in SQLite gespeichert")

 
    # Analytics/ML export
    df_analytics = df.drop(columns=["domain"], errors="ignore")
    df_analytics.fillna(-1, inplace=True)

    df_analytics.to_csv(ANALYTICS_CSV, index=False)

    print("[SUCCESS] Analytics CSV erstellt")
    print(f"Pfad: {ANALYTICS_CSV}")

    print("Storage abgeschlossen")

if __name__ == "__main__":
    run_storage()