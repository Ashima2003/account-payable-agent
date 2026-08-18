# Account Payable Agent

An accounts-payable automation agent that watches an email inbox, extracts and
validates invoices sent as PDF attachments, and answers follow-up "what's the
status of my invoice" questions by having an LLM query the database directly
&mdash; while only ever answering the person who actually submitted that
invoice in the first place.

Built on **CockroachDB** (relational storage, vector search for fuzzy
vendor/line-item matching, a transactional outbox for reliable queuing) and
**AWS** (EC2, S3, SQS, IAM, Systems Manager).

## What it does

1. **Invoice ingestion** &mdash; an email with a PDF attachment arrives, gets
   OCR-extracted into structured data by an LLM, checked for duplicates,
   checked against any referenced PO, matched to a known vendor by name
   similarity (via CockroachDB vector search, so "Ashima Anand" and "Ashima
   Anand Pvt Ltd" match), and stored. The sender gets an automatic
   confirmation email once it's done.
2. **Helpdesk queries** &mdash; if the same sender later emails back
   referencing that invoice, an LLM with a live, read-only SQL tool (via
   [MCP](https://modelcontextprotocol.io)) looks up the real data and writes
   a real answer. If anyone *other* than the original sender references that
   invoice's work ID (forwarded, guessed, leaked), the query is rejected and
   logged instead of answered.
3. **Dashboard** &mdash; a React app showing live metrics, a trend chart, and
   an Activity Log where every email's entire processing history (every DB
   write, every LLM call, every status change) can be inspected as a single
   timeline.

## Architecture

```
Email (IMAP poll)
  -> email_ingestion_worker  --classifies--> INVOICE | HELPDESK | other
       -> queue_outbox (transactional outbox, same DB txn as the write)
            -> outbox_relay_worker -> SQS (invoice / helpdesk / other queues)

invoice_extraction_worker (consumes "invoice" SQS queue)
  -> OCR extraction (Gemini) -> duplicate/PO/vendor validation -> invoice + line_item
  -> status notification email back to sender

helpdesk_worker (consumes "helpdesk" SQS queue)
  -> sender-identity check (must match the invoice's original sender)
  -> Gemini + MCP tool call against a read-only CockroachDB role
  -> reply email back to sender

dashboard_worker -> FastAPI + React, reads the same CockroachDB tables
```

All five workers run inside one process (`main.py all`), each on its own
thread, and in production run as a single `systemd` service on one EC2
instance.

### Backend layers (`db/` / `clients/` / `services/` / `workers/`)

- **`db/`** &mdash; all SQL. `repository.py` is the write-path layer the
  workers use; `dashboard_queries.py` is read-only queries for the dashboard.
- **`clients/`** &mdash; thin wrappers around external systems: Gmail (IMAP +
  SMTP), S3, SQS, the OCR/embeddings LLM calls, and the CockroachDB MCP
  session.
- **`services/`** &mdash; business logic: email classification and
  ingestion, invoice extraction, helpdesk query answering, status
  notifications.
- **`workers/`** &mdash; the long-running polling loops that tie the above
  together, plus the dashboard's web server.
- **`api/`** &mdash; the FastAPI app the dashboard worker serves.
- **`dashboard/`** &mdash; the React/TypeScript/Tailwind frontend, built
  separately and served as static files by `api/app.py`.
- **`deploy/`** &mdash; scripts to provision and redeploy the EC2 instance.

## Tech stack

- **Database:** CockroachDB (Postgres wire protocol, `VECTOR` columns +
  indexes for fuzzy matching, transactional outbox pattern)
- **Backend:** Python, FastAPI, psycopg2, boto3
- **LLM:** Google Gemini (OCR extraction, embeddings, and the helpdesk
  assistant via MCP tool-calling)
- **AWS:** EC2, S3, SQS, IAM, Systems Manager
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Recharts, React Router

## Prerequisites

- Python 3.12+
- Node.js 18+ and npm (for the dashboard frontend)
- [`uv`](https://docs.astral.sh/uv/) (recommended) or plain `pip`
- A CockroachDB cluster ([CockroachDB Cloud](https://cockroachlabs.cloud/) free tier works)
- An AWS account with permissions to create an SQS queue, an S3 bucket, and
  (for the read-only DB role setup) `psql`
- A Gmail account with an [App Password](https://myaccount.google.com/apppasswords) generated (IMAP + SMTP)
- A Gemini API key ([Google AI Studio](https://aistudio.google.com/apikey))

## Setup

### 1. Clone and install Python dependencies

```bash
git clone https://github.com/Ashima2003/account-payable-agent.git
cd account-payable-agent
uv venv --python 3.12 .venv
uv pip install -r requirements.txt --python .venv/bin/python3
source .venv/bin/activate
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```bash
# Gmail (IMAP polling + SMTP replies)
EMAIL=your-inbox@gmail.com
APP_PASSWORD=your-16-char-app-password

# CockroachDB
COCKROACHDB_CONNECTION=postgresql://user:pass@host:26257/defaultdb?sslmode=verify-full

# AWS
AWS_REGION=eu-north-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET=your-bucket-name

# LLM
LLM_MODEL=gemini-3.1-flash-lite
LLM_API_KEY=...

# SQS queue URLs (create these three queues first -- see step 4)
SQS_INVOICE_QUEUE_URL=https://sqs.<region>.amazonaws.com/<account-id>/invoice
SQS_HELPDESK_QUEUE_URL=https://sqs.<region>.amazonaws.com/<account-id>/helpdesk
SQS_OTHER_QUEUE_URL=https://sqs.<region>.amazonaws.com/<account-id>/other

# Dedicated read-only DB role for the helpdesk MCP tool -- see step 5
COCKROACHDB_READONLY_CONNECTION=postgresql://ap_helpdesk_readonly:pass@host:26257/defaultdb?sslmode=verify-full

# Dashboard login (HTTP Basic Auth)
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=choose-a-strong-password
```

### 3. Apply the database schema

```bash
psql "$COCKROACHDB_CONNECTION" -c "SET CLUSTER SETTING feature.vector_index.enabled = true;"
psql "$COCKROACHDB_CONNECTION" -f invoice-helpdesk-workflow-schema.sql
```

### 4. Create the SQS queues

Create three standard SQS queues (`invoice`, `helpdesk`, `other` &mdash; names
are up to you) in the AWS console or via `aws sqs create-queue`, and put
their URLs in `.env` as above. The IAM user/role your `AWS_ACCESS_KEY_ID`
belongs to needs `sqs:SendMessage`, `sqs:ReceiveMessage`, and
`sqs:DeleteMessage` on all three.

### 5. Create the read-only DB role

The helpdesk assistant queries the database through an MCP tool restricted
to a dedicated SQL role with `SELECT`-only grants, so LLM-generated SQL can
never write to the database:

```sql
CREATE USER ap_helpdesk_readonly WITH PASSWORD '...';
GRANT SELECT ON email, email_scan, work_item, helpdesk, invoice, line_item,
  invoice_source, line_item_source, work_execution, work_execution_log
  TO ap_helpdesk_readonly;
```

Put that role's connection string in `.env` as
`COCKROACHDB_READONLY_CONNECTION`. This also requires
[`uv`](https://docs.astral.sh/uv/) to be installed on whatever machine runs
the helpdesk worker &mdash; it launches the CockroachDB MCP server via `uvx`.

### 6. Build the dashboard frontend

```bash
cd dashboard
npm install
npm run build
cd ..
```

This produces `dashboard/dist/`, which `api/app.py` serves as static files.

## Running locally

Run everything (all four background workers + the dashboard) in one process:

```bash
python3 main.py all
```

Or run a single worker:

```bash
python3 main.py email-ingestion    # poll the inbox
python3 main.py invoice-extraction # consume the invoice SQS queue
python3 main.py helpdesk           # consume the helpdesk SQS queue
python3 main.py outbox-relay       # relay the outbox table to SQS
python3 main.py dashboard          # serve the dashboard on :8000
```

The dashboard is then at `http://localhost:8000` (Basic Auth login using the
`DASHBOARD_USERNAME`/`DASHBOARD_PASSWORD` from `.env`).

For frontend development with hot reload, run `npm run dev` inside
`dashboard/` instead (proxies `/api/*` to `:8000`, so also run
`python3 main.py dashboard` alongside it).

## Deployment

`deploy/provision_ec2.py` launches a single EC2 instance running all workers
as a `systemd` service; `deploy/redeploy.py` pushes code changes to an
already-running instance; `deploy/logs.py` tails its logs. All three use
[AWS Systems Manager](https://docs.aws.amazon.com/systems-manager/) instead
of SSH. See the docstring at the top of each script for details.

## Security notes

- The helpdesk assistant's database access goes through a **dedicated
  read-only SQL role**, not the app's main credentials &mdash; defense in
  depth in case anything upstream misbehaves.
- A helpdesk query is only answered if the requester's email address matches
  the address that originally submitted the referenced invoice
  (`services/email_classification.py:same_sender`); a mismatch is logged as
  `HELPDESK_REJECTED`, visible in the dashboard's Activity Logs, and never
  reaches the LLM.
- The dashboard is behind HTTP Basic Auth, enforced at the middleware level
  so it covers the frontend page itself, not just the API calls it makes.

## License

[MIT](LICENSE)
