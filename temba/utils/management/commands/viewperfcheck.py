from __future__ import unicode_literals

import time

from colorama import init as colorama_init, Fore, Style
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.urlresolvers import reverse
from django.db import connection, reset_queries
from django.http import HttpRequest
from django.test.client import Client
from importlib import import_module
from rest_framework.test import APIClient
from temba.api.models import APIToken


VIEW_TESTS = [
    # view name, querystring, main database table

    # UI views
    ('campaigns.campaign_list', '', 'campaigns_campaign'),
    ('channels.channelevent_calls', '', 'channels_channelevent'),
    ('contacts.contact_list', '', 'contacts_contact'),
    ('contacts.contact_failed', '', 'contacts_contact'),
    ('contacts.contact_blocked', '', 'contacts_contact'),
    ('flows.flow_list', '', 'flows_flow'),
    ('msgs.broadcast_schedule_list', '', 'msgs_broadcast'),
    ('msgs.msg_inbox', '', 'msgs_msg'),
    ('msgs.msg_flow', '', 'msgs_msg'),
    ('msgs.msg_archived', '', 'msgs_msg'),
    ('msgs.msg_outbox', '', 'msgs_msg'),
    ('msgs.msg_sent', '', 'msgs_msg'),
    ('msgs.msg_failed', '', 'msgs_msg'),

    # API v1
    ('api.v1.contacts', '', 'contacts_contact'),
    ('api.v1.messages', '?direction=I', 'msgs_msg'),
    ('api.v1.runs', '', 'flows_flowrun'),

    # API v2
    ('api.v2.broadcasts', '', 'msgs_broadcast'),
    ('api.v2.channels', '', 'channels_channel'),
    ('api.v2.channel_events', '', 'channels_channelevent'),
    ('api.v2.contacts', '', 'contacts_contact'),
    ('api.v2.contacts', '?deleted=true', 'contacts_contact'),
    ('api.v2.fields', '', 'contacts_contactfield'),
    ('api.v2.groups', '', 'contacts_contactgroup'),
    ('api.v2.labels', '', 'msgs_label'),
    ('api.v2.messages', '?folder=incoming', 'msgs_msg'),
    ('api.v2.messages', '?folder=inbox', 'msgs_msg'),
    ('api.v2.messages', '?folder=flows', 'msgs_msg'),
    ('api.v2.messages', '?folder=archived', 'msgs_msg'),
    ('api.v2.messages', '?folder=outbox', 'msgs_msg'),
    ('api.v2.messages', '?folder=sent', 'msgs_msg'),
    ('api.v2.org', '', 'orgs_org'),
    ('api.v2.runs', '', 'flows_flowrun'),
    ('api.v2.runs', '?responded=true', 'flows_flowrun'),
]


REQUEST_TIME_LIMITS = (0.5, 1)  # limit for warning, limit for problem
DB_TIME_LIMITS = (0.5, 1)
NUM_QUERY_LIMITS = (50, 100)


class Command(BaseCommand):  # pragma: no cover
    help = "Checks access and index usage of views"

    def add_arguments(self, parser):
        parser.add_argument(type=str, action='store', dest='token', metavar="APITOKEN",
                            help="The API token to test against")

    def handle(self, token, *args, **options):
        colorama_init()

        settings.COMPRESS_ENABLED = True

        try:
            token_obj = APIToken.objects.get(key=token)
        except APIToken.DoesNotExist:
            raise CommandError("No such API token exists")

        user, org = token_obj.user, token_obj.org

        self.stdout.write("Checking with token %s for user %s [%d] in org %s [%d] with role %s...\n\n"
                          % (colored(token, Fore.BLUE),
                             colored(user.username, Fore.BLUE),
                             user.pk,
                             colored(org.name, Fore.BLUE),
                             org.pk,
                             colored(token_obj.role.name, Fore.BLUE)))

        self.stdout.write("URL / HTTP status / request time / database time / number of queries / indexes scanned")
        self.stdout.write("--------------------------------------------------------------------------------------")

        for test in VIEW_TESTS:
            self.test_url(token_obj, *test, num_requests=3)

    def test_url(self, token, view_name, query, table, num_requests):
        if view_name.startswith('api.'):
            url = reverse(view_name) + '.json' + query

            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        else:
            url = reverse(view_name) + query

            client = DjangoClient()
            client.force_login(token.user)

            s = client.session
            s['org_id'] = token.org.pk
            s.save()

        pre_index_scans = self.get_index_scan_counts(table)

        statuses = []
        request_times = []
        db_times = []
        query_counts = []

        for r in range(num_requests):
            reset_queries()
            start_time = time.time()

            response = client.get(url)

            statuses.append(response.status_code)
            request_times.append(time.time() - start_time)
            db_times.append(sum([float(q['time']) for q in connection.queries]))
            query_counts.append(len(connection.queries))

        # TODO figure out how to get stats to refresh without this workaround.
        # You'd think that SELECT pg_stat_clear_snapshot() might work but no.
        connection.close()
        time.sleep(1)

        post_index_scans = self.get_index_scan_counts(table)
        used_indexes = [i for i, scans in pre_index_scans.iteritems() if post_index_scans.get(i) > scans]

        last_status = statuses[-1]
        avg_request_time = sum(request_times) / len(request_times)
        avg_db_time = sum(db_times) / len(db_times)
        last_query_count = query_counts[-1]

        self.stdout.write("%s %s / %s secs / %s secs / %s queries / %s" % (
            url,
            colored(last_status, Fore.GREEN if 200 <= last_status < 300 else Fore.RED),
            colorcoded(avg_request_time, REQUEST_TIME_LIMITS),
            colorcoded(avg_db_time, DB_TIME_LIMITS),
            colorcoded(last_query_count, NUM_QUERY_LIMITS),
            styled(", ".join(used_indexes), Style.DIM)
        ))

    @staticmethod
    def get_index_scan_counts(table_name):
        cursor = connection.cursor()
        cursor.execute("SELECT indexrelname, idx_scan FROM pg_stat_user_indexes "
                       "WHERE schemaname = 'public' AND relname = %s", [table_name])
        rows = cursor.fetchall()
        if not rows:
            raise ValueError("No indexes for table %s. Wrong table name?" % table_name)

        return {row[0]: row[1] for row in rows}


def colorcoded(val, limits):
    if val > limits[1]:
        color = Fore.RED
    elif val > limits[0]:
        color = Fore.YELLOW
    else:
        color = Fore.GREEN

    if isinstance(val, float):
        val = "%.3f" % val

    return colored(val, color)


def colored(val, color):
    return color + unicode(val) + Fore.RESET


def styled(val, style):
    return style + unicode(val) + Style.RESET_ALL


class DjangoClient(Client):
    """
    Until we upgrade to Django 1.9, provides a test client with force_login for easy access as different users
    """
    def login(self, **credentials):
        """
        Sets the Factory to appear as if it has successfully logged into a site.

        Returns True if login is possible; False if the provided credentials
        are incorrect, or the user is inactive, or if the sessions framework is
        not available.
        """
        from django.contrib.auth import authenticate
        user = authenticate(**credentials)
        if user and user.is_active:
            self._login(user)
            return True
        else:
            return False

    def force_login(self, user, backend=None):
        if backend is None:
            backend = settings.AUTHENTICATION_BACKENDS[0]
        user.backend = backend
        self._login(user)

    def _login(self, user):
        from django.contrib.auth import login
        engine = import_module(settings.SESSION_ENGINE)

        # Create a fake request to store login details.
        request = HttpRequest()

        if self.session:
            request.session = self.session
        else:
            request.session = engine.SessionStore()
        login(request, user)

        # Save the session values.
        request.session.save()

        # Set the cookie to represent the session.
        session_cookie = settings.SESSION_COOKIE_NAME
        self.cookies[session_cookie] = request.session.session_key
        cookie_data = {
            'max-age': None,
            'path': '/',
            'domain': settings.SESSION_COOKIE_DOMAIN,
            'secure': settings.SESSION_COOKIE_SECURE or None,
            'expires': None,
        }
        self.cookies[session_cookie].update(cookie_data)
