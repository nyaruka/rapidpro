from temba.msgs.models import QuickReply
from temba.tests import TembaTest


class QuickReplyTest(TembaTest):
    def test_quick_replies(self):
        # check equality
        self.assertEqual(QuickReply("Yes", "Let's go!"), QuickReply("Yes", "Let's go!"))
        self.assertNotEqual(QuickReply("Yes", "Let's go!"), QuickReply("Yes", None))

        # check parsing
        self.assertEqual(QuickReply("Yes", None), QuickReply.parse("Yes"))
        self.assertEqual(QuickReply("Yes", "Let's go!"), QuickReply.parse("Yes\nLet's go!"))

        # check encoding
        self.assertEqual("Yes", str(QuickReply("Yes", None)))
        self.assertEqual("Yes\nLet's go!", str(QuickReply("Yes", "Let's go!")))

        self.assertEqual({"text": "Yes"}, QuickReply("Yes", None).as_json())
        self.assertEqual({"text": "Yes", "extra": "Let's go!"}, QuickReply("Yes", "Let's go!").as_json())
