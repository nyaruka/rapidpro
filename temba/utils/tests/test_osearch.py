from unittest.mock import patch

from opensearchpy import RequestsHttpConnection

from temba.tests import TembaTest
from temba.utils.osearch import get_client


class OSearchTest(TembaTest):
    @patch("temba.utils.osearch.OpenSearch")
    @patch("temba.utils.osearch.settings")
    def test_get_client(self, mock_settings, mock_os):
        mock_settings.OPENSEARCH_ENDPOINT_URL = "http://localhost:9200"
        mock_settings.AWS_ACCESS_KEY_ID = ""
        mock_settings.AWS_SECRET_ACCESS_KEY = ""

        get_client()

        mock_os.assert_called_once_with(
            hosts=[{"host": "localhost", "port": 9200}],
            use_ssl=False,
            verify_certs=False,
            connection_class=RequestsHttpConnection,
        )

    @patch("temba.utils.osearch.OpenSearch")
    @patch("temba.utils.osearch.settings")
    def test_get_client_https(self, mock_settings, mock_os):
        mock_settings.OPENSEARCH_ENDPOINT_URL = "https://search.example.com"
        mock_settings.AWS_ACCESS_KEY_ID = ""
        mock_settings.AWS_SECRET_ACCESS_KEY = ""

        get_client()

        mock_os.assert_called_once_with(
            hosts=[{"host": "search.example.com", "port": 443}],
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )
