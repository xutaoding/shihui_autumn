# -*- coding: utf-8 -*-
import logging
from autumn.utils import json_hook, send_email
from . import BaseHandler
from decimal import Decimal
from xml.etree import ElementTree
from tornado.options import options
from autumn.api.jingdong import JdToUs
from autumn.sms import CouponSMSMessage
from autumn.order import new_distributor_order, new_distributor_item
import json
from autumn.coupon import refund_coupon
import itertools


class SendOrder(BaseHandler):
    def get(self):
        self.write('ok')

    def post(self):
        self.set_header('Content-Type', 'application/xml; charset=UTF-8')

        # 解析京东请求
        logging.info('jingdong api. send_order %s', self.request.body)
        request = JdToUs(self.request.body)
        distr_shop = self.db.get('select id, taobao_api_info from distributor_shop '
                                 'where distributor_id=%s and taobao_seller_id=%s',
                                 options.distributor_id_jingdong, request.vender_id)

        api_info = json.loads(distr_shop.taobao_api_info, object_hook=json_hook)
        request.set_key(api_info.vender_key, api_info.secret_key)
        request.parse()

        # 查找分销订单
        jd_order_id = request.message.findtext('JdOrderId')
        order = self.db.get('select * from distributor_order where '
                            'distributor_shop_id=%s and order_no=%s',
                            distr_shop.id, jd_order_id)
        order_message = ElementTree.tostring(request.message, encoding='utf-8', method='xml')
        logging.info('jingdong api. send_order decrypted %s', order_message)

        if order:
            return self.write(request.response('send_order', 212, 'the order has been processed'))
        else:
            # 保存分销订单信息
            distributor_order_id = self.db.execute(
                'insert into distributor_order(order_no, message, distributor_shop_id, created_at) '
                'values (%s, %s, %s, NOW())',
                jd_order_id, order_message, distr_shop.id)

        count = int(request.message.findtext('Count'))
        goods_link_id = request.message.findtext('VenderTeamId')
        order_amount = Decimal(request.message.findtext('Origin'))/100
        sales_price = Decimal(request.message.findtext('TeamPrice'))/100
        jd_goods_id = request.message.findtext('JdTeamId')
        mobile = request.message.findtext('Mobile')

        jd_coupons = [{'coupon_sn': c.findtext('CouponId'), 'coupon_pwd': c.findtext('CouponPwd')}
                      for c in request.message.findall('Coupons/Coupon')]

        # 找到关联的商品
        goods_info = self.db.get('select g.* from goods g, goods_distributor_shop gds '
                                 'where g.id = gds.goods_id and distributor_shop_id=%s and goods_link_id=%s',
                                 distr_shop.id, goods_link_id)
        if not goods_info and int(goods_link_id) < 20000:
            goods_info = self.db.get('select g.* from goods g where g.type="E" and g.id=%s', goods_link_id)

        if not goods_info:
            self.write(request.response('send_order', 213, 'goods not found'))
            return

        order_id, order_no = new_distributor_order(self.db, distr_shop.id, order_amount, order_amount, mobile)
        result = new_distributor_item(self.db, order_id, order_no, sales_price, count, goods_info,
                                      mobile, distr_shop.id, jd_goods_id, jd_coupons, False)

        if not result.ok:
            self.write(request.response('send_order', 213, result.msg))
            return
        else:
            self.db.execute('update orders set distributor_order_id=%s where id = %s',
                            distributor_order_id, result.order_id)
            self.db.execute('update distributor_order set order_id=%s where id = %s',
                            result.order_id, distributor_order_id)

        ## 按order_item发送券短信
        #all_order_items = self.db.query('select * from order_item where order_id=%s', order_id)
        #for item in all_order_items:
        #    CouponSMSMessage(self.db, self.redis, order_item=item).remark('京东订单短信发送').send()

        query_coupons = self.db.query('select ic.sn, ic.distr_sn from item_coupon ic, item i '
                                      'where ic.item_id=i.id and i.order_id=%s', order_id)
        result_coupon = []
        for jd_coupon in jd_coupons:
            for query_coupon in query_coupons:
                if query_coupon.distr_sn == jd_coupon['coupon_sn']:
                    result_coupon.append(query_coupon.sn)
                    break

        self.write(request.response('send_order', 200, 'ok',
                                    jd_team_id=jd_goods_id, vender_team_id=goods_link_id,
                                    sell_count=count, vender_order_id=order_no, coupons=result_coupon))


class SellCount(BaseHandler):
    def get(self):
        self.write('ok')

    def post(self):
        self.set_header('Content-Type', 'application/xml; charset=UTF-8')

        # 解析京东请求
        logging.info('jingdong api. sell_count %s', self.request.body)
        request = JdToUs(self.request.body)
        distr_shop = self.db.get('select id, taobao_api_info from distributor_shop '
                                 'where distributor_id=%s and taobao_seller_id=%s',
                                 options.distributor_id_jingdong, request.vender_id)

        api_info = json.loads(distr_shop.taobao_api_info, object_hook=json_hook)
        request.set_key(api_info.vender_key, api_info.secret_key)
        request.parse()

        logging.info('jingdong api. sell_count decrypted %s',
                     ElementTree.tostring(request.message, encoding='utf-8', method='xml'))

        goods_link_id = request.message.findtext('VenderTeamId')
        # 找到关联的商品
        goods_info = self.db.get(
            'select g.sales_count,g.virtual_sales_count from goods g, goods_distributor_shop gds '
            'where g.id = gds.goods_id and distributor_shop_id=%s and goods_link_id=%s',
            distr_shop.id, goods_link_id)
        if not goods_info and int(goods_link_id) < 20000:
            goods_info = self.db.get('select g.sales_count,g.virtual_sales_count '
                                     'from goods g where g.type="E" and g.id=%s', goods_link_id)
        if not goods_info:
            logging.info('jingdong query sell_count failed: goods not found.')
            return self.write(request.response('sell_count', 202, 'goods not found'))

        return self.write(request.response('sell_count', 200, 'ok',
                                           vender_team_id=goods_link_id,
                                           sell_count=max(goods_info.sales_count, goods_info.virtual_sales_count)))


class OrderRefund(BaseHandler):
    def get(self):
        self.write('ok')

    def post(self):
        self.set_header('Content-Type', 'application/xml; charset=UTF-8')

        # 解析京东请求
        logging.info('jingdong api. order_refund %s', self.request.body)
        request = JdToUs(self.request.body)
        distr_shop = self.db.get('select id, taobao_api_info from distributor_shop '
                                 'where distributor_id=%s and taobao_seller_id=%s',
                                 options.distributor_id_jingdong, request.vender_id)

        api_info = json.loads(distr_shop.taobao_api_info, object_hook=json_hook)
        request.set_key(api_info.vender_key, api_info.secret_key)
        request.parse()

        logging.info('jingdong api. order_refund decrypted %s',
                     ElementTree.tostring(request.message, encoding='utf-8', method='xml'))

        jd_order_id = request.message.findtext('JdOrderId')
        vender_order_id = request.message.findtext('VenderOrderId')
        coupons = self.db.query('select ic.* from item_coupon ic, item i '
                                'where i.status=1 and ic.item_id = i.id and i.order_no=%s', vender_order_id)
        tobe_refund = [e.text for e in request.message.findall('Coupons/Coupon')]
        refunded_coupons = []
        for coupon in coupons:
            if coupon.distr_sn in tobe_refund:
                result = refund_coupon(self.db, coupon.sn, '系统', '京东请求退款')
                if result.ok:
                    refunded_coupons.append(coupon.distr_sn)
                else:
                    logging.error('jingdong api. refund failed %s', coupon.sn)

        self.write(request.response('order_refund', 200, 'ok',
                                    jd_order_id=jd_order_id, vender_order_id=vender_order_id, coupons=refunded_coupons))


class SendSms(BaseHandler):
    def get(self):
        self.write('ok')

    def post(self):
        self.set_header('Content-Type', 'application/xml; charset=UTF-8')

        # 解析京东请求
        logging.info('jingdong api. send_sms %s', self.request.body)
        request = JdToUs(self.request.body)
        distr_shop = self.db.get('select id, taobao_api_info from distributor_shop '
                                 'where distributor_id=%s and taobao_seller_id=%s',
                                 options.distributor_id_jingdong, request.vender_id)

        api_info = json.loads(distr_shop.taobao_api_info, object_hook=json_hook)
        request.set_key(api_info.vender_key, api_info.secret_key)
        request.parse()

        logging.info('jingdong api. send_sms decrypted %s',
                     ElementTree.tostring(request.message, encoding='utf-8', method='xml'))

        mobile = request.message.findtext('Mobile')
        vender_coupon_id = request.message.findtext('VenderCouponId')
        jd_coupon_id = request.message.findtext('JdCouponId')
        coupon = self.db.get('select *, c.id as cid from item i, item_coupon c where i.id=c.item_id and sn=%s', vender_coupon_id)
        logging.info('JD-coupon:%s' % coupon)
        CouponSMSMessage(self.db, self.redis, coupon=coupon).mobile(mobile).remark('京东请求重发').send()

        self.write(request.response('send_sms', 200, 'ok',
                                    mobile=mobile, vender_coupon_id=vender_coupon_id, jd_coupon_id=jd_coupon_id))


class PushOrder(BaseHandler):
    """京东分销订单接收接口"""
    def get(self):
        self.write('ok')

    def post(self):
        self.set_header('Content-Type', 'application/xml; charset=UTF-8')

        logging.info('jingdong api. push_order %s', self.request.body)
        request = JdToUs(self.request.body)
        request.set_key(options.jingdong_fx_vender_key, options.jingdong_fx_secret_key)
        request.parse()


        logging.info('jingdong api. push_order decrypted %s',
                     ElementTree.tostring(request.message, encoding='utf-8', method='xml'))

        # 获得JD TEAM ID
        jd_team_id = request.message.findtext('JdTeamId')
        jd_order_id = request.message.findtext('JdOrderId')
        goods_id = self.db.get('select goods_id from goods_property where name="jd_team_id" and value=%s',
                               jd_team_id).goods_id
        # 没找到对应我们的商品ID, 发邮件
        if not goods_id:
            logging.error('jd push order failed: can not find internal goods_id for jd_team_id=%s', jd_team_id)
            send_email(redis=self.redis, subject='京东分销订单接收失败',
                       to_list='dev@uhuila.com',
                       html='京东分销订单接收失败, 没有对应内部商品, 京东商品id=%s,订单id=%s' % (jd_team_id, jd_order_id))
            return self.write(request.response('push_order', 200, 'ok'))

        jd_coupons = [{'coupon_sn': c.findtext('CouponId'), 'coupon_pwd': c.findtext('CouponPwd')}
                      for c in request.message.findall('Coupons/Coupon')]
        # 没找到券号，密码
        if not jd_coupons:
            logging.error('jd push order failed: can not find valid coupons for jd_team_id=%s', jd_team_id)
            return self.write(request.response('push_order', 200, 'no coupons found in request'))

        count = request.message.findtext('Count')

        try:
            # 插入导入券
            values = ','.join(['(%s, %s, %s, 0, NOW())'] * int(count))
            self.db.execute('insert into coupon_imported (goods_id, coupon_sn, coupon_pwd, used, created_at) '
                            'values %s' % values,
                            *list(itertools.chain(*[(goods_id, jd_coupon['coupon_sn'], jd_coupon['coupon_pwd'])
                                                    for jd_coupon in jd_coupons])))
        except Exception:
            logging.error('jd push order failed: insert into coupon_imported failed for jd_order_id=%s', jd_order_id)
            send_email(redis=self.redis, subject='京东分销订单接收失败',
                       to_list='dev@uhuila.com',
                       html='京东分销订单接收失败, 数据库插入导入券失败, 京东商品id=%s,订单id=%s' % (jd_team_id, jd_order_id))
            return self.write(request.response('push_order', 200, 'ok'))

        # 更新库存
        self.db.execute('update goods set stock=stock+%s where goods.id=%s', int(count), goods_id)
        logging.info('jd push order successfully received, jd_order_id: %s', jd_order_id)
        return self.write(request.response('push_order', 200, 'ok'))
