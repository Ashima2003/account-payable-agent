import argparse
import threading

from workers import email_ingestion_worker, invoice_extraction_worker


def main():
    parser = argparse.ArgumentParser(description="Account payable agent backend")
    parser.add_argument(
        "worker",
        choices=["email-ingestion", "invoice-extraction", "all"],
        help="Which polling worker to run",
    )
    args = parser.parse_args()

    if args.worker == "email-ingestion":
        email_ingestion_worker.run()
    elif args.worker == "invoice-extraction":
        invoice_extraction_worker.run()
    else:  # all
        threading.Thread(target=email_ingestion_worker.run, daemon=True).start()
        invoice_extraction_worker.run()


if __name__ == "__main__":
    main()
