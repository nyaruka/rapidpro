from temba.tests import TembaTest
from temba.utils.compose import compose_serialize


class ComposeTest(TembaTest):
    def test_empty_compose(self):
        self.assertEqual(compose_serialize(), {})
