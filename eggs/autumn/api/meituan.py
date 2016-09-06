# -*- coding: utf-8 -*-
"""
参数 params 构成：
{
    'login': 'SHPONY',
    'password': '123456',
    'cookie': 'aldasld',
    'poiid': '12312',
    'distributor_shop_id': 123,
    'goods_keys':{
        'name_key': 123,
        'name_key2': 223
    }
}
"""

import json
from . import BaseAPI
from autumn.utils import json_hook, PropDict, mix_str


class MeituanBrowser(BaseAPI):
    def __init__(self, method, params):
        super(MeituanBrowser, self).__init__()
        self.method = method
        self.params = params
        self.error = PropDict()

    def http_method(self):
        return 'POST'

    def url(self):
        return urls[self.method]

    def headers(self):
        h = {
            'Cookie': self.params.cookie,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/34.0.1847.116 Safari/537.36',
        }
        if self.method == 'verify':
            h['X-Requested-With'] = 'XMLHttpRequest'
        return h

    # def before_request(self):
    #     if self.method == 'verify':
    #         self.add_field('from', 'batchVerify')
    #         self.add_field('isAjax', True)

    def parse_response(self, response):
        if self.method == 'verify':
            self.message = json.loads(response, object_hook=json_hook)

    def is_ok(self):
        if self.method == 'verify':
            ok = self.message.status == 1
            if not ok:
                self.error = PropDict(
                    coupon_sn=mix_str(self.message.data.code),
                    msg=(mix_str(self.message.data.errmsg))
                )
            return ok

    def find_order_info(self):
        for key in self.params.goods_keys:
            if self.message.data.dealtitle.encode('utf-8').find(key) >= 0:
                return PropDict(goods_id=self.params.goods_keys[key],
                                coupon_sn=str(self.message.data.code),
                                distributor_shop_id=self.params.distributor_shop_id)
        return None
urls = {
    'verify': 'http://e.meituan.com/coupon/singleconsume',
}
