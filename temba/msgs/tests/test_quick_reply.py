from temba.msgs.models import QuickReply
from temba.tests import TembaTest


class QuickReplyTest(TembaTest):
    def test_quick_replies(self):
        # check equality
        self.assertEqual(QuickReply("text", "Yes", "Let's go!"), QuickReply("text", "Yes", "Let's go!"))
        self.assertNotEqual(QuickReply("text", "Yes", "Let's go!"), QuickReply("text", "Yes", None))

        # check parsing
        self.assertEqual(QuickReply("text", "Yes", None), QuickReply.parse("Yes"))
        self.assertEqual(QuickReply("text", "Yes", "Let's go!"), QuickReply.parse("Yes<extra>Let's go!"))
        self.assertEqual(QuickReply("location", None, None), QuickReply.parse("<location>"))
        self.assertEqual(QuickReply("location", "Click", None), QuickReply.parse("<location>Click"))

        # check encoding
        self.assertEqual("Yes", str(QuickReply("text", "Yes", None)))
        self.assertEqual("Yes<extra>Let's go!", str(QuickReply("text", "Yes", "Let's go!")))
        self.assertEqual("<location>", str(QuickReply("location", None, None)))
        self.assertEqual("<location>Click", str(QuickReply("location", "Click", None)))

        self.assertEqual({"type": "text", "text": "Yes"}, QuickReply("text", "Yes", None).as_json())
        self.assertEqual(
            {"type": "text", "text": "Yes", "extra": "Let's go!"}, QuickReply("text", "Yes", "Let's go!").as_json()
        )
        self.assertEqual({"type": "location"}, QuickReply("location", None, None).as_json())
        self.assertEqual({"type": "location", "text": "Click"}, QuickReply("location", "Click", None).as_json())
