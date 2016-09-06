# -*- coding: utf-8 -*-
"""
淘宝开放平台、淘宝电子凭证
"""

import hashlib
import time
import urllib
import json
from autumn.api import BaseAPI
from autumn.utils import json_hook
from tornado.options import options


class Taobao(BaseAPI):
    def __init__(self, method):
        super(Taobao, self).__init__()
        self.method = method
        self.session = None

    def http_method(self):
        return 'POST'

    def url(self):
        params = {
            'v':            '2.0',
            'format':       'json',
            'sign_method':  'md5',
            'partner_id':   'likang',
            'app_key':      self.app_key,
            'method':       self.method,
            'timestamp':    str(long(time.time() * 1000)),
        }
        if self.session:
            params['session'] = self.session

        sign_params = params.copy()
        sign_params.update(self._fields)
        params['sign'] = top_sign_params(sign_params, self.app_secret)
        return options.taobao_gateway_url + '?' + urllib.urlencode(params)

    def headers(self):
        return {
            'Cache-Control': 'no-cache',
            'Connection': 'Keep-Alive',
        }

    def set_session(self, session):
        self.session = session.encode('utf-8') if isinstance(session, unicode) else session

    def set_app_info(self, app_key, app_secret):
        self.app_key = app_key.encode('utf-8') if isinstance(app_key, unicode) else app_key
        self.app_secret = app_secret.encode('utf-8') if isinstance(app_secret, unicode) else app_secret

    def before_request(self):
        for name in self._fields.keys():
            self._fields[name.replace('__', '.')] = self._fields.pop(name)

    def parse_response(self, response):
        message = json.loads(response, object_hook=json_hook)
        if 'error_response' in message:
            self.error = message.error_response
            self.message = None
        else:
            self.error = None
            if self.method.startswith('taobao.'):
                key = self.method[7:].replace('.', '_') + '_response'
            else:
                key = self.method.replace('.', '_') + '_response'
            self.message = message[key]

    def is_ok(self):
        return self.message is not None


def top_sign_params(params, secret_key):
    secret_key = secret_key.encode('utf-8') if isinstance(secret_key, unicode) else secret_key
    content = '{0}{1}{0}'.format(secret_key, ''.join('%s%s' % (key, params[key]) for key in sorted(params.keys())))
    return hashlib.md5(content).hexdigest().upper()


def coupon_sign_params(params, serviceKey):
    """ 淘宝电子凭证生成签名字符串，所有参数都应该是utf-8的
    对于以下参数：
        method = 'send'
        order_id = 'aabbcc'
        taobao_sid = '828005208'
        a = u'你好'.encode('utf-8')
    所对应的sign应该为:
        sign=E7F9E77D4960620B96F7125E8EA7499A
    """
    signStr = serviceKey
    for key in sorted(params.keys()):
        value = params[key]
        if key != 'sign' and value:
            signStr = signStr + key + value

    return hashlib.new("md5", signStr.decode('utf-8').encode('GBK')).hexdigest().upper()