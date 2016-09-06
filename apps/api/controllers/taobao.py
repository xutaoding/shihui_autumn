# -*- coding: utf-8 -*-
import json
import logging
from . import BaseHandler
from autumn.utils import json_hook, PropDict, json_dumps, send_email
from autumn.api.taobao import coupon_sign_params
from autumn.sms import CouponSMSMessage
from tornado.options import options
from autumn.coupon import refund_coupon


class CouponAPI(BaseHandler):
    def get(self):
        self.post()

    def post(self):
        params = PropDict([(name, self.request.arguments[name][0].decode('GBK').encode('utf-8'))
                           for name in self.request.arguments])
        logging.info('taobao coupon order request: %s', json_dumps(params))
        seller_id = params.taobao_sid

        shop = self.db.get('select * from distributor_shop where deleted =0 and taobao_seller_id=%s', seller_id)
        if not shop:
            logging.error('distributor_shop not found. seller_id:%s', seller_id)
            return self.write('{"code":501}')
        shop.taobao_api_info = json.loads(shop.taobao_api_info, object_hook=json_hook)

        if coupon_sign_params(params, shop.taobao_api_info.coupon_service_key.encode('utf-8')) != params.sign:
            logging.error('taobao sign failed: %s %s',
                          coupon_sign_params(params, shop.taobao_api_info.coupon_service_key.encode('utf-8')),
                          params.sign)
            return self.write('{"code":502}')

        order = self.db.get('select * from distributor_order where distributor_shop_id=%s and order_no=%s',
                            shop.id, params.order_id)

        getattr(self, params.method)(params, order)

    def send(self, params, order):
        """ 发码通知  """
        if not order:
            shop = self.db.get('select id from distributor_shop where deleted =0 and '
                               'taobao_seller_id=%s', params.taobao_sid)
            distributor_order_id = self.db.execute(
                'insert into distributor_order(order_no, message, distributor_shop_id, created_at) '
                'values (%s, %s, %s, NOW())',
                params.order_id, json_dumps(params), shop.id)

            self.redis.lpush(options.queue_distributor_order,
                             json_dumps({'distributor_order_id': distributor_order_id,
                                         'distributor': 'TB', 'retry': 0}))
        else:
            self.redis.lpush(options.queue_distributor_order,
                             json_dumps({'distributor_order_id': order.id, 'distributor': 'TB', 'retry': 0}))

        logging.info('taobao coupon send end')
        self.write('{"code":200}')

    def resend(self, params, order):
        """ 重新发码 """
        if not order:
            return self.write('{"code":504}')

        # 按order_item发送券短信
        all_order_items = self.db.query('select * from order_item where order_id=%s', order.order_id)
        for item in all_order_items:
            CouponSMSMessage(self.db, self.redis, order_item=item).remark('淘宝订单短信重发').send()

        logging.info('taobao coupon resend end')
        self.write('{"code":200}')

    def cancel(self, params, order):
        """ 退款 """
        if not order:
            logging.info('taobao order cancel failed. order not found')
            return self.write('{"code":504}')
        refund_num = params.cancel_num
        coupons = self.db.query('select ic.* from item_coupon ic, item i '
                                'where ic.item_id=i.id and i.status=1 and i.order_id=%s limit %s',
                                order.order_id, int(refund_num))

        for coupon in coupons:
            result = refund_coupon(self.db, coupon.sn, 'system', '淘宝接口退款')
            if not result.ok:
                logging.error('taobao refund failed internally for coupon sn %s: %s', coupon.sn, result.msg)
                send_email(redis=self.redis, subject='淘宝接口退款失败',
                           to_list='dev@uhuila.com', html='淘宝订单退款失败coupon_sn: ' % coupon.sn)

        logging.info('taobao coupon cancel end')
        self.write('{"code":200}')

    def modified(self, params, order):
        """ 修改手机号 """
        if not order:
            logging.info('taobao modified failed. order not found')
            return self.write('{"code":504}')

        self.db.execute('update item_coupon ic, item i set ic.mobile=%s '
                        'where ic.item_id=i.id and i.order_id=%s', params.mobile, order.order_id)

        logging.info('taobao coupon modified end')
        self.write('{"code":200}')

    def order_modify(self, params, order):
        """ 订单修改通知 """
        logging.info('taobao coupon order_modify start')
        if not order:
            logging.info('taobao order_modify failed. order not found')
            return self.write('{"code":504}')

        data = json.loads(params.data, object_hook=json_hook)
        if params.sub_method == '1':
            if 'valid_start' in data:
                logging.error('taobao order_modify skip valid_start')

            if 'valid_ends' in data:
                self.db.execute('update item_coupon ic, item i set ic.expire_at=%s '
                                'where ic.item_id=i.id and i.order_id=%s', data.valid_ends, order.order_id)
        elif params.sub_method == '2':
            logging.error('taobao order_modify skip sub_method 2')  # 维权通知

        logging.info('taobao coupon order_modify end')
        self.write('{"code":200}')
