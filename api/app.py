import base64
import logging
import secrets
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import config
from db.dashboard_queries import (
    fetch_email_volume_trend,
    fetch_emails_page,
    fetch_metrics,
    fetch_recent_emails,
)
from db.repository import get_connection

log = logging.getLogger("ap_agent.dashboard")

app = FastAPI(title="Account Payable Agent Dashboard")

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "dashboard" / "dist"


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Applied ahead of routing (not per-endpoint Depends), so it covers
    the static frontend mount too -- the dashboard shows vendor names,
    invoice amounts, and email content, so the page itself, not just the
    /api/* calls it makes, needs to prompt for credentials before
    revealing anything. A GET with no/invalid credentials gets a 401 with
    WWW-Authenticate, which is what makes the browser show its native
    login prompt on first visit."""

    async def dispatch(self, request: Request, call_next):
        if not config.DASHBOARD_PASSWORD:
            return Response(
                "DASHBOARD_PASSWORD is not set -- refusing to serve without auth configured.",
                status_code=503,
            )

        auth_header = request.headers.get("Authorization", "")
        username, password = "", ""
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[len("Basic "):]).decode("utf-8")
                username, _, password = decoded.partition(":")
            except Exception:
                pass

        # constant-time comparisons -- a naive `==` would let a timing
        # attack narrow down the password one byte at a time.
        valid = secrets.compare_digest(username, config.DASHBOARD_USERNAME) and secrets.compare_digest(
            password, config.DASHBOARD_PASSWORD
        )
        if not valid:
            return Response(
                "Unauthorized", status_code=401, headers={"WWW-Authenticate": 'Basic realm="dashboard"'}
            )

        return await call_next(request)


app.add_middleware(BasicAuthMiddleware)


@app.get("/api/metrics")
def get_metrics():
    with get_connection() as conn:
        return fetch_metrics(conn)


@app.get("/api/trend")
def get_trend(days: int = Query(default=14, ge=1, le=90)):
    with get_connection() as conn:
        return fetch_email_volume_trend(conn, days=days)


@app.get("/api/emails/recent")
def get_recent_emails(limit: int = Query(default=5, ge=1, le=50)):
    with get_connection() as conn:
        return fetch_recent_emails(conn, limit=limit)


@app.get("/api/emails")
def get_emails_page(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
    with get_connection() as conn:
        return fetch_emails_page(conn, page=page, page_size=page_size)


# Serves the built React app -- `npm run build` locally produces
# dashboard/dist/, shipped as part of the deploy tarball rather than
# built on the server (the EC2 instance never installs Node). html=True
# serves index.html at "/", which is all a single-page dashboard needs.
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
else:
    log.warning("dashboard/dist not found -- frontend will not be served, only /api/*")
