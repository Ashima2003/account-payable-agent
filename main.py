import argparse
import threading

from logging_config import configure_logging
from workers import (
    dashboard_worker,
    email_ingestion_worker,
    helpdesk_worker,
    invoice_extraction_worker,
    outbox_relay_worker,
)

_WORKERS = {
    "email-ingestion": email_ingestion_worker.run,
    "invoice-extraction": invoice_extraction_worker.run,
    "helpdesk": helpdesk_worker.run,
    "outbox-relay": outbox_relay_worker.run,
    # Last on purpose: "all" runs every worker but the last one on a
    # background thread and the last one on the main thread (see below) --
    # uvicorn installs SIGINT/SIGTERM handlers that only work from the
    # main thread of the main interpreter, so the dashboard has to be it.
    "dashboard": dashboard_worker.run,
}


def main():
    parser = argparse.ArgumentParser(description="Account payable agent backend")
    parser.add_argument(
        "worker",
        choices=[*_WORKERS.keys(), "all"],
        help="Which polling worker to run",
    )
    args = parser.parse_args()

    configure_logging()

    if args.worker != "all":
        _WORKERS[args.worker]()
        return

    # Run everything but the last one on background threads, and the last
    # one on the main thread so the process has something blocking to keep
    # it alive (and Ctrl-C/signals land where you'd expect).
    names = list(_WORKERS.keys())
    for name in names[:-1]:
        threading.Thread(target=_WORKERS[name], daemon=True).start()
    _WORKERS[names[-1]]()


if __name__ == "__main__":
    main()
