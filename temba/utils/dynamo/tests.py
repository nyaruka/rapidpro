from decimal import Decimal

from temba.tests import TembaTest
from temba.utils import dynamo


class DynamoTest(TembaTest):
    def tearDown(self):
        for table in [dynamo.MAIN, dynamo.HISTORY]:
            for item in table.scan()["Items"]:
                table.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

        return super().tearDown()

    def test_get_client(self):
        client1 = dynamo.get_client()
        client2 = dynamo.get_client()
        self.assertIs(client1, client2)

    def test_table_name(self):
        self.assertEqual("TestThings", dynamo.table_name("Things"))

    def test_jsongz(self):
        data = dynamo.dump_jsongz({"foo": "barbarbarbarbarbarbarbarbarbarbarbarbarbarbarbar"})
        self.assertEqual(36, len(data))
        self.assertEqual({"foo": "barbarbarbarbarbarbarbarbarbarbarbarbarbarbarbar"}, dynamo.load_jsongz(data))

    def test_merged_page_query(self):
        dynamo.MAIN.put_item(Item={"PK": "foo#3", "SK": "bar#100", "OrgID": Decimal(1), "Data": {}})
        dynamo.MAIN.put_item(Item={"PK": "foo#1", "SK": "bar#101", "OrgID": Decimal(1), "Data": {}})
        dynamo.MAIN.put_item(Item={"PK": "foo#2", "SK": "bar#102", "OrgID": Decimal(1), "Data": {}})
        dynamo.MAIN.put_item(Item={"PK": "foo#2", "SK": "bar#103", "OrgID": Decimal(1), "Data": {}})
        dynamo.MAIN.put_item(Item={"PK": "foo#1", "SK": "bar#104", "OrgID": Decimal(1), "Data": {}})
        dynamo.MAIN.put_item(Item={"PK": "foo#1", "SK": "bar#105", "OrgID": Decimal(1), "Data": {}})

        pks = ["foo#1", "foo#2", "foo#3", "foo#4"]

        page1, cursor1 = dynamo.merged_page_query(dynamo.MAIN, pks, forward=True, limit=4)
        self.assertEqual(
            [
                {"PK": "foo#3", "SK": "bar#100", "OrgID": Decimal(1), "Data": {}},
                {"PK": "foo#1", "SK": "bar#101", "OrgID": Decimal(1), "Data": {}},
                {"PK": "foo#2", "SK": "bar#102", "OrgID": Decimal(1), "Data": {}},
                {"PK": "foo#2", "SK": "bar#103", "OrgID": Decimal(1), "Data": {}},
            ],
            page1,
        )
        self.assertEqual("bar#103", cursor1)

        page2, cursor2 = dynamo.merged_page_query(dynamo.MAIN, pks, forward=True, limit=4, start_sk=cursor1)
        self.assertEqual(
            [
                {"PK": "foo#1", "SK": "bar#104", "OrgID": Decimal(1), "Data": {}},
                {"PK": "foo#1", "SK": "bar#105", "OrgID": Decimal(1), "Data": {}},
            ],
            page2,
        )
        self.assertEqual("bar#105", cursor2)

        page3, cursor3 = dynamo.merged_page_query(dynamo.MAIN, pks, forward=True, limit=4, start_sk=cursor2)
        self.assertEqual([], page3)
        self.assertIsNone(cursor3)

        # now do the same queries in reverse order
        page1, cursor1 = dynamo.merged_page_query(dynamo.MAIN, pks, forward=False, limit=4)
        self.assertEqual(
            [
                {"PK": "foo#1", "SK": "bar#105", "OrgID": Decimal(1), "Data": {}},
                {"PK": "foo#1", "SK": "bar#104", "OrgID": Decimal(1), "Data": {}},
                {"PK": "foo#2", "SK": "bar#103", "OrgID": Decimal(1), "Data": {}},
                {"PK": "foo#2", "SK": "bar#102", "OrgID": Decimal(1), "Data": {}},
            ],
            page1,
        )
        self.assertEqual("bar#102", cursor1)

        page2, cursor2 = dynamo.merged_page_query(dynamo.MAIN, pks, forward=False, limit=4, start_sk=cursor1)
        self.assertEqual(
            [
                {"PK": "foo#1", "SK": "bar#101", "OrgID": Decimal(1), "Data": {}},
                {"PK": "foo#3", "SK": "bar#100", "OrgID": Decimal(1), "Data": {}},
            ],
            page2,
        )
        self.assertEqual("bar#100", cursor2)

        page3, cursor3 = dynamo.merged_page_query(dynamo.MAIN, pks, forward=False, limit=4, start_sk=cursor2)
        self.assertEqual([], page3)
        self.assertIsNone(cursor3)
