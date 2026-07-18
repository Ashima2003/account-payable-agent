import time
import traceback

from db import (
    claim_work_item,
    fetch_unprocessed_invoice_documents,
    get_connection,
    insert_invoice_and_line_items,
    mark_status,
)
from ocr import pdf_bytes_to_structured_json
from s3_client import fetch_document_bytes

POLL_INTERVAL_SECONDS = 10


def process_document(conn, work_id, document_link):
    if not claim_work_item(conn, work_id):
        # Another poller already picked this one up.
        return

    print(f"[{work_id}] extraction started -> {document_link}")

    try:
        pdf_bytes = fetch_document_bytes(document_link)
        invoice_data = pdf_bytes_to_structured_json(pdf_bytes)
        insert_invoice_and_line_items(conn, work_id, invoice_data)
        mark_status(conn, work_id, "EXTRACTION_COMPLETED")
        print(f"[{work_id}] extraction completed")
    except Exception:
        mark_status(conn, work_id, "EXTRACTION_FAILED")
        print(f"[{work_id}] extraction failed:")
        traceback.print_exc()


def poll_once():
    with get_connection() as conn:
        for doc in fetch_unprocessed_invoice_documents(conn):
            process_document(conn, doc["work_id"], doc["document_link"])


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
