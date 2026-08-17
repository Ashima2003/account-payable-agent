import re
from email.utils import parseaddr
from typing import Optional

# work_id (and invoice_work_id, helpdesk_work_id, etc.) are standard random
# UUIDs everywhere in the schema (see invoice-helpdesk-workflow-schema.sql),
# so a reply referencing a prior invoice is expected to include one
# verbatim, e.g. in a subject line like "Re: Invoice Processed [Ref:
# 4ec2e78a-8afb-4ddb-aaed-ef432d4a60af]".
_WORK_ID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def extract_work_id(subject: str, body: str) -> Optional[str]:
    """Best-effort work_id (UUID) extraction, checked in subject then body."""
    for text in (subject, body):
        match = _WORK_ID_RE.search(text or "")
        if match:
            return match.group(0)
    return None


def same_sender(a: Optional[str], b: Optional[str]) -> bool:
    """Compares two raw From-header values by their address only, not the
    full header string -- "Ashima Anand <a@x.com>" and "a@x.com" (or a
    different display name on the same address) must count as the same
    sender, since a mail client is free to format either email
    differently across messages. Case-insensitive, since addresses are."""
    addr_a = parseaddr(a or "")[1].lower()
    addr_b = parseaddr(b or "")[1].lower()
    return bool(addr_a) and addr_a == addr_b
