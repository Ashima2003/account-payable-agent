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


def _build_dashboard_frontend() -> None:
    """dashboard/dist is gitignored (a build artifact, not source), so
    `git archive` below never includes it -- it has to be built fresh
    here and added to the tarball explicitly, the same way .env is.
    Builds from this machine's dashboard/src, not a fresh checkout of
    DEPLOY_REF, so push+merge before redeploying like normal -- same
    assumption already made for .env."""
    dashboard_dir = REPO_ROOT / "dashboard"
    if not (dashboard_dir / "node_modules").is_dir():
        subprocess.run(["npm", "install"], cwd=dashboard_dir, check=True)
    subprocess.run(["npm", "run", "build"], cwd=dashboard_dir, check=True)


def build_tarball() -> bytes:
    """What's deployed is exactly what's committed on DEPLOY_REF -- not
    local working-tree state -- so what's live is always traceable to a
    specific, reviewable commit. `git archive` only includes tracked
    files, so .env (deliberately gitignored, since it holds secrets)
    and the built dashboard/dist/ (gitignored, a build artifact) are
    appended afterward, from whatever's on this machine right now."""
    subprocess.run(["git", "-C", str(REPO_ROOT), "fetch", "origin", "main"], check=True)
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "archive", "--format=tar", DEPLOY_REF],
        check=True, capture_output=True,
    )
    buf = io.BytesIO(proc.stdout)
    with tarfile.open(fileobj=buf, mode="a") as tar:
        tar.add(REPO_ROOT / ".env", arcname=".env")

        _build_dashboard_frontend()
        dist_dir = REPO_ROOT / "dashboard" / "dist"
        for path in dist_dir.rglob("*"):
            if path.is_file():
                tar.add(path, arcname=str(path.relative_to(REPO_ROOT)))

    return gzip.compress(buf.getvalue())
