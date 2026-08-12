import json
import traceback

from clients.sqs_client import delete_message, receive_messages
from services.helpdesk_query_service import answer_and_reply

QUEUE_NAME = "helpdesk"


def run():
    print("Listening on the helpdesk SQS queue...")
    while True:
        try:
            messages = receive_messages(QUEUE_NAME)
        except Exception:
            traceback.print_exc()
            continue

        for msg in messages:
            try:
                body = json.loads(msg["Body"])
                answer_and_reply(body["work_id"])
                delete_message(QUEUE_NAME, msg["ReceiptHandle"])
            except Exception:
                traceback.print_exc()


if __name__ == "__main__":
    run()
