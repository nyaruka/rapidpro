from datetime import timedelta

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from temba import __version__ as temba_version
from temba.apks.models import Apk
from temba.channels.models import ChannelEvent
from temba.tests import TembaTest


class PublicTest(TembaTest):
    def test_index(self):
        home_url = reverse("public.public_index")
        response = self.client.get(home_url, follow=True)
        self.assertEqual(response.request["PATH_INFO"], "/")
        self.assertContains(response, temba_version)

    def test_forgetme(self):
        contact = self.create_contact("Joe", phone="+250788111222")
        e1 = ChannelEvent.objects.create(
            org=self.org,
            channel=self.channel,
            event_type=ChannelEvent.TYPE_STOP_CONTACT,
            contact=contact,
            created_on=timezone.now() - timedelta(days=3),
            occurred_on=timezone.now() - timedelta(days=3),
        )
        e2 = ChannelEvent.objects.create(
            org=self.org,
            channel=self.channel,
            event_type=ChannelEvent.TYPE_DELETE_CONTACT,
            contact=contact,
            created_on=timezone.now() - timedelta(days=2),
            occurred_on=timezone.now() - timedelta(days=3),
        )
        self.assertEqual(2, ChannelEvent.objects.all().count())

        # 404 for non delete request event type
        forgetme_url = reverse("public.public_forgetme")

        response = self.client.get(forgetme_url)
        self.assertEqual(200, response.status_code)
        self.assertNotContains(response, "Incorrect code provided, try again")

        # not valid uuid
        post_data = dict(code="foo")
        response = self.client.post(forgetme_url, post_data, follow=True)
        self.assertFormError(response.context["form"], "code", ["Invalid confirmation code"])
        self.assertNotContains(response, "Incorrect code provided, try again")

        # invalid confirmation code for event of type delete request
        post_data = dict(code=e1.uuid)
        response = self.client.post(forgetme_url, post_data, follow=True)
        self.assertContains(response, "Incorrect code provided, try again")

        # valid confirmation code for event of type delete request
        post_data = dict(code=e2.uuid)
        response = self.client.post(forgetme_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, f"Confirmation code: {e2.uuid}")

    def test_android(self):
        android_url = reverse("public.public_android")
        response = self.client.get(android_url, follow=True)
        self.assertEqual(404, response.status_code)

        Apk.objects.create(
            apk_type="R",
            version="1.9.8",
            description="* better syncing",
            apk_file=SimpleUploadedFile(
                "relayer.apk", content=b"DATA", content_type="application/vnd.android.package-archive"
            ),
        )

        android_url = reverse("public.public_android")
        response = self.client.get(android_url)
        self.assertEqual(302, response.status_code)
        self.assertIn(f"{settings.STORAGE_URL}/apks/relayer", response.url)

        Apk.objects.create(
            apk_type="M",
            version="1.9.8",
            pack=1,
            description="* latest pack",
            apk_file=SimpleUploadedFile(
                "pack.apk", content=b"DATA", content_type="application/vnd.android.package-archive"
            ),
        )

        response = self.client.get(f"{android_url}?v=1.9.8&pack=1")
        self.assertEqual(302, response.status_code)
        self.assertIn(f"{settings.STORAGE_URL}/apks/pack", response.url)

    def test_welcome(self):
        welcome_url = reverse("public.public_welcome")
        response = self.client.get(welcome_url, follow=True)
        self.assertIn("next", response.request["QUERY_STRING"])
        self.assertEqual(response.request["PATH_INFO"], settings.LOGIN_URL)

        self.login(self.editor)
        response = self.client.get(welcome_url, follow=True)
        self.assertEqual(response.request["PATH_INFO"], reverse("public.public_welcome"))

    def test_demo_coupon(self):
        coupon_url = reverse("demo.generate_coupon")
        response = self.client.get(coupon_url, follow=True)
        self.assertEqual(response.request["PATH_INFO"], coupon_url)
        self.assertContains(response, "coupon")

    def test_demo_status(self):
        status_url = reverse("demo.order_status")
        response = self.client.get(status_url, follow=True)
        self.assertEqual(response.request["PATH_INFO"], status_url)
        self.assertContains(response, "Invalid")

        response = self.client.get("%s?text=somethinginvalid" % status_url)
        self.assertEqual(response.request["PATH_INFO"], status_url)
        self.assertContains(response, "Invalid")

        response = self.client.get("%s?text=cu001" % status_url)
        self.assertEqual(response.request["PATH_INFO"], status_url)
        self.assertContains(response, "Shipped")

        response = self.client.get("%s?text=cu002" % status_url)
        self.assertEqual(response.request["PATH_INFO"], status_url)
        self.assertContains(response, "Pending")

        response = self.client.get("%s?text=cu003" % status_url)
        self.assertEqual(response.request["PATH_INFO"], status_url)
        self.assertContains(response, "Cancelled")

        response = self.client.post(status_url, {}, content_type="application/json", follow=True)
        self.assertEqual(response.request["PATH_INFO"], status_url)
        self.assertContains(response, "Invalid")

        response = self.client.post(status_url, dict(text="somethinginvalid"), content_type="application/json")
        self.assertEqual(response.request["PATH_INFO"], status_url)
        self.assertContains(response, "Invalid")

        response = self.client.post(status_url, dict(input=dict(text="CU001")), content_type="application/json")
        self.assertEqual(response.request["PATH_INFO"], status_url)
        self.assertContains(response, "Shipped")

        response = self.client.post(status_url, dict(input=dict(text="CU002")), content_type="application/json")
        self.assertEqual(response.request["PATH_INFO"], status_url)
        self.assertContains(response, "Pending")

        response = self.client.post(status_url, dict(input=dict(text="CU003")), content_type="application/json")
        self.assertEqual(response.request["PATH_INFO"], status_url)
        self.assertContains(response, "Cancelled")

    def test_templatetags(self):
        from .templatetags.public import gear_link_classes

        link = dict()
        link["posterize"] = True
        self.assertTrue("posterize", gear_link_classes(link))
        link["js_class"] = "alright"
        self.assertTrue("posterize alright", gear_link_classes(link))
        link["style"] = "pull-right"
        self.assertTrue("posterize alright pull-right", gear_link_classes(link, True))
        link["modal"] = True
        self.assertTrue("posterize alright pull-right gear-modal", gear_link_classes(link, True))
        link["delete"] = True
        self.assertTrue("posterize alright pull-right gear-modal gear-delete", gear_link_classes(link, True))

    def test_sitemaps(self):
        sitemap_url = reverse("public.sitemaps")

        response = self.client.get(sitemap_url)
        self.assertEqual(
            response.context["urlset"][0],
            {
                "priority": "0.5",
                "item": "public.public_index",
                "lastmod": None,
                "changefreq": "daily",
                "location": "http://example.com/",
                "alternates": [],
            },
        )
