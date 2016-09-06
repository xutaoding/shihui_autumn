# -*- coding: utf-8 -*-

"""
参数 params 构成：
{
    'cookie': 'aldasld',
    'distributor_shop_id': 123,
    'goods_keys':{
        'name_key': 123,
        'name_key2': 223
    }
}
"""
import re
from tornado.httputil import url_concat
from autumn.api import BaseAPI
from autumn.utils import PropDict, mix_str


class LashouBrowser(BaseAPI):
    """拉手模拟验证api"""
    def __init__(self, method, params):
        super(LashouBrowser, self).__init__()
        self.method = method
        self.params = params
        self.error = PropDict()

    def http_method(self):
        return 'GET'

    def url(self):
        return url_concat(urls[self.method], self._fields)

    def headers(self):
        return {
            'Cookie': self.params.cookie,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/34.0.1847.116 Safari/537.36',
        }

    def parse_response(self, response):
        if self.method == 'verify':
            self.message = response

    def is_ok(self):
        if self.method == 'verify':
            ok = '<strong>验证成功提示</strong>' in self.message
            msg = '验证失败，该券已被验证' if '被消费验证' in self.message else '验证失败，无效的拉手券密码'
            if not ok:
                self.error = PropDict(
                    coupon_sn=self._fields['password'],
                    msg=msg
                )
            return ok

    def find_order_info(self):
        for key in self.params.goods_keys:
            ptn = re.compile(""".*<strong>商品ID：</strong>(\d+).*""")
            lashou_id = re.match(ptn, self.message.replace('\n', ''))
            if lashou_id and str(lashou_id.groups()[0]) == key:
                sn = re.compile(""".*>券号：</strong>(\d+).*""")
                lashou_sn = re.match(sn, self.message.replace('\n', '')).groups()[0]
                pwd = re.compile(""".*<strong>密码：</strong>(\d+).*""")
                lashou_pwd = re.match(pwd, self.message.replace('\n', '')).groups()[0]
                return PropDict(goods_id=self.params.goods_keys[key],
                                coupon_sn=lashou_sn,
                                coupon_pwd=lashou_pwd,
                                distributor_shop_id=self.params.distributor_shop_id)
        return None


urls = {
    'verify': 'http://sp.lashou.com/new_index.php'
}