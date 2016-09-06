# -*- coding: utf-8 -*-
"""
参数 params 构成：
{
    'cookie': 'aldasld',
    'distributor_shop_id': 123,
    'emailOrMobile': 'shihui88@y.com',
    'password': '123456789',
    'goods_keys':{
        'name_key': 123,
        'name_key2': 223
    }
}
"""

from . import BaseAPI
import json
import logging
from autumn.utils import json_hook, PropDict, mix_str


class NuomiBrowser(BaseAPI):
    def __init__(self, method, params):
        super(NuomiBrowser, self).__init__()
        self.method = method
        self.params = params
        self.error = PropDict()

    def http_method(self):
        return 'POST'

    def url(self):
        if self.method == 'verify':
            return urls[self.method] % self._fields['code']
        return urls[self.method]

    def headers(self):
        return {
            'Cookie': self.params.cookie,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/34.0.1847.116 Safari/537.36',
        }

    def build_body(self):
        if self.method == 'verify':
            return ''
        return super(NuomiBrowser, self).build_body()

    def parse_response(self, response):
        if self.method == 'verify':
            self.message = json.loads(response, object_hook=json_hook)

    def is_ok(self):
        if self.method == 'verify':
            ok = self.message.data.isSuccess
            if not ok:
                self.error = PropDict(
                    coupon_sn=mix_str(self.message.data.siteCode),
                    msg=mix_str(self.message.data.message).replace('糯米','')
                )
            return ok

    def find_order_info(self):
        logging.info('nuomi self.message: %s', self.message)
        for key in self.params.goods_keys:
            if self.message.data.dealName.encode('utf-8').find(key) >= 0:
                return PropDict(goods_id=self.params.goods_keys[key],
                                coupon_sn=mix_str(self.message.data.siteCode),
                                distributor_shop_id=self.params.distributor_shop_id)
        return None


urls = {
    'verify': 'http://y.nuomi.com/coupon/%s/deals/confirm',
}
