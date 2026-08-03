import json

import boto3

import config

_sqs = boto3.client(
    "sqs",
    region_name=config.AWS_REGION,
    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
)

_QUEUE_URLS = {
    "invoice": config.SQS_INVOICE_QUEUE_URL,
    "helpdesk": config.SQS_HELPDESK_QUEUE_URL,
    "other": config.SQS_OTHER_QUEUE_URL,
}


def _queue_url(queue_name: str) -> str:
    url = _QUEUE_URLS.get(queue_name)
    if not url:
        raise RuntimeError(
            f"No SQS queue URL configured for queue_name={queue_name!r} -- "
            f"set the corresponding SQS_*_QUEUE_URL env var."
        )
    return url


def publish_message(queue_name: str, payload: dict) -> None:
    _sqs.send_message(QueueUrl=_queue_url(queue_name), MessageBody=json.dumps(payload))


def receive_messages(queue_name: str, max_messages: int = 10, wait_time_seconds: int = 20):
    response = _sqs.receive_message(
        QueueUrl=_queue_url(queue_name),
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=wait_time_seconds,
    )
    return response.get("Messages", [])


def delete_message(queue_name: str, receipt_handle: str) -> None:
    _sqs.delete_message(QueueUrl=_queue_url(queue_name), ReceiptHandle=receipt_handle)
