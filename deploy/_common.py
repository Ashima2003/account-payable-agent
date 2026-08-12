import gzip
import io
import subprocess
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
import config  # noqa: E402

REGION = "eu-north-1"
INSTANCE_NAME = "ap-agent-worker"
S3_DEPLOY_KEY = "deploy/app.tar.gz"
DEPLOY_REF = "origin/main"


def build_tarball() -> bytes:
    """What's deployed is exactly what's committed on DEPLOY_REF -- not
    local working-tree state -- so what's live is always traceable to a
    specific, reviewable commit. `git archive` only includes tracked
    files, so .env (deliberately gitignored, since it holds secrets)
    is appended afterward, from whatever's on this machine right now."""
    subprocess.run(["git", "-C", str(REPO_ROOT), "fetch", "origin", "main"], check=True)
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "archive", "--format=tar", DEPLOY_REF],
        check=True, capture_output=True,
    )
    buf = io.BytesIO(proc.stdout)
    with tarfile.open(fileobj=buf, mode="a") as tar:
        tar.add(REPO_ROOT / ".env", arcname=".env")
    return gzip.compress(buf.getvalue())
