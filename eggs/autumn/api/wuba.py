# -*- coding: utf-8 -*-
import json
import base64
import urllib
from autumn.api import BaseAPI
from Crypto.Cipher import DES
from tornado.options import options
from autumn.utils import des_padding, des_unpadding
from autumn.utils import json_hook, json_dumps


class Wuba(BaseAPI):
    def __init__(self, method):
        super(Wuba, self).__init__()
        self.method = 'emc.groupbuy.' + method

    def url(self):
        if self.method not in get_methods:
            return options.wuba_gateway_url
        else:
            return options.wuba_gateway_url + '?' + urllib.urlencode(self._fields)

    def http_method(self):
        return 'GET' if self.method in get_methods else 'POST'

    def before_request(self):
        params = {'appid': options.wuba_app_id, 'f': 'json', 'v': '1.0', 'sn': '1'}
        if self.method in get_methods:
            self._fields['m'] = self.method
            self._fields.update(params)
            return

        json_message = json_dumps(self._fields)
        params['m'] = self.method
        if 'request' in encrypt_info[self.method]:
            params['param'] = encrypt(json_message, options.wuba_secret_key)
        else:
            params['param'] = json_message
        self._fields = params

    def parse_response(self, response):
        self.message = json.loads(response, object_hook=json_hook)
        if self.is_ok():
            if 'response' in encrypt_info[self.method]:
                if self.message.data:
                    self.message.data = decrypt(self.message.data, options.wuba_secret_key)
            if self.message.data:
                self.message.data = json.loads(self.message.data, object_hook=json_hook)

    def is_ok(self):
        return 'status' in self.message and self.message.status == 10000


def encrypt(message, secret_key):
    cipher = DES.new(secret_key)
    return urllib.quote(base64.b64encode(cipher.encrypt(des_padding(urllib.quote(message))).encode('hex')))


def decrypt(message, secret_key):
    cipher = DES.new(secret_key)
    return urllib.unquote(des_unpadding(cipher.decrypt(base64.b64decode(urllib.unquote(message)).decode('hex'))))


# 标记需要使用 GET 请求的接口
get_methods = ('emc.groupbuy.queryjiesuan', 'emc.groupbuy.queryrefundjiesuan')

# 标记接口的请求和响应是否需要加密/解密
encrypt_info = {
    'emc.groupbuy.find.allprotype':         (),
    'emc.groupbuy.queryjiesuan':            (),
    'emc.groupbuy.changeinventory':         ('response',),
    'emc.groupbuy.delay':                   ('response',),
    'emc.groupbuy.editgroupbuyinfo':        ('response',),
    'emc.groupbuy.editpartnerbygroupbuy':   ('response',),
    'emc.groupbuy.addgroupbuy':             ('response',),
    'emc.groupbuy.xiaxian':                 ('request', 'response'),
    'emc.groupbuy.shangxian':               ('request', 'response'),
    'emc.groupbuy.getstatus':               ('request', 'response'),
    'emc.groupbuy.order.ticketcheck':       ('request', 'response'),
    'emc.groupbuy.ticket.findinfo.bycreatetime':       ('request', 'response'),
    'emc.groupbuy.ticket.findinfo.byid':       ('request', 'response'),
}