# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from temba.utils.access_token import APIClient


class WeChatClient(APIClient):
    API_NAME = 'WeChat'
    API_SLUG = 'wechat'
    TOKEN_URL = 'https://api.weixin.qq.com/cgi-bin/token'
