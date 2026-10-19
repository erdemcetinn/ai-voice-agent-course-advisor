"""Where the tools read the catalog and the search index from.

Locally the files are in data/. On Lambda the DATA_BUCKET environment variable names the S3
bucket: each file is downloaded to /tmp once per container and reused while the container stays
warm, so only a cold start pays for the download.
"""

import json
import os
from functools import lru_cache
from pathlib import Path

import boto3
import numpy as np

LOCAL_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LAMBDA_TMP_DIR = Path("/tmp")
DATA_BUCKET_ENV = "DATA_BUCKET"


def data_file(name: str) -> Path:
    """Local path of a data file, downloading it from S3 first when DATA_BUCKET is set."""
    bucket = os.environ.get(DATA_BUCKET_ENV)
    if not bucket:
        return LOCAL_DATA_DIR / name
    target = LAMBDA_TMP_DIR / name
    if not target.exists():
        boto3.client("s3").download_file(bucket, name, str(target))
    return target


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    return json.loads(data_file("catalog.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_index() -> tuple[np.ndarray, list[dict]]:
    index_path = data_file("index.npy")
    if not index_path.exists():
        raise FileNotFoundError(f"{index_path.name} is missing. Run: python -m scripts.build_index")
    return np.load(index_path), json.loads(data_file("chunks.json").read_text(encoding="utf-8"))
