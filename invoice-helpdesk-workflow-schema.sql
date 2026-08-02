-- ============================================================================
-- Invoice / Helpdesk Work Item Schema — CockroachDB
-- Tables: email_scan, email, work_item, document, invoice_source, line_item_source,
--         invoice, line_item, helpdesk, work_execution, work_execution_log
-- ============================================================================
-- Design notes:
--   * work_id (and all other *_id columns) are random UUIDs — CockroachDB
--     range-shards by primary key order, so a random key spreads writes
--     evenly across the cluster instead of hotspotting one range.
--   * `work_item` is the universal parent row for every work item (invoice or
--     helpdesk). `invoice` and `helpdesk` are 1:1 "extension" tables keyed
--     on work_id — a work item is exactly one subtype, never both.
--   * helpdesk.invoice_work_id references invoice(invoice_work_id), not
--     work_item(work_id) directly. This is deliberate: it makes "a helpdesk
--     query can only point at an already-processed invoice" a referential
--     integrity guarantee instead of an application-level check, since only
--     invoice-classified work items ever get a row in `invoice`.
--   * `execution` holds the current/latest status per work_id (upserted on
--     every step). `execution_log` is the append-only history of every
--     status change. Write both in the same transaction.
-- ============================================================================

CREATE TABLE email_scan (
    scan_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    count_of_email  INT4 NOT NULL,
    scanned_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE email (
    email_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id       UUID NOT NULL REFERENCES email_scan(scan_id),
    email_from    STRING NOT NULL,
    email_subject STRING NOT NULL,
    email_content STRING NOT NULL,
    INDEX idx_email_scan (scan_id)
);

CREATE TABLE work_item (
    work_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id      UUID NOT NULL REFERENCES email(email_id),
    process_type  STRING NOT NULL CHECK (process_type IN ('INVOICE', 'HELPDESK')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- one email can spawn several work_ids (one per invoice attachment, or
    -- one per helpdesk query); this index serves both "all work_ids for an
    -- email" and "just the invoice/helpdesk ones".
    INDEX idx_work_item_email (email_id, process_type)
);

-- Strictly 1:1 with work_item, per current requirement.
CREATE TABLE document (
    work_id        UUID PRIMARY KEY REFERENCES work_item(work_id),
    document_id    UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    document_link  STRING NOT NULL   -- S3 URI
);

-- Raw extraction output, one row per invoice work item, written straight
-- from OCR before any validation. Same shape as `invoice` below, but
-- every column here is nullable -- the extraction model returns null for
-- anything it isn't confident about, and this table has to be able to
-- hold that as-is. Validation reads a work_id's row out of this table,
-- and only a row that passes validation ever gets copied into `invoice`.
CREATE TABLE invoice_source (
    invoice_work_id   UUID PRIMARY KEY REFERENCES work_item(work_id),
    invoice_number    STRING,
    invoice_date      DATE,
    vendor_name       STRING,
    total_amount      DECIMAL(18,2),
    invoice_currency  STRING(3),
    purchase_order    STRING,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Raw line items as extracted, one row per line, mirroring `line_item`
-- below. References invoice_source (not invoice) since these rows are
-- written before validation -- a work_id can have line_item_source rows
-- with no corresponding validated line_item rows yet.
CREATE TABLE line_item_source (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_work_id   UUID NOT NULL REFERENCES invoice_source(invoice_work_id),
    line_number       INT4 NOT NULL,
    description       STRING,
    quantity          DECIMAL(18,4),
    unit_price        DECIMAL(18,4),
    line_amount       DECIMAL(18,2),
    UNIQUE (invoice_work_id, line_number),
    INDEX idx_line_item_source_invoice (invoice_work_id, line_number)
);

-- Extension table: only ever populated for work_item.process_type = 'INVOICE'.
CREATE TABLE invoice (
    invoice_work_id   UUID PRIMARY KEY REFERENCES work_item(work_id),
    invoice_number    STRING NOT NULL,
    invoice_date      DATE,
    vendor_name       STRING NOT NULL,
    total_amount      DECIMAL(18,2) NOT NULL,
    invoice_currency  STRING(3) NOT NULL,
    purchase_order    STRING,   -- PO number, when the invoice references one; not every invoice has one
    -- candidate lookup for duplicate-invoice detection
    INDEX idx_invoice_dup_lookup (vendor_name, invoice_number, invoice_currency)
);

-- One row per line on the invoice. line_number preserves the original
-- order as it appeared on the document (OCR/extraction order).
CREATE TABLE line_item (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_work_id  UUID NOT NULL REFERENCES invoice(invoice_work_id),
    line_number      INT4 NOT NULL,
    description      STRING,
    quantity         DECIMAL(18,4),
    unit_price       DECIMAL(18,4),
    line_amount      DECIMAL(18,2) NOT NULL,
    UNIQUE (invoice_work_id, line_number),
    INDEX idx_line_item_invoice (invoice_work_id, line_number)
);

-- Extension table: only ever populated for work_item.process_type = 'HELPDESK'.
CREATE TABLE helpdesk (
    helpdesk_work_id  UUID PRIMARY KEY REFERENCES work_item(work_id),
    invoice_work_id   UUID NOT NULL REFERENCES invoice(invoice_work_id),
    -- reverse lookup: "every helpdesk query raised about this invoice"
    INDEX idx_helpdesk_invoice (invoice_work_id)
);

-- Current/latest state per work_id — upsert on every step.
CREATE TABLE work_execution (
    work_id     UUID PRIMARY KEY REFERENCES work_item(work_id),
    status      STRING NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- ops dashboards: "show everything currently FAILED / MANUAL_REVIEW"
    INDEX idx_execution_status (status)
);

-- Append-only step-by-step history — insert a new row after every step.
CREATE TABLE work_execution_log (
    work_id    UUID NOT NULL REFERENCES work_item(work_id),
    timestamp  TIMESTAMPTZ NOT NULL DEFAULT now(),
    log_id     UUID NOT NULL DEFAULT gen_random_uuid(),   -- tiebreaker for same-timestamp writes
    status     STRING NOT NULL,
    -- leading column (work_id, random UUID) spreads different work items
    -- across ranges; trailing (timestamp, log_id) keeps one work_id's own
    -- history physically contiguous and pre-sorted, so "get history for
    -- this work_id" is a single-range scan with no secondary index needed.
    PRIMARY KEY (work_id, timestamp, log_id)
);
