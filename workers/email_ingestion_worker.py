import time
import traceback

from services.email_ingestion_service import run_ingestion

POLL_INTERVAL_SECONDS = 30


def run():
    print(f"Polling every {POLL_INTERVAL_SECONDS}s for new emails...")
    while True:
        try:
            run_ingestion()
        except Exception:
            traceback.print_exc()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
