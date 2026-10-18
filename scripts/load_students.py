"""Creates the DynamoDB students table (if missing) and loads data/students.json into it (phase 6.2).

Usage:
    source env.sh
    python -m scripts.load_students

Safe to run again: an existing table is reused and each student record is overwritten with the
current file contents. On-demand billing, so an idle table costs nothing beyond storage.
"""

import json
import logging
from pathlib import Path

import boto3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STUDENTS_PATH = PROJECT_ROOT / "data" / "students.json"
TABLE_NAME = "course-advisor-students"
KEY = "student_id"

log = logging.getLogger(__name__)


def student_items(path: Path = STUDENTS_PATH) -> list[dict]:
    """One DynamoDB item per student, keyed by student_id."""
    students = json.loads(path.read_text(encoding="utf-8"))["students"]
    return [students[student_id] for student_id in sorted(students)]


def ensure_table(client) -> None:
    existing = client.list_tables()["TableNames"]
    if TABLE_NAME in existing:
        log.info("Table %s already exists, reusing it.", TABLE_NAME)
        return
    log.info("Creating table %s...", TABLE_NAME)
    client.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": KEY, "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": KEY, "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    client.get_waiter("table_exists").wait(TableName=TABLE_NAME)
    log.info("Table is active.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ensure_table(boto3.client("dynamodb"))
    table = boto3.resource("dynamodb").Table(TABLE_NAME)
    items = student_items()
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
    log.info("Loaded %d students: %s", len(items), ", ".join(item[KEY] for item in items))


if __name__ == "__main__":
    main()
