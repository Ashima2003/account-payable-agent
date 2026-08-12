"""
Pushes local code changes to the already-running EC2 instance (the one
`provision_ec2.py` launched). Run this every time you want a code change
to go live -- provision_ec2.py only runs its setup once, at first boot, so
running it again would launch a brand-new second instance rather than
update the existing one.

Usage (same admin AWS profile as provision_ec2.py):
    cd account-payable-agent
    source .venv/bin/activate
    python3 deploy/redeploy.py

What it does:
    - Packages whatever is currently on origin/main (code) plus this
      machine's local .env (secrets, deliberately gitignored so they're
      never committed) and re-uploads it to the same S3 deploy/ location.
      Merge/push to main first -- this does NOT deploy uncommitted local
      changes or other branches.
    - Finds the running instance by its Name=ap-agent-worker tag.
    - Over SSM (no SSH needed): stops the service, wipes and re-extracts
      the app directory, re-syncs dependencies (uv pip install -- cheap
      no-op if requirements.txt didn't change), and restarts the service.
    - Prints the fresh `systemctl status` so you can confirm it came back
      up clean.
"""

import time

import boto3

from _common import INSTANCE_NAME, REGION, S3_DEPLOY_KEY, build_tarball, config

_REMOTE_SCRIPT = """#!/bin/bash
set -euxo pipefail
exec > /var/log/ap-agent-redeploy.log 2>&1

systemctl stop ap-agent || true
rm -rf /opt/account-payable-agent
mkdir -p /opt/account-payable-agent
curl -sL "{presigned_url}" -o /tmp/app.tar.gz
tar -xzf /tmp/app.tar.gz -C /opt/account-payable-agent

cd /opt/account-payable-agent
/usr/local/bin/uv venv --python 3.12 .venv
/usr/local/bin/uv pip install -r requirements.txt --python .venv/bin/python3

systemctl start ap-agent
sleep 3
systemctl status ap-agent --no-pager
"""


def find_instance_id(ec2) -> str:
    resp = ec2.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": [INSTANCE_NAME]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    )
    instances = [i for r in resp["Reservations"] for i in r["Instances"]]
    if not instances:
        raise RuntimeError(
            f"No running instance tagged Name={INSTANCE_NAME} found -- "
            "has it been launched with provision_ec2.py, or was it stopped/terminated?"
        )
    return instances[0]["InstanceId"]


def run_remote(ssm, instance_id: str, script: str) -> None:
    command_id = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [script]},
    )["Command"]["CommandId"]

    for _ in range(60):
        time.sleep(3)
        invocation = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        if invocation["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
            print(f"--- status: {invocation['Status']} ---")
            print(invocation["StandardOutputContent"])
            if invocation["StandardErrorContent"]:
                print("--- stderr ---")
                print(invocation["StandardErrorContent"])
            if invocation["Status"] != "Success":
                raise RuntimeError(f"redeploy command {invocation['Status']}")
            return
    raise RuntimeError("timed out waiting for redeploy command to finish")


def main():
    session = boto3.Session(profile_name="ap-agent-admin", region_name=REGION)
    ec2 = session.client("ec2")
    ssm = session.client("ssm")
    s3 = session.client("s3")

    print("1/3 finding running instance...")
    instance_id = find_instance_id(ec2)
    print(f"   instance={instance_id}")

    print("2/3 packaging and uploading app tarball to S3...")
    tarball = build_tarball()
    s3.put_object(Bucket=config.AWS_S3_BUCKET, Key=S3_DEPLOY_KEY, Body=tarball, ServerSideEncryption="AES256")
    presigned_url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": config.AWS_S3_BUCKET, "Key": S3_DEPLOY_KEY}, ExpiresIn=3600
    )

    print("3/3 redeploying over SSM (stop -> refresh code -> reinstall deps -> start)...")
    run_remote(ssm, instance_id, _REMOTE_SCRIPT.format(presigned_url=presigned_url))
    print("\ndone.")


if __name__ == "__main__":
    main()
