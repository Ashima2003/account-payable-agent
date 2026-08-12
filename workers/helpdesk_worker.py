import json
import logging
import traceback

from clients.sqs_client import delete_message, receive_messages
from logging_config import configure_logging
from services.helpdesk_query_service import answer_and_reply

log = logging.getLogger("ap_agent.helpdesk")

QUEUE_NAME = "helpdesk"


def run():
    log.info("listening on the helpdesk SQS queue...")
    while True:
        try:
            messages = receive_messages(QUEUE_NAME)
        except Exception:
            traceback.print_exc()
            continue

        for msg in messages:
            try:
                body = json.loads(msg["Body"])
                # answer_and_reply() opens its own trace(work_id) context,
                # so every DB/LLM/MCP operation for this item is tagged
                # automatically -- see logging_config.py.
                answer_and_reply(body["work_id"])
                delete_message(QUEUE_NAME, msg["ReceiptHandle"])
            except Exception:
                traceback.print_exc()


if __name__ == "__main__":
    configure_logging()
    run()
