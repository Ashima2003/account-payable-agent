import logging
import time
import traceback

from logging_config import configure_logging
from services.email_ingestion_service import run_ingestion

log = logging.getLogger("ap_agent.ingestion")

POLL_INTERVAL_SECONDS = 30


def run():
    log.info("polling every %ss for new emails...", POLL_INTERVAL_SECONDS)
    while True:
        try:
            run_ingestion()
        except Exception:
            traceback.print_exc()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    configure_logging()
    run()
