import os

import certifi
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.environ["EMAIL"]
APP_PASSWORD = os.environ["APP_PASSWORD"]

DB_URL = os.environ["COCKROACHDB_CONNECTION"]
# The connection string uses sslmode=verify-full, which needs a root CA
# bundle to validate the server certificate against. Point it at certifi's
# bundle rather than relying on a system cert path that may not exist
# (e.g. libpq's default ~/.postgresql/root.crt).
if "sslrootcert=" not in DB_URL:
    _separator = "&" if "?" in DB_URL else "?"
    DB_URL = f"{DB_URL}{_separator}sslrootcert={certifi.where()}"

AWS_REGION = os.environ["AWS_REGION"]
AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_S3_BUCKET = os.environ["AWS_S3_BUCKET"]

LLM_MODEL = os.environ["LLM_MODEL"]
# Optional (not os.environ[...]) -- callers that need it check for None
# themselves and raise a friendlier, call-site-specific error message.
LLM_API_KEY = os.environ.get("LLM_API_KEY")

# Optional and unset until the queues are actually created -- everything
# else in the app has to keep working without them (the outbox table
# fills up either way; only the relay/consumer workers need these set).
SQS_INVOICE_QUEUE_URL = os.environ.get("SQS_INVOICE_QUEUE_URL")
SQS_HELPDESK_QUEUE_URL = os.environ.get("SQS_HELPDESK_QUEUE_URL")
SQS_OTHER_QUEUE_URL = os.environ.get("SQS_OTHER_QUEUE_URL")

# Dedicated read-only SQL role (SELECT-only grants -- see
# invoice-helpdesk-workflow-schema.sql) used exclusively by the CockroachDB
# MCP server so LLM-generated SQL, driven by untrusted inbound email text,
# can never write to the database.
CRDB_READONLY_URL = os.environ.get("COCKROACHDB_READONLY_CONNECTION")
if CRDB_READONLY_URL and "sslrootcert=" not in CRDB_READONLY_URL:
    _separator = "&" if "?" in CRDB_READONLY_URL else "?"
    CRDB_READONLY_URL = f"{CRDB_READONLY_URL}{_separator}sslrootcert={certifi.where()}"

# HTTP Basic Auth in front of the dashboard (api/app.py) -- it shows
# vendor names, invoice amounts, and email content, so it isn't left open
# on the internet just because the EC2 security group has to allow the
# port in. Optional here (only the dashboard worker needs it) so the
# other workers keep working without it set.
DASHBOARD_USERNAME = os.environ.get("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD")
