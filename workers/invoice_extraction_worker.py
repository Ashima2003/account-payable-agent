import time
import traceback

from services.invoice_extraction_service import poll_once

POLL_INTERVAL_SECONDS = 10


def run():
    print(f"Polling every {POLL_INTERVAL_SECONDS}s for new invoice documents...")
    while True:
        try:
            poll_once()
        except Exception:
            traceback.print_exc()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
