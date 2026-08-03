import json
import traceback

from clients.sqs_client import delete_message, receive_messages
from db.repository import get_connection
from services.invoice_extraction_service import process_document

QUEUE_NAME = "invoice"


def run():
    print("Listening on the invoice SQS queue...")
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
                    process_document(conn, body["work_id"], body["document_link"])
                delete_message(QUEUE_NAME, msg["ReceiptHandle"])
            except Exception:
                traceback.print_exc()


if __name__ == "__main__":
    run()
