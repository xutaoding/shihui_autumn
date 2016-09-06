# -*- coding: utf-8 -*-

from .. import BaseHandler
from tornado.web import authenticated
from tornado.options import options
from autumn.api.alipay import sign
import urllib


class Pay(BaseHandler):
    @authenticated
    def get(self):
        self.render('pay/pay.html')

    @authenticated
    def post(self):
        fee = 0.01
        subject = 'very nice goods'
        order_no = '20140402174256'

        params = dict(
            payment_type='1',
            show_url='http://www.yibaiquan.com',
            total_fee=fee,
            subject=subject,
            out_trade_no=order_no,

            service='create_direct_pay_by_user',
            partner=options.alipay_partner,
            return_url=options.alipay_return_url,
            notify_url=options.alipay_notify_url,
            seller_email=options.alipay_seller_email,
            _input_charset=options.alipay_input_charset,
        )
        alipay_sign = sign(params, options.alipay_secret_key)
        package = urllib.urlencode(dict(sorted(params.iteritems(), key=lambda d: d[0]))) + '&sign=' + alipay_sign

        url = '%s' % options.alipay_gateway_url + '?' + package
        self.redirect(url)
