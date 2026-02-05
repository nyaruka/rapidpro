from temba.msgs.models import QuickReply
from temba.tests import TembaTest


class QuickReplyTest(TembaTest):
    def test_quick_replies(self):
        # check decoding
        self.assertEqual({"type": "text", "text": "Yes"}, QuickReply.decode("Yes"))
        self.assertEqual(
            {"type": "text", "text": "Yes", "extra": "Let's go!"}, QuickReply.decode("Yes<extra>Let's go!")
        )
        self.assertEqual({"type": "location"}, QuickReply.decode("<location>"))
        self.assertEqual({"type": "location", "text": "Click"}, QuickReply.decode("<location>Click"))

        # check encoding
        self.assertEqual("Yes", QuickReply.encode({"type": "text", "text": "Yes"}))
        self.assertEqual(
            "Yes<extra>Let's go!", QuickReply.encode({"type": "text", "text": "Yes", "extra": "Let's go!"})
        )
        self.assertEqual("<location>", QuickReply.encode({"type": "location"}))
        self.assertEqual("<location>Click", QuickReply.encode({"type": "location", "text": "Click"}))
