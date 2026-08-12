import json
import logging
import traceback

from clients.sqs_client import delete_message, receive_messages
from db.repository import get_connection
from logging_config import configure_logging
from services.invoice_extraction_service import process_document

log = logging.getLogger("ap_agent.invoice")

QUEUE_NAME = "invoice"


def run():
    log.info("listening on the invoice SQS queue...")
    while True:
        try:
            messages = receive_messages(QUEUE_NAME)
        except Exception:
            traceback.print_exc()
            continue

        for msg in messages:
            try:
                body = json.loads(msg["Body"])
                with get_connection() as conn:
                    # process_document() opens its own trace(work_id)
                    # context -- see logging_config.py.
                    process_document(conn, body["work_id"], body["document_link"])
                delete_message(QUEUE_NAME, msg["ReceiptHandle"])
            except Exception:
                traceback.print_exc()


if __name__ == "__main__":
    configure_logging()
    run()
