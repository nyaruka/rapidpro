from temba.tests import TembaTest
from temba.utils.compose import compose_deserialize, compose_serialize


class ComposeTest(TembaTest):
    def test_serialize(self):
        self.assertEqual(compose_serialize(None), {})
        self.assertEqual(compose_serialize({"eng": {"text": "Hello"}}), {"eng": {"text": "Hello"}})
        self.assertEqual(
            compose_serialize({"eng": {"text": "Hello", "quick_replies": [{"text": "Yes"}, {"text": "No"}]}}),
            {"eng": {"text": "Hello", "quick_replies": ["Yes", "No"]}},
        )

    def test_deserialize(self):
        self.assertEqual(compose_deserialize({"eng": {"text": "Hello"}}), {"eng": {"text": "Hello", "attachments": []}})
        self.assertEqual(
            compose_deserialize(
                {
                    "eng": {
                        "text": "Hello",
                        "attachments": [
                            {
                                "uuid": "8a798c81-c890-4fe5-b9c7-617c06096b94",
                                "content_type": "image/jpeg",
                                "url": "https://example.com/image.jpg",
                                "filename": "image.jpg",
                                "size": "12345",
                            }
                        ],
                        "quick_replies": ["Yes", "No"],
                    }
                }
            ),
            {
                "eng": {
                    "text": "Hello",
                    "attachments": ["image/jpeg:https://example.com/image.jpg"],
                    "quick_replies": [{"text": "Yes"}, {"text": "No"}],
                }
            },
        )
