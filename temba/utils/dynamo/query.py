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


def merged_page_query(table, pks: list, *, forward=True, limit=50, start_sk=None) -> tuple[list, str | None]:
    """
    Performs a paginated query across multiple partition keys merging the results into a single page. Returns the page
    of results and the last sort key for the next page.
    """
    merged = []

    for pk in pks:
        kwargs = dict(
            Select="ALL_ATTRIBUTES",
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": pk},
            ScanIndexForward=forward,
            Limit=limit + 1,  # +1 to check if there is a next page
        )
        if start_sk:
            kwargs["ExclusiveStartKey"] = {"PK": pk, "SK": start_sk}

        response = table.query(**kwargs)

        merged.extend(response["Items"])

    merged.sort(key=lambda x: x["SK"], reverse=not forward)

    has_next_page = len(merged) > limit

    page = merged[:limit]
    resume_sk = page[-1]["SK"] if page and has_next_page else None

    return page, resume_sk
