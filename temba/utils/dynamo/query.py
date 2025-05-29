def merged_page_query(table, pks: list, *, forward=True, limit=50, start_sk=None) -> tuple[list, str | None]:
    """
    Performs a paginated query across multiple partition keys merging the results into a single page. Returns the page
    of results and the last sort key for the next page.
    """
    merged = []

    for pk in pks:
        kwargs = dict(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": pk},
            ScanIndexForward=forward,
            Limit=limit,
        )
        if start_sk:
            kwargs["ExclusiveStartKey"] = {"PK": pk, "SK": start_sk}

        response = table.query(**kwargs)

        merged.extend(response["Items"])

    merged.sort(key=lambda x: x["SK"], reverse=not forward)
    page = merged[:limit]
    last_sk = page[-1]["SK"] if page else None

    return page, last_sk
