# -*- coding: utf-8 -*-

from . import BaseHandler
import random
import string
from urllib import unquote_plus
from xml.etree import ElementTree as ET
import logging
from tornado.options import options
from autumn.sms import CouponSMSMessage
from autumn.utils import send_email


class Notify(BaseHandler):
    def post(self):
        notify_data = unquote_plus(self.get_argument('notify_data').encode('utf-8'))
        notify_data_xml = ET.fromstring(notify_data)

        status_set = {
            'WAIT_BUYER_PAY': 0,
            'TRADE_CLOSED': 1,
            'TRADE_SUCCESS': 2,
            'TRADE_PENDING': 3,
            'TRADE_FINISHED': 4
        }

        order_id = notify_data_xml.findtext('out_trade_no')
        trade_status = notify_data_xml.findtext('trade_status')

        status = status_set.get(trade_status, -1)

        if status in [2, 4]:
            shipping = self.db.get('select oi.shipping_info_id, oi.goods_id, o.distributor_shop_id, s.sales_id, g.*, '
                                   'o.id oid, oi.id oiid, o.payment, o.order_no, o.mobile, oi.num '
                                   'from orders o, order_item oi, goods g, supplier s '
                                   'where o.id = oi.order_id and oi.goods_id = g.id and g.supplier_id = s.id '
                                   'and o.status = 0 and o.id = %s', order_id)
            if shipping:
                self.db.execute('update orders set paid_at = NOW(), status = 1 where id = %s', order_id)
                if shipping.shipping_info_id:
                    self.db.execute('update order_shipping_info set paid_at = NOW() where id = %s',
                                    shipping.shipping_info_id)

                item_ids = []
                for i in range(shipping.num):
                    item_id = self.db.execute('insert into item(status, goods_name, goods_id, distr_id, distr_shop_id, '
                                              'sp_id, sales_id, order_id, order_item_id, order_no, face_value, payment, '
                                              'sales_price, purchase_price, created_at) '
                                              'values(1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())',
                                              shipping.short_name, shipping.goods_id, options.distributor_id_weixin,
                                              shipping.distributor_shop_id, shipping.supplier_id, shipping.sales_id, shipping.oid,
                                              shipping.oiid, shipping.order_no, shipping.face_value, shipping.payment,
                                              shipping.sales_price, shipping.purchase_price)
                    item_ids.append(item_id)
                # 如果是电子券，生成item_coupon 并发货
                if shipping.type == 'E':
                    # 导入券，获得导入的券号，密码
                    if shipping.generate_type == 'IMPORT':
                        coupon_imported = self.db.query('select * from coupon_imported where goods_id=%s and used=0 '
                                                        'limit %s', shipping.goods_id, shipping.num)
                        # 导入券库存不足，直接返回
                        if len(coupon_imported) < shipping.num:
                            send_email(redis=self.redis,
                                       subject='weixin coupon generation failed:out of stock for imported coupon',
                                       to_list='dev@uhuila.com',
                                       html='order id=%s and goods id=%s' % (shipping.oid, shipping.goods_id))
                            logging.error('imported goods id=%s out of stock' % shipping.goods_id)
                            self.write('success')
                            return

                        imported_ids = [c.id for c in coupon_imported]
                        self.db.execute('update coupon_imported set used=1 where id in (%s)'
                                        % ','.join(['%s']*len(imported_ids)), *imported_ids)
                        coupon_sns = [c.coupon_sn for c in coupon_imported]
                        coupon_pwds = [c.coupon_pwd for c in coupon_imported]

                    # 生成电子券
                    for i in range(int(shipping.num)):
                        if shipping.generate_type == 'IMPORT':
                            coupon_sn = coupon_sns[i]
                            coupon_pwd = coupon_pwds[i]
                        else:
                            coupon_pwd = ''
                            while True:
                                coupon_sn = ''.join([random.choice(string.digits) for z in range(10)])
                                # 没有重复，停止
                                if not self.db.get('select id from item_coupon where sn=%s', coupon_sn):
                                    break
                        item_coupon_field = {
                            'mobile':                   shipping.mobile,
                            'sn':                       coupon_sn,
                            'pwd':                      coupon_pwd,
                            'distr_sn':                 None,
                            'distr_pwd':                None,
                            'sms_sent_count':           0,
                            'expire_at':                shipping.expire_at,
                            'item_id':                  item_ids.pop()
                        }
                        self.db.execute('insert into item_coupon(%s) values (%s)'
                                        % (','.join(item_coupon_field.keys()), ','.join(['%s']*len(item_coupon_field))),
                                        *item_coupon_field.values())

                    # 发送电子券
                    all_order_items = self.db.query('select * from order_item where order_id=%s', order_id)
                    for item in all_order_items:
                        CouponSMSMessage(self.db, self.redis, order_item=item).remark('微商城发送券号短信').send()

                # 删除redis对应的值
                self.redis.delete('o:alipay:%s' % order_id)
                logging.info('order: %s, paid success', order_id)
            else:
                logging.info('order: %s, can not find order', order_id)
        else:
            logging.info('order: %s, paid failed. status: %s', order_id, trade_status)

        self.write('success')