import logging
import time
import traceback

from clients.sqs_client import publish_message
from db.repository import fetch_unpublished_outbox_messages, get_connection, mark_outbox_published
from logging_config import configure_logging, trace

log = logging.getLogger("ap_agent.outbox")

RELAY_INTERVAL_SECONDS = 5


def relay_once():
    with get_connection() as conn:
        for row in fetch_unpublished_outbox_messages(conn):
            with trace(row["id"]):
                publish_message(row["queue_name"], row["payload"])
                mark_outbox_published(conn, row["id"])
                log.info("relayed to %s: %s", row["queue_name"], row["payload"])


def run():
    log.info("relaying outbox messages to SQS every %ss...", RELAY_INTERVAL_SECONDS)
    while True:
        try:
            relay_once()
        except Exception:
            traceback.print_exc()
        time.sleep(RELAY_INTERVAL_SECONDS)


if __name__ == "__main__":
    configure_logging()
    run()
