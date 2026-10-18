"""Builds dist/lambda.zip for the tools Lambda (phase 6.3).

Usage:
    python -m scripts.package_lambda

The zip holds src/ plus numpy built for Lambda's Linux runtime (the macOS wheel would not load there).
boto3 is already part of the Lambda Python runtime, so it is left out. Data files are not packaged:
the Lambda reads them from S3.
"""

import logging
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = PROJECT_ROOT / "dist" / "lambda"
ZIP_BASE = PROJECT_ROOT / "dist" / "lambda"
LAMBDA_PYTHON = "3.11"
LAMBDA_PLATFORM = "manylinux2014_x86_64"
# Newest numpy that still ships manylinux2014 wheels; the python3.11 runtime (Amazon Linux 2) needs them.
# Only np.load, @ and argsort are used, which behave the same as in the local 2.4.x.
NUMPY_REQUIREMENT = "numpy==2.2.6"

log = logging.getLogger(__name__)


def install_numpy(target: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--target", str(target),
         "--platform", LAMBDA_PLATFORM, "--implementation", "cp", "--python-version", LAMBDA_PYTHON,
         "--only-binary=:all:", NUMPY_REQUIREMENT],
        check=True,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    BUILD_DIR.mkdir(parents=True)
    install_numpy(BUILD_DIR)
    shutil.copytree(PROJECT_ROOT / "src", BUILD_DIR / "src", ignore=shutil.ignore_patterns("__pycache__"))
    archive = shutil.make_archive(str(ZIP_BASE), "zip", BUILD_DIR)
    size_mb = Path(archive).stat().st_size / 1_000_000
    log.info("Wrote %s (%.1f MB). Handler: src.lambda_handler.handler", Path(archive).relative_to(PROJECT_ROOT), size_mb)


if __name__ == "__main__":
    main()
