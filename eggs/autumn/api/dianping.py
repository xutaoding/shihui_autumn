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
注意：name_key:对应点评上的商品名称的一部分
"""

from . import BaseAPI
import time
import json
from autumn.utils import json_hook, PropDict, mix_str


class DianpingBrowser(BaseAPI):
    def __init__(self, method, params):
        super(DianpingBrowser, self).__init__()
        self.method = method
        self.params = params
        self.error = []

    def http_method(self):
        return 'POST'

    def url(self):
        return urls[self.method]

    def headers(self):
        return {
            'Cookie': self.params.cookie,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/34.0.1847.116 Safari/537.36',
        }

    def before_request(self):
        if self.method == 'verify':
            self.add_fields(receiptId=0, t='m%s' % int(time.time()))

    def parse_response(self, response):
        if self.method == 'verify':
            self.message = json.loads(response, object_hook=json_hook)

    def is_ok(self):
        if self.method == 'verify':
            result = self.message.msg.serialNumList
            for i in result:
                if i.result.code != 200:
                    self.error.append(PropDict(
                        coupon_sn=mix_str(i.serialNum),
                        msg=mix_str(i.result.msg.message)
                    ))
            return any([i.result.code == 200 for i in result])

    def find_order_info(self):
        results = []
        for i in self.message.msg.serialNumList:
            # 只有code 是200 的才有receiptList
            if i.result.code == 200:
                for receipt in i.result.msg.receiptList:
                    for key in self.params.goods_keys:
                        if receipt.dealSMSName.encode('utf-8').find(key) >= 0:
                            results.append(PropDict(goods_id=self.params.goods_keys[key],
                                                    coupon_sn=receipt.serialNum.replace(' ', ''),
                                                    distributor_shop_id=self.params.distributor_shop_id))
        return results

urls = {
    'verify': 'http://e.dianping.com/tuangou/ajax/batchverify',
}
