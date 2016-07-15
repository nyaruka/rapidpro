from django.core.urlresolvers import reverse
from mock import patch
from temba.events.models import AirtimeEvent
from temba.tests import TembaTest, MockResponse


class AirtimeEventTest(TembaTest):
    def setUp(self):
        super(AirtimeEventTest, self).setUp()

        self.org.connect_transferto('mylogin', 'api_token', self.admin)
        self.airtime_event = AirtimeEvent.objects.create(org=self.org, recipient='+250788123123', amount='100',
                                                         created_by=self.admin, modified_by=self.admin)

    def test_translate_transferto_api_response(self):
        self.assertEqual(AirtimeEvent.translate_transferto_response_content_as_json(""), dict())

        self.assertEqual(AirtimeEvent.translate_transferto_response_content_as_json("foo"), dict())

        self.assertEqual(AirtimeEvent.translate_transferto_response_content_as_json("foo\r\nbar"), dict())

        self.assertEqual(AirtimeEvent.translate_transferto_response_content_as_json("foo=allo\r\nbar"),
                         dict(foo='allo'))

        self.assertEqual(AirtimeEvent.translate_transferto_response_content_as_json("foo=allo\r\nbar=1,2,3\r\n"),
                         dict(foo='allo', bar=['1', '2', '3']))

    @patch('temba.events.models.AirtimeEvent.post_transferto_api_response')
    def test_get_transferto_response_json(self, mock_post_transferto):
        mock_post_transferto.return_value = MockResponse(200, "foo=allo\r\nbar=1,2,3\r\n")

        self.assertEqual((200, dict(foo="allo", bar=["1", "2", "3"]), "foo=allo\r\nbar=1,2,3\r\n"),
                         self.airtime_event.get_transferto_response_json(action='command'))

        mock_post_transferto.assert_called_once_with('mylogin', 'api_token', action='command')

    def test_list(self):
        list_url = reverse('events.airtimeevent_list')

        self.login(self.user)
        response = self.client.get(list_url)
        self.assertRedirect(response, '/users/login/')

        self.login(self.editor)
        response = self.client.get(list_url)
        self.assertRedirect(response, '/users/login/')

        self.login(self.admin)
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.airtime_event in response.context['object_list'])

    def test_read(self):
        read_url = reverse('events.airtimeevent_read', args=[self.airtime_event.pk])

        self.login(self.user)
        response = self.client.get(read_url)
        self.assertRedirect(response, '/users/login/')

        self.login(self.editor)
        response = self.client.get(read_url)
        self.assertRedirect(response, '/users/login/')

        self.login(self.admin)
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.airtime_event.pk, response.context['object'].pk)
