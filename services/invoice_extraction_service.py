import traceback

from db.repository import (
    append_log,
    claim_work_item,
    fetch_line_item_comparison,
    fetch_unprocessed_invoice_documents,
    find_duplicate_invoice,
    find_po_in_source,
    find_similar_vendor,
    get_connection,
    insert_invoice_and_line_items,
    insert_invoice_source_and_line_items,
    mark_status,
    parse_invoice_date,
)
from clients.embeddings_client import embed_text
from clients.ocr_client import pdf_bytes_to_structured_json
from clients.s3_client import fetch_document_bytes
from services.validation import build_duplicate_decline_reply, lines_match, vendor_is_match


def _check_duplicate(conn, work_id, invoice_data) -> bool:
    """Returns True if this invoice has already been processed -- in which
    case this execution is marked SKIPPED (with a draft decline reply
    logged) and the caller must not go on to insert it into
    invoice/line_item."""
    duplicate_work_id = find_duplicate_invoice(
        conn,
        invoice_number=invoice_data.invoice_no or "UNKNOWN",
        purchase_order=invoice_data.purchase_order,
        invoice_date=parse_invoice_date(invoice_data.invoice_date),
        total_amount=invoice_data.invoice_amount or 0,
        invoice_currency=invoice_data.currency or "USD",
        exclude_work_id=work_id,
    )
    if duplicate_work_id is None:
        return False

    reply = build_duplicate_decline_reply(invoice_data.invoice_no, invoice_data.purchase_order)
    append_log(
        conn, work_id, "SKIPPED",
        detail=f"duplicate of work_id {duplicate_work_id}; draft_reply: {reply}",
    )
    mark_status(conn, work_id, "SKIPPED")
    print(f"[{work_id}] skipped: duplicate of {duplicate_work_id}")
    return True


def _check_po(conn, work_id, invoice_data) -> None:
    """PO validation: does this PO number appear on an earlier processed
    invoice (invoice_source), and if so do this invoice's line items match
    that earlier invoice's line items (line_item_source)? Purely
    informational -- logged, doesn't block extraction from completing."""
    purchase_order = invoice_data.purchase_order
    if not purchase_order:
        return

    source_work_id = find_po_in_source(conn, purchase_order, exclude_work_id=work_id)
    if source_work_id is None:
        append_log(conn, work_id, "PO_NOT_FOUND", detail=f"PO {purchase_order!r} not seen on any prior invoice")
        print(f"[{work_id}] PO {purchase_order!r} not found in invoice_source -- unverified")
        return

    # Both sides are read out of line_item_source -- this invoice's own
    # rows (inserted earlier in process_document, embeddings included) and
    # the matched PO's rows -- rather than comparing DB rows against the
    # in-memory OCR object, since description matching now needs the
    # embedding that's only stored in the table.
    comparison_rows = fetch_line_item_comparison(conn, current_work_id=work_id, source_work_id=source_work_id)
    if lines_match(comparison_rows):
        append_log(conn, work_id, "PO_VALIDATED", detail=f"matches invoice_source work_id {source_work_id}")
        print(f"[{work_id}] PO {purchase_order!r} validated against {source_work_id}")
    else:
        append_log(
            conn, work_id, "PO_VALIDATION_MISMATCH",
            detail=f"line items differ from invoice_source work_id {source_work_id}",
        )
        print(f"[{work_id}] PO {purchase_order!r} line items do NOT match {source_work_id}")


def _check_vendor(conn, work_id, vendor_embedding) -> None:
    """Informational, like PO validation: does this vendor's name embed
    close to a vendor we've already seen elsewhere in `invoice`? Catches
    "Ashima Anand" vs "Ashima Anand Pvt Ltd" as the same vendor without
    requiring an exact string match. Logged, doesn't block extraction."""
    match = find_similar_vendor(conn, vendor_embedding, exclude_work_id=work_id)
    if match is not None and vendor_is_match(match["distance"]):
        append_log(
            conn, work_id, "VENDOR_MATCHED",
            detail=f"matches vendor on work_id {match['invoice_work_id']} ({match['vendor_name']!r}, distance={match['distance']:.4f})",
        )
        print(f"[{work_id}] vendor matches {match['vendor_name']!r} (work_id {match['invoice_work_id']})")
    else:
        append_log(conn, work_id, "VENDOR_NEW", detail="no sufficiently similar vendor found in invoice")
        print(f"[{work_id}] vendor not matched to any known vendor")


def process_document(conn, work_id, document_link):
    if not claim_work_item(conn, work_id):
        # Another poller already picked this one up.
        return

    print(f"[{work_id}] extraction started -> {document_link}")

    try:
        pdf_bytes = fetch_document_bytes(document_link)
        invoice_data = pdf_bytes_to_structured_json(pdf_bytes)

        # Raw output always lands here first -- it's both the audit trail
        # and the reference data duplicate/PO checks are run against.
        insert_invoice_source_and_line_items(conn, work_id, invoice_data)

        if _check_duplicate(conn, work_id, invoice_data):
            return

        _check_po(conn, work_id, invoice_data)

        # Computed once and reused for both the similarity lookup and the
        # final insert below, rather than embedding the vendor name twice.
        vendor_embedding = embed_text(invoice_data.customer_name)
        _check_vendor(conn, work_id, vendor_embedding)

        insert_invoice_and_line_items(conn, work_id, invoice_data, vendor_embedding)
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
