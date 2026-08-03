import re
from typing import Optional

# Matches common ways people reference a PO number in free text: "PO 12345",
# "PO# 12345", "PO Number: 12345", "P.O. No 12345", "Purchase Order 12345".
# Regex-based rather than LLM-based (unlike ocr.py's PDF extraction) --
# this is plain text with a fairly narrow set of common phrasings, so a
# pattern match is enough without the cost/latency of a model call on
# every incoming email.
_PO_NUMBER_RE = re.compile(
    # capture group requires at least one digit, so "PO Box 123" doesn't
    # false-positive on "Box" the way a bare [A-Za-z0-9-]+ would.
    r"\b(?:purchase\s*order|p\.?\s?o\.?)\s*(?:number|no\.?|num|#)?\s*[:\-]?\s*([A-Za-z0-9\-]*\d[A-Za-z0-9\-]*)",
    re.IGNORECASE,
)


def extract_po_number(subject: str, body: str) -> Optional[str]:
    """Best-effort PO number extraction, checked in subject then body."""
    for text in (subject, body):
        match = _PO_NUMBER_RE.search(text or "")
        if match:
            return match.group(1)
    return None
