import io
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
import config  # noqa: E402

REGION = "eu-north-1"
INSTANCE_NAME = "ap-agent-worker"
S3_DEPLOY_KEY = "deploy/app.tar.gz"

_EXCLUDE_DIRS = {".git", ".venv", "__pycache__", "deploy"}


def build_tarball() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in REPO_ROOT.rglob("*"):
            if path.is_dir():
                continue
            rel = path.relative_to(REPO_ROOT)
            if rel.parts[0] in _EXCLUDE_DIRS or path.suffix == ".pyc":
                continue
            tar.add(path, arcname=str(rel))
    return buf.getvalue()
