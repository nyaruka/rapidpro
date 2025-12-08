import base64
from datetime import date, datetime, timezone as tzone
from unittest.mock import ANY, call, patch

from temba.archives.models import Archive
from temba.tests import TembaTest
from temba.utils import json, s3


class ArchiveTest(TembaTest):
    def setUp(self):
        super().setUp()

        self.s3_calls = []

        def record_s3(model, params, **kwargs):
            self.s3_calls.append((model.name, params))

        s3.client().meta.events.register("provide-client-params.s3.*", record_s3)

    def test_iter_records(self):
        archive = self.create_archive(Archive.TYPE_MSG, "D", date(2024, 8, 14), [{"id": 1}, {"id": 2}, {"id": 3}])
        bucket, key = archive.get_storage_location()
        self.assertEqual("test-archives", bucket)
        self.assertEqual(f"{self.org.id}/message_D20240814_{archive.hash}.jsonl.gz", key)

        # can fetch records without any filtering
        records_iter = archive.iter_records()

        self.assertEqual(next(records_iter), {"id": 1})
        self.assertEqual(next(records_iter), {"id": 2})
        self.assertEqual(next(records_iter), {"id": 3})
        self.assertRaises(StopIteration, next, records_iter)

        def encode_jsonl(records):
            return b"".join([json.dumps(record).encode("utf-8") + b"\n" for record in records])

        # SelectObjectContent is a pro feature in localstack, and there's a bug in botocore that prevents using Stubber
        # (see https://github.com/boto/botocore/issues/1621), so we patch the client method directly
        with patch.object(s3.client(), "select_object_content") as mock_select_object_content:
            mock_select_object_content.return_value = {
                "ResponseMetadata": ANY,
                "Payload": [{"Records": {"Payload": encode_jsonl([{"id": 2}, {"id": 3}])}, "Stats": {}, "End": {}}],
            }

            # can filter using where dict
            records_iter = archive.iter_records(where={"id__gt": 1})

            self.assertEqual([{"id": 2}, {"id": 3}], [r for r in records_iter])

            mock_select_object_content.assert_called_once_with(
                Bucket="test-archives",
                Key=f"{self.org.id}/message_D20240814_477c143c30f72ee7a028c7c9e04992f9.jsonl.gz",
                ExpressionType="SQL",
                Expression="SELECT s.* FROM s3object s WHERE s.id > 1",
                InputSerialization={"CompressionType": "GZIP", "JSON": {"Type": "LINES"}},
                OutputSerialization={"JSON": {"RecordDelimiter": "\n"}},
            )
            mock_select_object_content.reset_mock()
            mock_select_object_content.return_value = {
                "ResponseMetadata": ANY,
                "Payload": [{"Records": {"Payload": encode_jsonl([{"id": 1}, {"id": 2}])}, "Stats": {}, "End": {}}],
            }

            # can also filter using raw where string (used by search_archives command)
            records_iter = archive.iter_records(where={"__raw__": "s.id < 3"})

            self.assertEqual([{"id": 1}, {"id": 2}], list(records_iter))

            mock_select_object_content.assert_called_once_with(
                Bucket="test-archives",
                Key=f"{self.org.id}/message_D20240814_477c143c30f72ee7a028c7c9e04992f9.jsonl.gz",
                ExpressionType="SQL",
                Expression="SELECT s.* FROM s3object s WHERE s.id < 3",
                InputSerialization={"CompressionType": "GZIP", "JSON": {"Type": "LINES"}},
                OutputSerialization={"JSON": {"RecordDelimiter": "\n"}},
            )

    def test_iter_all_records(self):
        d20200731 = self.create_archive(
            Archive.TYPE_MSG,
            "D",
            date(2020, 7, 31),
            [
                {"id": 1, "created_on": "2020-07-30T10:00:00Z", "contact": {"name": "Bob"}},
                {"id": 2, "created_on": "2020-07-30T15:00:00Z", "contact": {"name": "Jim"}},
            ],
        )
        m20200701 = self.create_archive(
            Archive.TYPE_MSG,
            "M",
            date(2020, 7, 1),
            [
                {"id": 1, "created_on": "2020-07-30T10:00:00Z", "contact": {"name": "Bob"}},
                {"id": 2, "created_on": "2020-07-30T15:00:00Z", "contact": {"name": "Jim"}},
            ],
            rollup_of=(d20200731,),
        )
        d20200801 = self.create_archive(
            Archive.TYPE_MSG,
            "D",
            date(2020, 8, 1),
            [
                {"id": 3, "created_on": "2020-08-01T10:00:00Z", "contact": {"name": "Jim"}},
                {"id": 4, "created_on": "2020-08-01T15:00:00Z", "contact": {"name": "Bob"}},
            ],
        )
        self.create_archive(
            Archive.TYPE_FLOWRUN,
            "D",
            date(2020, 8, 1),
            [
                {"id": 3, "created_on": "2020-08-01T10:00:00Z", "contact": {"name": "Jim"}},
                {"id": 4, "created_on": "2020-08-01T15:00:00Z", "contact": {"name": "Bob"}},
            ],
        )
        d20200802 = self.create_archive(
            Archive.TYPE_MSG,
            "D",
            date(2020, 8, 2),
            [
                {"id": 5, "created_on": "2020-08-02T10:00:00Z", "contact": {"name": "Bob"}},
                {"id": 6, "created_on": "2020-08-02T15:00:00Z", "contact": {"name": "Bob"}},
            ],
        )

        # no date range or where clause returns all message records, avoiding duplicates from rollups
        record_iter = Archive.iter_all_records(self.org, Archive.TYPE_MSG)

        self.assertEqual([1, 2, 3, 4, 5, 6], [r["id"] for r in list(record_iter)])

        with patch.object(s3.client(), "select_object_content") as mock_select_object_content:
            mock_select_object_content.return_value = {"ResponseMetadata": ANY, "Payload": [{"Stats": {}, "End": {}}]}

            list(
                Archive.iter_all_records(
                    self.org,
                    Archive.TYPE_MSG,
                    after=datetime(2020, 7, 30, 12, 0, 0, 0, tzone.utc),
                    before=datetime(2020, 8, 2, 12, 0, 0, 0, tzone.utc),
                )
            )

            self.assertEqual(
                [
                    call(
                        Bucket="test-archives",
                        Key=m20200701.get_storage_location()[1],
                        ExpressionType="SQL",
                        Expression="SELECT s.* FROM s3object s WHERE CAST(s.created_on AS TIMESTAMP) >= CAST('2020-07-30T12:00:00+00:00' AS TIMESTAMP) AND CAST(s.created_on AS TIMESTAMP) <= CAST('2020-08-02T12:00:00+00:00' AS TIMESTAMP)",
                        InputSerialization={"CompressionType": "GZIP", "JSON": {"Type": "LINES"}},
                        OutputSerialization={"JSON": {"RecordDelimiter": "\n"}},
                    ),
                    call(
                        Bucket="test-archives",
                        Key=d20200801.get_storage_location()[1],
                        ExpressionType="SQL",
                        Expression="SELECT s.* FROM s3object s WHERE CAST(s.created_on AS TIMESTAMP) >= CAST('2020-07-30T12:00:00+00:00' AS TIMESTAMP) AND CAST(s.created_on AS TIMESTAMP) <= CAST('2020-08-02T12:00:00+00:00' AS TIMESTAMP)",
                        InputSerialization={"CompressionType": "GZIP", "JSON": {"Type": "LINES"}},
                        OutputSerialization={"JSON": {"RecordDelimiter": "\n"}},
                    ),
                    call(
                        Bucket="test-archives",
                        Key=d20200802.get_storage_location()[1],
                        ExpressionType="SQL",
                        Expression="SELECT s.* FROM s3object s WHERE CAST(s.created_on AS TIMESTAMP) >= CAST('2020-07-30T12:00:00+00:00' AS TIMESTAMP) AND CAST(s.created_on AS TIMESTAMP) <= CAST('2020-08-02T12:00:00+00:00' AS TIMESTAMP)",
                        InputSerialization={"CompressionType": "GZIP", "JSON": {"Type": "LINES"}},
                        OutputSerialization={"JSON": {"RecordDelimiter": "\n"}},
                    ),
                ],
                mock_select_object_content.mock_calls,
            )

    def test_end_date(self):
        daily = self.create_archive(Archive.TYPE_FLOWRUN, "D", date(2018, 2, 1), [], needs_deletion=True)
        monthly = self.create_archive(Archive.TYPE_FLOWRUN, "M", date(2018, 1, 1), [])

        self.assertEqual(date(2018, 2, 2), daily.get_end_date())
        self.assertEqual(date(2018, 2, 1), monthly.get_end_date())

    def test_rewrite(self):
        archive = self.create_archive(
            Archive.TYPE_FLOWRUN,
            "D",
            date(2020, 8, 1),
            [
                {"id": 1, "created_on": "2020-08-01T09:00:00Z", "contact": {"name": "Bob"}},
                {"id": 2, "created_on": "2020-08-01T10:00:00Z", "contact": {"name": "Jim"}},
                {"id": 3, "created_on": "2020-08-01T15:00:00Z", "contact": {"name": "Bob"}},
            ],
        )

        bucket, key = archive.get_storage_location()

        def purge_jim(record):
            return record if record["contact"]["name"] != "Jim" else None

        archive.rewrite(purge_jim, delete_old=True)
        archive.refresh_from_db()

        new_bucket, new_key = archive.get_storage_location()
        self.assertEqual("test-archives", new_bucket)
        self.assertNotEqual(key, new_key)
        self.assertEqual(f"test-archives:{self.org.id}/run_D20200801_{archive.hash}.jsonl.gz", archive.location)
        self.assertEqual("59de3863f44426885fd58660c7ff58a6", archive.hash)

        hash_b64 = base64.standard_b64encode(bytes.fromhex(archive.hash)).decode()

        self.assertEqual("PutObject", self.s3_calls[-2][0])
        self.assertEqual("test-archives", self.s3_calls[-2][1]["Bucket"])
        self.assertEqual(f"{self.org.id}/run_D20200801_{archive.hash}.jsonl.gz", self.s3_calls[-2][1]["Key"])
        self.assertEqual(hash_b64, self.s3_calls[-2][1]["ContentMD5"])
        self.assertEqual("DeleteObject", self.s3_calls[-1][0])
        self.assertEqual("test-archives", self.s3_calls[-1][1]["Bucket"])

        self.s3_calls = []

        # rewriting again should produce same content, same hash, and thus result in a put but not a delete
        archive.rewrite(purge_jim, delete_old=True)
        archive.refresh_from_db()

        new_bucket, new_key = archive.get_storage_location()
        self.assertEqual("test-archives", new_bucket)
        self.assertNotEqual(key, new_key)
        self.assertEqual("59de3863f44426885fd58660c7ff58a6", archive.hash)
        self.assertEqual(f"test-archives:{self.org.id}/run_D20200801_{archive.hash}.jsonl.gz", archive.location)

        self.assertEqual(2, len(self.s3_calls))
        self.assertEqual("GetObject", self.s3_calls[0][0])
        self.assertEqual("PutObject", self.s3_calls[1][0])

        self.assertEqual(2, len(list(archive.iter_records())))
