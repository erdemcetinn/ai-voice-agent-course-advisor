"""Creates the AgentCore Gateway that exposes the tools Lambda to Amazon Connect as MCP tools.

Usage:
    source env.sh
    python -m scripts.setup_gateway

Safe to run again: an existing gateway or target with the same name is reused and updated.

Connect authenticates to the gateway with a JWT from the Connect instance, so the gateway uses a
custom JWT authorizer with the instance's discovery URL, and its own ID as the allowed audience.
Connect speaks MCP protocol version 2025-03-26, which the gateway must list.
"""

import json
import logging
import time
from pathlib import Path

import boto3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_PATH = PROJECT_ROOT / "connect" / "gateway-tools.json"

ACCOUNT_ID = "452383571300"
GATEWAY_NAME = "course-advisor-gateway"
TARGET_NAME = "advisor-tools"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/course-advisor-gateway"
LAMBDA_ARN = f"arn:aws:lambda:us-east-1:{ACCOUNT_ID}:function:course-advisor-tools"
DISCOVERY_URL = "https://erdem-advisor-east.my.connect.aws/.well-known/openid-configuration"
CONNECT_MCP_VERSION = "2025-03-26"
READY_POLLS = 30
READY_POLL_SECONDS = 5

log = logging.getLogger(__name__)


def _gateway_settings(audience: list[str]) -> dict:
    return {
        "name": GATEWAY_NAME,
        "roleArn": ROLE_ARN,
        "protocolType": "MCP",
        "protocolConfiguration": {"mcp": {"supportedVersions": [CONNECT_MCP_VERSION]}},
        "authorizerType": "CUSTOM_JWT",
        "authorizerConfiguration": {"customJWTAuthorizer": {"discoveryUrl": DISCOVERY_URL, "allowedAudience": audience}},
        "description": "Course advisor tools for Amazon Connect",
    }


def _wait_until_ready(client, gateway_id: str) -> None:
    for _ in range(READY_POLLS):
        status = client.get_gateway(gatewayIdentifier=gateway_id)["status"]
        if status == "READY":
            return
        if status == "FAILED":
            raise RuntimeError(f"Gateway {gateway_id} failed to create")
        time.sleep(READY_POLL_SECONDS)
    raise TimeoutError(f"Gateway {gateway_id} not ready after {READY_POLLS * READY_POLL_SECONDS} seconds")


def _find(items: list[dict], name: str) -> dict | None:
    return next((item for item in items if item["name"] == name), None)


def ensure_gateway(client) -> str:
    """Creates the gateway if missing, then makes its own ID the allowed JWT audience."""
    existing = _find(client.list_gateways()["items"], GATEWAY_NAME)
    if existing:
        gateway_id = existing["gatewayId"]
        log.info("Gateway exists: %s", gateway_id)
    else:
        gateway_id = client.create_gateway(**_gateway_settings(["pending"]))["gatewayId"]
        log.info("Created gateway: %s", gateway_id)
    _wait_until_ready(client, gateway_id)
    client.update_gateway(gatewayIdentifier=gateway_id, **_gateway_settings([gateway_id]))
    _wait_until_ready(client, gateway_id)
    log.info("Allowed audience set to the gateway ID; MCP version %s", CONNECT_MCP_VERSION)
    return gateway_id


def ensure_target(client, gateway_id: str) -> str:
    target = {
        "name": TARGET_NAME,
        "targetConfiguration": {"mcp": {"lambda": {
            "lambdaArn": LAMBDA_ARN,
            "toolSchema": {"inlinePayload": json.loads(TOOLS_PATH.read_text(encoding="utf-8"))},
        }}},
        "credentialProviderConfigurations": [{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
    }
    existing = _find(client.list_gateway_targets(gatewayIdentifier=gateway_id)["items"], TARGET_NAME)
    if existing:
        client.update_gateway_target(gatewayIdentifier=gateway_id, targetId=existing["targetId"], **target)
        log.info("Updated target: %s", existing["targetId"])
        return existing["targetId"]
    target_id = client.create_gateway_target(gatewayIdentifier=gateway_id, **target)["targetId"]
    log.info("Created target: %s", target_id)
    return target_id


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    client = boto3.client("bedrock-agentcore-control")
    gateway_id = ensure_gateway(client)
    ensure_target(client, gateway_id)
    gateway = client.get_gateway(gatewayIdentifier=gateway_id)
    log.info("Status: %s. MCP endpoint: %s", gateway.get("status"), gateway.get("gatewayUrl"))


if __name__ == "__main__":
    main()
