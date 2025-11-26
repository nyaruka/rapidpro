from django.conf import settings


def dynamo_scan_all(table) -> list:
    """
    Scans all items in the given DynamoDB table and returns them as a list.
    """

    assert settings.TESTING and table.name.startswith("Test"), "only for use in tests"

    last_key = None
    items = []

    while True:
        kwargs = dict(Limit=100)
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key

        response = table.scan(**kwargs)

        for item in response.get("Items", []):
            items.append(item)

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break

    # sort by PK, SK for easier comparison in tests
    return list(sorted(items, key=lambda i: (i["PK"], i["SK"])))


def dynamo_truncate(table) -> int:
    """
    Deletes all items from the given DynamoDB table.
    """

    assert settings.TESTING and table.name.startswith("Test"), "only for use in tests"

    num_deleted = 0
    last_key = None

    while True:
        kwargs = dict(ProjectionExpression="PK, SK", Limit=100)
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key

        response = table.scan(**kwargs)

        with table.batch_writer() as batch:
            for item in response.get("Items", []):
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
                num_deleted += 1

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break

    return num_deleted
