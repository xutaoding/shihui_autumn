# -*- coding: utf-8 -*-
""" 助通短信平台
"""

import urllib
from autumn.api import BaseAPI
from tornado.options import options


class Zhutong(BaseAPI):
    def http_method(self):
        return 'GET'

    def url(self):
        self._fields.update({
            'username': options.ztsms_username,
            'password': options.ztsms_password,
            'productid': options.ztsms_product_id,
        })
        return options.ztsms_gateway_url + '?' + urllib.urlencode(self._fields)

    def parse_response(self, response):
        self.message = response

    def is_ok(self):
        return self.message.startswith('1,')