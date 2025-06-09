from temba.tests import TembaTest, matchers

from ..models import Channel, ChannelLog


class ChannelLogTest(TembaTest):
    def test_get_by_uuid(self):
        log1 = self.create_channel_log(
            self.channel,
            ChannelLog.LOG_TYPE_MSG_SEND,
            http_logs=[{"url": "https://foo.bar/send1"}],
            errors=[{"code": "bad_response", "message": "response not right"}],
        )
        log2 = self.create_channel_log(
            self.channel,
            ChannelLog.LOG_TYPE_MSG_STATUS,
            http_logs=[{"url": "https://foo.bar/send2"}],
            errors=[],
        )

        self.assertEqual([], ChannelLog.get_by_uuid(self.channel, []))

        logs = ChannelLog.get_by_uuid(self.channel, [log1.uuid, log2.uuid])
        self.assertEqual(2, len(logs))
        self.assertEqual(log1.uuid, logs[0].uuid)
        self.assertEqual(self.channel, logs[0].channel)
        self.assertEqual(ChannelLog.LOG_TYPE_MSG_SEND, logs[0].log_type)
        self.assertEqual([{"url": "https://foo.bar/send1"}], logs[0].http_logs)
        self.assertEqual([{"code": "bad_response", "message": "response not right"}], logs[0].errors)
        self.assertEqual(log1.created_on, logs[0].created_on)

        self.assertEqual(log2.uuid, logs[1].uuid)
        self.assertEqual(self.channel, logs[1].channel)
        self.assertEqual(ChannelLog.LOG_TYPE_MSG_STATUS, logs[1].log_type)

    def test_get_by_channel(self):
        channel = self.create_channel("TG", "Telegram", "mybot")
        log1 = self.create_channel_log(
            channel, ChannelLog.LOG_TYPE_MSG_SEND, http_logs=[{"url": "https://foo.bar/send1"}]
        )
        log2 = self.create_channel_log(
            channel, ChannelLog.LOG_TYPE_MSG_STATUS, http_logs=[{"url": "https://foo.bar/send2"}]
        )
        log3 = self.create_channel_log(
            channel, ChannelLog.LOG_TYPE_MSG_STATUS, http_logs=[{"url": "https://foo.bar/send2"}]
        )
        self.create_channel_log(
            self.channel, ChannelLog.LOG_TYPE_MSG_STATUS, http_logs=[{"url": "https://foo.bar/send2"}]
        )

        logs, prev_after, next_after = ChannelLog.get_by_channel(channel, limit=2)

        self.assertEqual([log3.uuid, log2.uuid], [l.uuid for l in logs])
        self.assertIsNone(prev_after)
        self.assertEqual(str(log2.uuid), next_after)

        logs, prev_after, next_after = ChannelLog.get_by_channel(channel, limit=2, after_uuid=next_after)

        self.assertEqual([log1.uuid], [l.uuid for l in logs])
        self.assertIsNone(prev_after)
        self.assertIsNone(next_after)

    def test_get_display(self):
        channel = self.create_channel("TG", "Telegram", "mybot")
        contact = self.create_contact("Fred Jones", urns=["telegram:74747474"])
        log = self.create_channel_log(
            channel,
            ChannelLog.LOG_TYPE_MSG_SEND,
            http_logs=[
                {
                    "url": "https://telegram.com/send?to=74747474",
                    "status_code": 400,
                    "request": 'POST https://telegram.com/send?to=74747474 HTTP/1.1\r\n\r\n{"to":"74747474"}',
                    "response": 'HTTP/2.0 200 OK\r\n\r\n{"to":"74747474","first_name":"Fred"}',
                    "elapsed_ms": 263,
                    "retries": 0,
                    "created_on": "2022-08-17T14:07:30Z",
                }
            ],
            errors=[{"code": "bad_response", "ext_code": "", "message": "response not right"}],
        )
        msg_out = self.create_outgoing_msg(contact, "Working", channel=channel, status="S", logs=[log])

        self.assertEqual(
            {
                "uuid": str(log.uuid),
                "type": "msg_send",
                "http_logs": [
                    {
                        "url": "https://telegram.com/send?to=74747474",
                        "status_code": 400,
                        "request": 'POST https://telegram.com/send?to=74747474 HTTP/1.1\r\n\r\n{"to":"74747474"}',
                        "response": 'HTTP/2.0 200 OK\r\n\r\n{"to":"74747474","first_name":"Fred"}',
                        "elapsed_ms": 263,
                        "retries": 0,
                        "created_on": "2022-08-17T14:07:30Z",
                    }
                ],
                "errors": [{"code": "bad_response", "ext_code": "", "message": "response not right", "ref_url": None}],
                "is_error": True,
                "elapsed_ms": 12,
                "created_on": matchers.ISODatetime(),
            },
            log.get_display(anonymize=False, urn=msg_out.contact_urn),
        )

        self.assertEqual(
            {
                "uuid": str(log.uuid),
                "type": "msg_send",
                "http_logs": [
                    {
                        "url": "https://telegram.com/send?to=********",
                        "status_code": 400,
                        "request": 'POST https://telegram.com/send?to=******** HTTP/1.1\r\n\r\n{"to":"********"}',
                        "response": 'HTTP/2.0 200 OK\r\n\r\n{"to": "********", "first_name": "********"}',
                        "elapsed_ms": 263,
                        "retries": 0,
                        "created_on": "2022-08-17T14:07:30Z",
                    }
                ],
                "errors": [{"code": "bad_response", "ext_code": "", "message": "response n********", "ref_url": None}],
                "is_error": True,
                "elapsed_ms": 12,
                "created_on": matchers.ISODatetime(),
            },
            log.get_display(anonymize=True, urn=msg_out.contact_urn),
        )

        # if we don't pass it a URN, anonymization is more aggressive
        self.assertEqual(
            {
                "uuid": str(log.uuid),
                "type": "msg_send",
                "http_logs": [
                    {
                        "url": "https://te********",
                        "status_code": 400,
                        "request": "POST https********",
                        "response": "HTTP/2.0 2********",
                        "elapsed_ms": 263,
                        "retries": 0,
                        "created_on": "2022-08-17T14:07:30Z",
                    }
                ],
                "errors": [{"code": "bad_response", "ext_code": "", "message": "response n********", "ref_url": None}],
                "is_error": True,
                "elapsed_ms": 12,
                "created_on": matchers.ISODatetime(),
            },
            log.get_display(anonymize=True, urn=None),
        )

    def test_get_display_timed_out(self):
        channel = self.create_channel(
            "D3C",
            "360Dialog channel",
            address="1234",
            country="BR",
            config={
                Channel.CONFIG_BASE_URL: "https://waba-v2.360dialog.io",
                Channel.CONFIG_AUTH_TOKEN: "123456789",
            },
        )
        contact = self.create_contact("Bob", urns=["whatsapp:75757575"])
        log = self.create_channel_log(
            channel,
            ChannelLog.LOG_TYPE_MSG_SEND,
            http_logs=[
                {
                    "url": "https://waba-v2.360dialog.io/send?to=75757575",
                    "request": 'POST https://waba-v2.360dialog.io/send?to=75757575 HTTP/1.1\r\n\r\n{"to":"75757575"}',
                    "elapsed_ms": 30001,
                    "retries": 0,
                    "created_on": "2022-08-17T14:07:30Z",
                }
            ],
            errors=[{"code": "bad_response", "ext_code": "", "message": "response not right"}],
        )
        msg_out = self.create_outgoing_msg(contact, "Working", channel=channel, status="S", logs=[log])

        self.assertEqual(
            {
                "uuid": str(log.uuid),
                "type": "msg_send",
                "http_logs": [
                    {
                        "url": "https://waba-v2.360dialog.io/send?to=75757575",
                        "request": 'POST https://waba-v2.360dialog.io/send?to=75757575 HTTP/1.1\r\n\r\n{"to":"75757575"}',
                        "elapsed_ms": 30001,
                        "retries": 0,
                        "created_on": "2022-08-17T14:07:30Z",
                    }
                ],
                "errors": [{"code": "bad_response", "ext_code": "", "message": "response not right", "ref_url": None}],
                "is_error": True,
                "elapsed_ms": 12,
                "created_on": matchers.ISODatetime(),
            },
            log.get_display(anonymize=False, urn=msg_out.contact_urn),
        )

        self.assertEqual(
            {
                "uuid": str(log.uuid),
                "type": "msg_send",
                "http_logs": [
                    {
                        "url": "https://waba-v2.360dialog.io/send?to=********",
                        "request": 'POST https://waba-v2.360dialog.io/send?to=******** HTTP/1.1\r\n\r\n{"to":"********"}',
                        "response": "",
                        "elapsed_ms": 30001,
                        "retries": 0,
                        "created_on": "2022-08-17T14:07:30Z",
                    }
                ],
                "errors": [{"code": "bad_response", "ext_code": "", "message": "response n********", "ref_url": None}],
                "is_error": True,
                "elapsed_ms": 12,
                "created_on": matchers.ISODatetime(),
            },
            log.get_display(anonymize=True, urn=msg_out.contact_urn),
        )
