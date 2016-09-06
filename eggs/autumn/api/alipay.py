# -*- coding: utf-8 -*-
import hashlib
from autumn.api import BaseAPI
from tornado.options import options
import urllib2
import urllib
from xml.etree import ElementTree as ET


class AlipayNotify(BaseAPI):
    """ 校验即时到账支付通知 """
    def __init__(self, notify_id):
        super(AlipayNotify, self).__init__()
        self.notify_id = notify_id

    def http_method(self):
        return 'GET'

    def url(self):
        return '%s?partner=%s&notify_id=%s' % (options.alipay_verify_url, options.alipay_partner, self.notify_id)

    def parse_response(self, response):
        self.message = response

    def is_ok(self):
        return self.message == 'true'


def sign(params, secret_key):
    content = '&'.join(['%s=%s' % (key, params[key]) for key in sorted(params.keys())
                        if key not in ('sign', 'sign_type') and params[key]])
    return hashlib.md5(content + secret_key).hexdigest()


def build_form(order_no, subject, fee):
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
    params['sign'] = sign(params, options.alipay_secret_key)
    params['sign_type'] = 'MD5'

    form = """
    <form id="alipay" name="alipay" action="%s" method="GET">
        %s
        <input type="submit" value="提交" style="display:none">
    </form>
    <script>document.forms["alipay"].submit();</script>"""
    return form % (
        options.alipay_gateway_url,
        ''.join(['<input type="hidden" name="%s" value="%s"/>' % (key, params[key]) for key in params])
    )


def build_token_req_data(db, sp_id, goods_id, num, out_trade_no, call_back_url, merchant_url, wx_id):
    req_data = '<direct_trade_create_req>' \
               '<subject>%s</subject>' \
               '<out_trade_no>%s</out_trade_no>' \
               '<total_fee>%s</total_fee>' \
               '<seller_account_name>%s</seller_account_name>' \
               '<call_back_url>%s</call_back_url>' \
               '<notify_url>%s</notify_url>' \
               '<out_user>%s</out_user>' \
               '<merchant_url>%s</merchant_url>' \
               '<pay_expire>120</pay_expire>' \
               '</direct_trade_create_req>'
    goods = db.get('select short_name, sales_price from goods g, goods_property gp '
                   'where gp.name = "is_wx_goods" and gp.value = 1 and g.id = %s and g.supplier_id = %s limit 1',
                   goods_id, sp_id)
    total_fee = float(goods.sales_price) * num
    req_data = req_data % (goods.short_name, out_trade_no, total_fee, options.alipay_seller_email, call_back_url,
                           options.alipay_wap_notify_url, wx_id, merchant_url)

    return req_data


def build_pay_req_data(token):
    req_data = '<auth_and_execute_req><request_token>%s</request_token></auth_and_execute_req>' % token

    return req_data


def build_request(operator, req_data, req_id=''):
    params = dict(
        format='xml',
        v='2.0',
        partner=options.alipay_partner,
        sec_id='MD5',
        req_data=req_data
    )

    if operator == 'token':
        params.update({'req_id': req_id, 'service': 'alipay.wap.trade.create.direct'})
    elif operator == 'pay':
        params.update({'service': 'alipay.wap.auth.authAndExecute'})
    else:
        pass

    content = '&'.join(['%s=%s' % (key, params[key]) for key in sorted(params.keys())])
    sign = hashlib.md5(content + options.alipay_secret_key).hexdigest()
    url = options.alipay_wap_gateway_url + '?' + content + '&sign=' + sign

    if operator == 'token':
        result = urllib.unquote_plus(urllib2.urlopen(url).read())

        result_dict = dict([i.split('=', 1) for i in result.split('&')])

        if 'res_error' in result_dict.keys():
            error_tree = ET.fromstring(result_dict['res_error'])
            return {'result': False, 'detail': error_tree.findtext('detail')}
        else:
            token_tree = ET.fromstring(result_dict['res_data'])
            return {'result': True, 'token': token_tree.findtext('request_token')}
    elif operator == 'pay':
        return url
    else:
        return ''
