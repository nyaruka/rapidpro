import itertools


def batch_get(table, keys: list[tuple]) -> list:
    """
    Performs a batch get item operation on the given table for the provided keys.
    """
    if not keys:
        return []

    items = []

    for key_batch in itertools.batched(keys, 100):
        key_attrs = [{"PK": pk, "SK": sk} for pk, sk in keys]
        response = table.meta.client.batch_get_item(RequestItems={table.name: {"Keys": key_attrs}})

        items.extend(response.get("Responses", {}).get(table.name, []))

    return items


def merged_page_query(table, pks: list, *, desc=False, limit=50, after_sk=None) -> tuple[list, str | None]:
    """
    Performs a paginated query across multiple partition keys merging the results into a single page. Returns the page
    of results and the last sort key for the next page.
    """

    # fetch this page +1 from all partitions
    merged = _merged_partition_query(table, pks, limit=limit + 1, desc=desc, after_sk=after_sk)

    has_next_after = len(merged) > limit  # if we got +1 then there's a next page

    page = merged[:limit]
    next_after_sk = page[-1]["SK"] if page and has_next_after else None

    return page, next_after_sk


def _merged_partition_query(table, pks: list, *, limit: int, desc: bool, after_sk: str | None):
    merged = []

    for pk in pks:
        kwargs = dict(
            Select="ALL_ATTRIBUTES",
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": pk},
            ScanIndexForward=not desc,
            Limit=limit,
        )
        if after_sk:
            kwargs["ExclusiveStartKey"] = {"PK": pk, "SK": after_sk}

        response = table.query(**kwargs)
        merged.extend(response["Items"])

    merged.sort(key=lambda x: x["SK"], reverse=desc)
    return merged[:limit]
