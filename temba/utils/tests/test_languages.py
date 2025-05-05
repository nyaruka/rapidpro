from django.test import override_settings

from temba.tests import TembaTest
from temba.utils import languages


class LanguagesTest(TembaTest):
    def test_get_name(self):
        with override_settings(NON_ISO6391_LANGUAGES={"acx", "frc", "kir"}):
            languages.reload()
            self.assertEqual("French", languages.get_name("fra"))
            self.assertEqual("Arabic (Omani, ISO-639-3)", languages.get_name("acx"))  # name is overridden
            self.assertEqual("Cajun French", languages.get_name("frc"))  # non ISO-639-1 lang explicitly included
            self.assertEqual("Kyrgyz", languages.get_name("kir"))
            self.assertEqual("Oromifa", languages.get_name("orm"))

            self.assertEqual("", languages.get_name("cpi"))  # not in our allowed languages
            self.assertEqual("", languages.get_name("xyz"))

            # should strip off anything after an open paren or semicolon
            self.assertEqual("Haitian", languages.get_name("hat"))

        languages.reload()

    def test_search_by_name(self):
        # check that search returns results and in the proper order
        self.assertEqual(
            [
                {"value": "afr", "name": "Afrikaans"},
                {"value": "fra", "name": "French"},
                {"value": "fry", "name": "Western Frisian"},
            ],
            languages.search_by_name("Fr"),
        )

        # usually only return ISO-639-1 languages but can add inclusions in settings
        with override_settings(NON_ISO6391_LANGUAGES={"afr", "afb", "acx", "frc"}):
            languages.reload()

            # order is based on name rather than code
            self.assertEqual(
                [
                    {"value": "afr", "name": "Afrikaans"},
                    {"value": "frc", "name": "Cajun French"},
                    {"value": "fra", "name": "French"},
                    {"value": "fry", "name": "Western Frisian"},
                ],
                languages.search_by_name("Fr"),
            )

            # searching and ordering uses overridden names
            self.assertEqual(
                [
                    {"value": "ara", "name": "Arabic"},
                    {"value": "afb", "name": "Arabic (Gulf, ISO-639-3)"},
                    {"value": "acx", "name": "Arabic (Omani, ISO-639-3)"},
                ],
                languages.search_by_name("Arabic"),
            )

        languages.reload()

    def alpha2_to_alpha3(self):
        self.assertEqual("eng", languages.alpha2_to_alpha3("en"))
        self.assertEqual("eng", languages.alpha2_to_alpha3("en-us"))
        self.assertEqual("spa", languages.alpha2_to_alpha3("es"))
        self.assertIsNone(languages.alpha2_to_alpha3("xx"))
