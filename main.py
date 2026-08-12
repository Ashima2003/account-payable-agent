import argparse
import threading

from workers import email_ingestion_worker, invoice_extraction_worker, outbox_relay_worker

_WORKERS = {
    "email-ingestion": email_ingestion_worker.run,
    "invoice-extraction": invoice_extraction_worker.run,
    "outbox-relay": outbox_relay_worker.run,
}


def main():
    parser = argparse.ArgumentParser(description="Account payable agent backend")
    parser.add_argument(
        "worker",
        choices=[*_WORKERS.keys(), "all"],
        help="Which polling worker to run",
    )
    args = parser.parse_args()

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
