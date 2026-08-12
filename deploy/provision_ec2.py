"""
One-time provisioning script: launches a single always-on EC2 instance that
runs `python3 main.py all` (all four workers) as a systemd service.

Run this with YOUR OWN admin-capable AWS credentials, not the app's
ap-agent-worker service credentials in .env -- ap-agent-worker is
deliberately scoped to just SQS/S3/DB and has no EC2/IAM permissions, and
widening it just for a one-time deploy would be a permanent privilege
increase for no ongoing benefit.

Usage:
    1. Install the AWS CLI and run `aws configure` with an admin IAM
       user's access key (Console -> IAM -> Users -> your user -> Security
       credentials -> Create access key). Do NOT use root account keys.
    2. cd account-payable-agent
    3. source .venv/bin/activate   (created earlier; has boto3 already)
    4. python3 deploy/provision_ec2.py

What it does:
    - Packages the current working tree (code + .env) into a tarball and
      uploads it to the existing AWS_S3_BUCKET under deploy/, via a
      short-lived presigned URL (not made public) so the new instance can
      fetch it with a single `curl` and no AWS credentials of its own.
    - Creates an IAM role + instance profile for the EC2 instance with
      only AmazonSSMManagedInstanceCore attached (so you can open a
      shell on it later via SSM Session Manager with no SSH key/open
      port needed) -- no S3/SQS permissions on the instance role itself,
      since the app authenticates with the ap-agent-worker keys baked
      into the deployed .env, same as it does locally.
    - Creates a security group with the account's default outbound-only
      rules and NO inbound rules at all -- nothing needs to reach this
      box from the internet; SSM connects outbound from the instance.
    - Launches one t4g.small in eu-north-1's default VPC running Amazon
      Linux 2023, with user-data that installs uv, sets up the venv,
      writes a systemd unit (Restart=always, so it survives crashes and
      reboots), and starts it.
    - Adds a 1-day expiration lifecycle rule on deploy/ in S3, so the
      tarball (which contains your .env secrets) doesn't linger in the
      bucket indefinitely.
"""

import json
import time

import boto3

from _common import INSTANCE_NAME, REGION, S3_DEPLOY_KEY, build_tarball, config

INSTANCE_TYPE = "t4g.small"
ROLE_NAME = "ap-agent-ec2-role"
INSTANCE_PROFILE_NAME = "ap-agent-ec2-profile"
SECURITY_GROUP_NAME = "ap-agent-sg"


def ensure_role(iam):
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }
    try:
        iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="EC2 role for the account-payable-agent worker instance",
        )
        print(f"created IAM role {ROLE_NAME}")
    except iam.exceptions.EntityAlreadyExistsException:
        print(f"IAM role {ROLE_NAME} already exists, reusing")

    iam.attach_role_policy(
        RoleName=ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    )

    try:
        iam.create_instance_profile(InstanceProfileName=INSTANCE_PROFILE_NAME)
        iam.add_role_to_instance_profile(
            InstanceProfileName=INSTANCE_PROFILE_NAME, RoleName=ROLE_NAME
        )
        print(f"created instance profile {INSTANCE_PROFILE_NAME}")
        print("waiting 10s for IAM propagation...")
        time.sleep(10)
    except iam.exceptions.EntityAlreadyExistsException:
        print(f"instance profile {INSTANCE_PROFILE_NAME} already exists, reusing")


def ensure_security_group(ec2, vpc_id: str) -> str:
    existing = ec2.describe_security_groups(
        Filters=[
            {"Name": "group-name", "Values": [SECURITY_GROUP_NAME]},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ]
    )["SecurityGroups"]
    if existing:
        sg_id = existing[0]["GroupId"]
        print(f"security group {SECURITY_GROUP_NAME} already exists, reusing {sg_id}")
        return sg_id

    sg_id = ec2.create_security_group(
        GroupName=SECURITY_GROUP_NAME,
        Description="ap-agent-worker: no inbound rules, default outbound only",
        VpcId=vpc_id,
    )["GroupId"]
    print(f"created security group {sg_id} (no inbound rules)")
    return sg_id


def user_data_script(presigned_url: str) -> str:
    return f"""#!/bin/bash
set -euxo pipefail
exec > /var/log/ap-agent-bootstrap.log 2>&1

dnf install -y git tar gzip

mkdir -p /opt/account-payable-agent
curl -sL "{presigned_url}" -o /tmp/app.tar.gz
tar -xzf /tmp/app.tar.gz -C /opt/account-payable-agent

curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

cd /opt/account-payable-agent
/usr/local/bin/uv venv --python 3.12 .venv
/usr/local/bin/uv pip install -r requirements.txt --python .venv/bin/python3

cat > /etc/systemd/system/ap-agent.service <<'UNIT'
[Unit]
Description=Account Payable Agent Workers
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/account-payable-agent
ExecStart=/opt/account-payable-agent/.venv/bin/python3 -u main.py all
Restart=always
RestartSec=5
Environment="PATH=/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin"
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable ap-agent
systemctl start ap-agent
"""


def main():
    session = boto3.Session(profile_name="ap-agent-admin", region_name=REGION)
    iam = session.client("iam")
    ec2 = session.client("ec2")
    ssm = session.client("ssm")
    s3 = session.client("s3")

    print("1/6 packaging and uploading app tarball to S3...")
    tarball = build_tarball()
    key = S3_DEPLOY_KEY
    s3.put_object(Bucket=config.AWS_S3_BUCKET, Key=key, Body=tarball, ServerSideEncryption="AES256")
    try:
        s3.put_bucket_lifecycle_configuration(
            Bucket=config.AWS_S3_BUCKET,
            LifecycleConfiguration={
                "Rules": [{
                    "ID": "expire-deploy-artifacts",
                    "Filter": {"Prefix": "deploy/"},
                    "Status": "Enabled",
                    "Expiration": {"Days": 1},
                }]
            },
        )
    except Exception as e:
        print(f"warning: couldn't set lifecycle rule ({e}) -- delete s3://{config.AWS_S3_BUCKET}/{key} manually after confirming the instance booted")
    presigned_url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": config.AWS_S3_BUCKET, "Key": key}, ExpiresIn=3600
    )

    print("2/6 ensuring IAM role + instance profile...")
    ensure_role(iam)

    print("3/6 finding default VPC/subnet...")
    vpc_id = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"][0]["VpcId"]
    subnet_id = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"][0]["SubnetId"]
    print(f"   vpc={vpc_id} subnet={subnet_id}")

    print("4/6 ensuring security group (no inbound rules)...")
    sg_id = ensure_security_group(ec2, vpc_id)

    print("5/6 finding latest Amazon Linux 2023 arm64 AMI...")
    ami_id = ssm.get_parameter(Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64")["Parameter"]["Value"]
    print(f"   ami={ami_id}")

    print("6/6 launching instance...")
    resp = ec2.run_instances(
        ImageId=ami_id,
        InstanceType=INSTANCE_TYPE,
        MinCount=1,
        MaxCount=1,
        SubnetId=subnet_id,
        SecurityGroupIds=[sg_id],
        IamInstanceProfile={"Name": INSTANCE_PROFILE_NAME},
        UserData=user_data_script(presigned_url),
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": INSTANCE_NAME}],
        }],
    )
    instance_id = resp["Instances"][0]["InstanceId"]
    print(f"\nlaunched {instance_id} -- boot + dependency install takes ~2-3 minutes.")
    print(f"check status once it's registered with SSM:")
    print(f"  aws ssm start-session --target {instance_id} --region {REGION}")
    print(f"  (then, on the instance)  sudo systemctl status ap-agent")
    print(f"  (then, on the instance)  sudo journalctl -u ap-agent -f")


if __name__ == "__main__":
    main()
