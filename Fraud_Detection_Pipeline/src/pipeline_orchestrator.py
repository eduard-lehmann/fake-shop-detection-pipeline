import logging
import os
from datetime import datetime
import time

# Logging Konfiguration
if not os.path.exists("C:/Visual-Studio-Code/DATE/logs"):
    os.makedirs("C:/Visual-Studio-Code/DATE/logs")

logging.basicConfig(
    filename=f'C:/Visual-Studio-Code/DATE/logs/pipeline_run_{datetime.now().strftime("%Y%m%d")}.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_pipeline_step(step_name, command):
    print(f"--- Starte {step_name} ---")
    logging.info(f"START: {step_name}")
    start_time = time.time()
    
    exit_code = os.system(command)
    
    duration = time.time() - start_time
    
    if exit_code == 0:
        logging.info(f"SUCCESS: {step_name} (Dauer: {duration:.2f}s)")
        print(f"--- {step_name} erfolgreich ---\n")
        return True
    else:
        logging.error(f"FAILURE: {step_name} (Exit Code: {exit_code})")
        print(f"--- {step_name} FEHLGESCHLAGEN ---\n")
        return False

def main():
    logging.info("Pipeline-Start initiiert.")
    
    # Phase 1: Ingestion
    if not run_pipeline_step("Ingestion", "python DATE/src/run_ingestion.py"):
        return

    # Phase 2: Processing
    if not run_pipeline_step("Processing", "python DATE/src/run_processing.py"):
        return

    # Phase 3: Storage
    if not run_pipeline_step("Storage", "python DATE/src/run_storage.py"):
        return

    logging.info("Pipeline erfolgreich beendet.")
    print("Pipeline fertig. Prüfen Sie den Ordner /logs für Details.")

if __name__ == "__main__":
    main()