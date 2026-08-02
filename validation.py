from typing import List, Optional

# Absolute tolerance for comparing extracted numbers: DB values come back as
# Decimal, OCR values as float, and OCR re-reads of the same document can
# differ in the last decimal place. Anything within a cent/thousandth is
# treated as the same value rather than a mismatch.
_NUMERIC_TOLERANCE = 0.01


def _numbers_match(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= _NUMERIC_TOLERANCE


def lines_match(source_lines: List[dict], current_line_items: List) -> bool:
    """True if `current_line_items` (fresh OCR output, ocr.LineItem
    instances) line up exactly, in order, with `source_lines` (rows from
    line_item_source for a previously-seen PO): same count, and each pair
    matching on quantity, unit_price, and line_amount."""
    if len(source_lines) != len(current_line_items):
        return False

    for source, current in zip(source_lines, current_line_items):
        if not _numbers_match(source["quantity"], current.quantity):
            return False
        if not _numbers_match(source["unit_price"], current.unit_price):
            return False
        if not _numbers_match(source["line_amount"], current.amount):
            return False

    return True


def build_duplicate_decline_reply(invoice_number: Optional[str], purchase_order: Optional[str]) -> str:
    """Draft reply text for an invoice that's already been processed.
    Not sent automatically -- stored as a work_execution_log detail for a
    human (or a future send step) to pick up."""
    reference = f"invoice {invoice_number}" if invoice_number else "this invoice"
    if purchase_order:
        reference += f" (PO {purchase_order})"

    return (
        f"Thank you for your submission. {reference} has already been received "
        "and is currently in our processing pipeline. No further action is "
        "needed on your part at this time -- if you believe this is in error, "
        "please reply with the correct invoice/PO details."
    )
