from typing import List, Optional

# Absolute tolerance for comparing extracted numbers: DB values come back as
# Decimal, OCR values as float, and OCR re-reads of the same document can
# differ in the last decimal place. Anything within a cent/thousandth is
# treated as the same value rather than a mismatch.
_NUMERIC_TOLERANCE = 0.01

# L2 distance thresholds for the two embedding-based fuzzy matches, chosen
# from empirical testing against real cases: "ROTI" vs "ROTY" (an OCR
# misread of the same item) measured ~0.43, vs. ~0.58 for two genuinely
# different items; "Ashima Anand" vs "Ashima Anand Pvt Ltd" (same vendor)
# measured ~0.28, vs. ~0.57 for two different vendors. 0.5 sits cleanly
# between "same" and "different" in both cases.
DESCRIPTION_DISTANCE_THRESHOLD = 0.5
VENDOR_DISTANCE_THRESHOLD = 0.5


def _numbers_match(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= _NUMERIC_TOLERANCE


def lines_match(comparison_rows: List[dict]) -> bool:
    """True if every line lines up between the two invoices being compared
    (see db.fetch_line_item_comparison, which joins them on line_number):
    same count on both sides, matching quantity/unit_price/line_amount, and
    a description-embedding distance within threshold -- so "ROTI" vs
    "ROTY" (an OCR misread of the same item) still counts as a match
    instead of requiring the description to be character-for-character
    identical.

    A row with a NULL curr_/src_ line_number means the FULL OUTER JOIN
    found a line present on only one side -- i.e. the two invoices don't
    have the same number of lines -- which is an automatic mismatch."""
    if not comparison_rows:
        return False

    for row in comparison_rows:
        if row["curr_line_number"] is None or row["src_line_number"] is None:
            return False
        if not _numbers_match(row["curr_quantity"], row["src_quantity"]):
            return False
        if not _numbers_match(row["curr_unit_price"], row["src_unit_price"]):
            return False
        if not _numbers_match(row["curr_line_amount"], row["src_line_amount"]):
            return False
        if row["description_distance"] is None or row["description_distance"] > DESCRIPTION_DISTANCE_THRESHOLD:
            return False

    return True


def vendor_is_match(distance: Optional[float]) -> bool:
    return distance is not None and distance <= VENDOR_DISTANCE_THRESHOLD


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
