# -*- coding: utf-8 -*-
import json
from autumn.api import BaseAPI
from datetime import datetime
from tornado.options import options
from HTMLParser import HTMLParser


class Baidu(BaseAPI):
    def __init__(self, method):
        super(Baidu, self).__init__()
        self.method = method

    def http_method(self):
        return 'POST'

    def url(self):
        return options.baidu_gateway_url + self.method

    def before_request(self):
        self._fields = {
            'auth': json.dumps({'token': options.baidu_token, 'userName': options.baidu_user_name}),
            'data': json.dumps(self._fields),
        }

    def parse_response(self, response):
        self.message = json.loads(HTMLParser().unescape(response))

    def is_ok(self):
        return self.message['code'] == 0


def sign():
    return datetime.now().strftime('%Y_%m_%d_%H_Bootstrap')