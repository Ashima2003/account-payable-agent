"""
Tails the live worker logs from the EC2 instance over SSM -- no SSH, no
open ports. Since AWS-RunShellScript is one-shot rather than a real
stream, this just polls journalctl in a loop and prints only new lines.

Usage:
    python3 deploy/logs.py             # last 2 minutes, then follow
    python3 deploy/logs.py --since 1h  # different initial window
"""

import argparse
import time

import boto3

from _common import INSTANCE_NAME, REGION

_POLL_SECONDS = 5


def find_instance_id(ec2) -> str:
    resp = ec2.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": [INSTANCE_NAME]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    )
    instances = [i for r in resp["Reservations"] for i in r["Instances"]]
    if not instances:
        raise RuntimeError(f"No running instance tagged Name={INSTANCE_NAME} found.")
    return instances[0]["InstanceId"]


def fetch_logs(ssm, instance_id: str, since: str) -> str:
    command_id = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [f'journalctl -u ap-agent --no-pager --since "{since}"']},
    )["Command"]["CommandId"]

    for _ in range(20):
        time.sleep(1)
        invocation = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        if invocation["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
            return invocation["StandardOutputContent"]
    raise RuntimeError("timed out waiting for log fetch")


def main():
    parser = argparse.ArgumentParser(description="Tail account-payable-agent logs from EC2")
    parser.add_argument("--since", default="2 minutes ago", help="journalctl --since window for the initial fetch")
    args = parser.parse_args()

    session = boto3.Session(profile_name="ap-agent-admin", region_name=REGION)
    ec2 = session.client("ec2")
    ssm = session.client("ssm")

    instance_id = find_instance_id(ec2)
    print(f"tailing ap-agent on {instance_id} (Ctrl-C to stop)\n")

    seen_lines = set()
    since = args.since
    try:
        while True:
            output = fetch_logs(ssm, instance_id, since)
            for line in output.splitlines():
                if line not in seen_lines:
                    print(line)
                    seen_lines.add(line)
            since = "30 seconds ago"
            time.sleep(_POLL_SECONDS)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
