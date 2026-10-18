"""Tests for scripts/load_students.py. No AWS: only the item building and the table check are tested."""

from scripts.load_students import KEY, TABLE_NAME, ensure_table, student_items


def test_one_item_per_student_with_the_key():
    items = student_items()
    assert [item[KEY] for item in items] == ["s001", "s002", "s003"]
    assert items[0]["terms"][0]["courses"][0] == {"course": "ITC 6105", "grade": "A"}


def test_existing_table_is_not_created_again():
    class FakeDynamo:
        created = False

        def list_tables(self):
            return {"TableNames": [TABLE_NAME]}

        def create_table(self, **kwargs):
            self.created = True

    client = FakeDynamo()
    ensure_table(client)
    assert client.created is False
