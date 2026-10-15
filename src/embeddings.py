"""Turns text into a list of numbers (an embedding) with Titan Text Embeddings V2.

build_index.py (catalog chunks) and catalog_search.py (the student's question) use the same function.
Both must use the same model and settings, otherwise the numbers cannot be compared.
"""

import json

import boto3

MODEL_ID = "amazon.titan-embed-text-v2:0"
DIMENSIONS = 1024


def make_client():
    """The region comes from env.sh (AWS_REGION)."""
    return boto3.client("bedrock-runtime")


def embed_text(text: str, client) -> list[float]:
    """Returns a normalized embedding (length 1), so cosine similarity = dot product."""
    if not text.strip():
        raise ValueError("Cannot embed empty text")
    body = json.dumps({"inputText": text, "dimensions": DIMENSIONS, "normalize": True})
    response = client.invoke_model(modelId=MODEL_ID, body=body)
    embedding = json.loads(response["body"].read())["embedding"]
    if len(embedding) != DIMENSIONS:
        raise ValueError(f"Expected {DIMENSIONS} dimensions, got {len(embedding)}")
    return embedding
