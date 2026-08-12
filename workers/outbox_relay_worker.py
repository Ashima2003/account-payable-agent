import time
import traceback

from clients.sqs_client import publish_message
from db.repository import fetch_unpublished_outbox_messages, get_connection, mark_outbox_published

RELAY_INTERVAL_SECONDS = 5


def relay_once():
    with get_connection() as conn:
        for row in fetch_unpublished_outbox_messages(conn):
            publish_message(row["queue_name"], row["payload"])
            mark_outbox_published(conn, row["id"])


def run():
    print(f"Relaying outbox messages to SQS every {RELAY_INTERVAL_SECONDS}s...")
    while True:
        try:
            relay_once()
        except Exception:
            traceback.print_exc()
        time.sleep(RELAY_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
