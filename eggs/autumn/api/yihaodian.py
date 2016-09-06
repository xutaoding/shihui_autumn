# -*- coding: utf-8 -*-
import hashlib
import xml.etree.ElementTree as ET
from autumn.api import BaseAPI
from tornado.options import options
from datetime import datetime


class Yihaodian(BaseAPI):
    def __init__(self, method):
        super(Yihaodian, self).__init__()
        self._fields['method'] = method

    def before_request(self):
        self._fields.update({
            'appKey':       options.yhd_app_key,
            'timestamp':    str(datetime.now()),
            'sessionKey':   options.yhd_app_session,
            'erp':          'self',
            'erpVer':       '1.0',
            'format':       'xml',
            'ver':          '1.0',
        })
        self.add_field('sign', sign(self._fields, options.yhd_app_secret))

    def url(self):
        return options.yhd_gateway_url

    def http_method(self):
        return 'POST'

    def parse_response(self, response):
        # element object: xml root
        self.message = ET.fromstring(response)

    def is_ok(self):
        return self.message.find('errorCount').text == '0'


def sign(params, secret_key):
    content = '{0}{1}{0}'.format(
        secret_key,
        ''.join(['%s%s' % (key, params[key]) for key in sorted(params.keys())])
    )
    return hashlib.new('md5', content).hexdigest()
