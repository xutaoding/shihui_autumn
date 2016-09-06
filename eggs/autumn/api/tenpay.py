# -*- coding: utf-8 -*-

from . import BaseAPI
from tornado.options import options
from tornado.httputil import url_concat
import hashlib
import urllib


class TenPay(BaseAPI):
    """财付通支付、查询"""
    def __init__(self, method):
        super(TenPay, self).__init__()
        self.method = method

    def http_method(self):
        return 'POST'

    def url(self):
        print '%s/%s' % (options.tenpay_gateway_url, method_dict[self.method]) + '?' + self.package
        return '%s/%s' % (options.tenpay_gateway_url, method_dict[self.method]) + '?' + self.package

    def parse_response(self, response):
        self.message = response

    def is_ok(self):
        return self.message == 'success'

    def package_create(self, fee, order_no, subject):
        params = dict(
            bank_type='DEFAULT',
            fee_type=1,
            body='测试能否搞得通流程',
            subject=subject,
            input_charset=options.tenpay_input_charset,
            partner=1900000113,
            total_fee=fee,
            spbill_create_ip='127.0.0.1',
            out_trade_no=order_no,
            notify_url=options.tenpay_notify_url,
            return_url=options.tenpay_return_url
        )
        content = '&'.join(['%s=%s' % (key, params[key]) for key in sorted(params.keys())])
        sign = hashlib.md5(content + '&key=' + options.tenpay_secret_key).hexdigest().upper()
        package = urllib.urlencode(dict(sorted(params.iteritems(), key=lambda d: d[0]))) + '&sign=' + sign

        self.package = package


method_dict = {
    'pay': 'pay.html',
    'verify': 'simpleverifynotifyid.xml'
}

