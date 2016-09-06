# -*- coding: utf-8 -*-

from . import BaseHandler
from autumn.utils import json_hook, json_dumps
from autumn.order import new_distributor_order, new_distributor_item
from autumn.api.wuba import decrypt, encrypt
from autumn.coupon import refund_coupon
from autumn.sms import CouponSMSMessage
from autumn import const
from tornado.options import options
from decimal import Decimal
from datetime import datetime
import logging
import json
import re


class NewOrder(BaseHandler):
    """处理58新订单"""
    def get(self):
        self.post()

    def post(self):

        # 解密58请求参数
        json_text = decrypt(self.get_argument('param'), options.wuba_secret_key)  # '2a6f8f2c')#
        params = json.loads(json_text, object_hook=json_hook)
        logging.info('wuba new order request : %s', json_dumps(params))

        # 获得参数
        try:
            wuba_order_no = params.orderId                      # 58 订单号
            sales_price = Decimal(params.prodPrice)             # 商品售价
            product_count = int(params.prodCount)               # 购买数量
            mobile = params.mobile                              # 订单券号接受手机号
            goods_link_id = int(params.groupbuyIdThirdpart)     # 伪商品ID
        except AttributeError:
            logging.info('wuba request failed: wrong params')
            return self.write('{"status":"10201", "msg": "参数解析错误"}')

        # 检查参数格式
        if int(product_count) <= 0 or sales_price.compare(Decimal(0)) < 0 or not check_phone(mobile):
            logging.info('wuba request failed: invalid params')
            return self.write('{"status":"20210", "msg": "输入参数错误"}')

        # 查找分销订单
        wuba_order = self.db.get('select * from distributor_order where '
                                 'distributor_shop_id=%s and order_no=%s',
                                 options.shop_id_wuba, wuba_order_no)

        if wuba_order:
            # 分销订单重复
            logging.info('wuba request failed: duplicated wuba order no')
            return self.write('{"status":"10100", "msg": "订单已存在"}')
        else:
            # 分销订单不存在， 生成分销订单
            distributor_order_id = self.db.execute(
                'insert into distributor_order(order_no, message, distributor_shop_id, created_at) '
                'values (%s, %s, %s, NOW())',
                wuba_order_no, json_text, options.shop_id_wuba)
            #放入处理队列
            self.redis.lpush(options.queue_distributor_failed_order, "%s-%s" % (wuba_order_no, goods_link_id))

        # 根据伪商品找到关联的商品
        goods_info = self.db.get('select g.* from goods g, goods_distributor_shop gds '
                                 'where g.id = gds.goods_id and distributor_shop_id=%s and goods_link_id=%s',
                                 options.shop_id_wuba, goods_link_id)
        # 如果商品不存在，根据真实商品ID查找
        if not goods_info and goods_link_id < 20000:
            goods_info = self.db.get('select g.* from goods g where g.type="E" and g.id=%s', goods_link_id)
        # 商品不存在， 返回错误信息
        if not goods_info:
            logging.info('wuba request failed: can not find goods')
            return self.write('{"status":"10100", "msg": "未找到商品"}')
        
        # 生成订单
        order_id, order_no = new_distributor_order(self.db, options.shop_id_wuba,
                                                   sales_price*product_count, sales_price*product_count, mobile)
        result = new_distributor_item(self.db, order_id, order_no, sales_price, product_count, goods_info,
                                      mobile, options.shop_id_wuba, "", [], False)

        if not result.ok:
            # 生成订单失败，返回
            logging.info('wuba request failed: generate order failed msg %s' % result.msg)
            return self.write('{"status":"10100", "msg": %s}' % result.msg)
        else:
            # 生成订单成功，更新id
            self.db.execute('update orders set distributor_order_id=%s where id = %s',
                            distributor_order_id, result.order_id)
            self.db.execute('update distributor_order set order_id=%s where id = %s',
                            result.order_id, distributor_order_id)
            # 从处理队列移除
            self.redis.lrem(options.queue_distributor_failed_order, 0, "%s-%s" % (wuba_order_no, goods_link_id))

        # 发送短信
        all_order_items = self.db.query('select * from order_item where order_id=%s', order_id)
        for item in all_order_items:
            CouponSMSMessage(self.db, self.redis, order_item=item).remark('58订单短信发送').send()

        tickets = []
        # 添加券信息到需要返回的tickets
        for coupon in result.coupons:
            coupon_sn = coupon['coupon_sn']
            created_at = self.db.get('select * from item i, item_coupon c where i.id=c.item_id and c.sn=%s', coupon_sn).created_at
            ticket = {
                "ticketId": int(coupon['id']),
                "ticketCode": str(coupon_sn),
                "ticketCount": 1,
                "createTime": str(created_at),
                "endTime": str(goods_info.expire_at),
            }
            tickets.append(ticket)

        # 生成合法的json返回
        data = {'orderId': wuba_order_no, 'orderIdThirdpart': order_no, 'tickets': tickets}
        result_json = {'status': '10000', 'msg': 'ok', 'data': encrypt(str(data), options.wuba_secret_key)}  # '2a6f8f2c')
        logging.info('wuba request success: %s tickets generated' % product_count)
        return self.write(json_dumps(result_json))


class Refund(BaseHandler):
    def post(self):

        # 解密58请求参数
        params = get_params(self.get_argument('param'))
        logging.info('wuba refund request : %s', json_dumps(params))

        try:
            # 获得参数
            coupon_id = int(params.ticketId)
            order_id = int(params.orderId)
            reason = params.reason.encode('utf-8')
            status = int(params.status)
        except AttributeError:
            logging.info('wuba request failed: wrong params')
            return self.write('{"status":"10201", "msg": "参数错误"}')

        # 查找对应券
        coupon = self.db.get('select * from item i, item_coupon c where i.id=c.item_id and c.id=%s', coupon_id)
        if not coupon or (order_id != int(coupon.order_no) and order_id != int(coupon.order_id)):
            logging.info('wuba request failed: invalid coupon_sn from wuba')
            return self.write('{"status": "10202", "msg": "券不存在"}')

        # 检查58券状态
        if not 10 == status and not 11 == status and not 12 == status:
            logging.info('wuba request failed: coupon status is not valid for refund')
            return self.write('{"status": "10100", "msg": "该券状态无法退款"}')

        # 检查本地券状态
        if coupon.status == const.status.USED:
            logging.info('wuba request failed: coupon was consumed, invalid for refund')
            return self.write('{"status": "10100", "msg": "该券为已消费状态，无法退款，需要先联系视惠客服"}')

        if coupon.status == const.status.REFUND:
            logging.info('wuba request success: coupon refund status sync to 58')
            return self.write('{"status": "10000", "msg": "成功"}')

        # 执行退款
        result = refund_coupon(self.db, coupon.sn, '分销商id＝%s' % coupon.distr_shop_id, reason)
        if result.ok:
            logging.info('wuba request success: coupon %s refunded' % coupon.sn)
            return self.write('{"status": "10000", "msg": "成功"}')
        else:
            logging.info('wuba request failed: coupon internal refund failed')
            return self.write('{"status": "10100", "msg": %s}' % result.msg)


class Coupon(BaseHandler):
    def post(self):

        # 解密58请求参数
        params = get_params(self.get_argument('param'))
        logging.info('wuba order query request : %s', json_dumps(params))

        try:
            # 获得参数
            coupon_ids = params.ticketIds
        except AttributeError:
            logging.info('wuba request failed: wrong params')
            return self.write('{"status":"10201", "msg": "参数错误"}')

        # 查询每个券号
        tickets = []
        for coupon_id in coupon_ids:
            coupon = self.db.get('select * from item i, item_coupon c where i.id=c.item_id and c.id=%s',
                                 coupon_id.encode('utf-8'))
            if not coupon:
                # 券不存在，跳过
                continue
            else:
                distributor_order = self.db.get('select * from distributor_order where order_id=%s', coupon.order_id)
                if not distributor_order:
                    #  分销订单不存在，跳过
                    continue
                else:
                    message = json.loads(distributor_order.message, object_hook=json_hook)
                    # 检查状态
                    if coupon.status == const.status.BUY:
                        status = 0
                    elif coupon.status == const.status.USED:
                        status = 1
                    elif coupon.expire_at < datetime.now():
                        status = 9
                    elif coupon.status == const.status.REFUND:
                        status = 10
                    # 生成返回信息
                    ticket = {
                        "ticketIdThirdpart": int(coupon_id),
                        "orderIdThirdpart": int(coupon.order_no),
                        "groupbuyIdThirdpart": int(message.groupbuyIdThirdpart),
                        "ticketId58": "",
                        "orderId58": int(distributor_order.order_no),
                        "groupbuyId58": int(message.groupbuyId),
                        "ticketCode": str(coupon.sn),
                        "orderPrice": float(message.prodPrice),
                        "status": status,
                        "createtime": str(coupon.created_at),
                        "endtime": str(coupon.expire_at),
                    }
                    tickets.append(ticket)

        if not tickets:
            logging.info('wuba request failed: can not find coupon')
            return self.write('{"status":"10202", "msg": "券号不存在"}')
        else:
            logging.info('wuba request success:  %s coupon(s) found' % len(tickets))
            result_json = {'status': '10000', 'msg': 'ok', 'data': encrypt(str(tickets), options.wuba_secret_key)}  # '2a6f8f2c')
            return self.write(json_dumps(result_json))


def check_phone(phone):
    if not phone:
        return False
    ptn = re.compile('^1\d{10}$')
    if re.match(ptn, phone):
        return True
    return False


def get_params(encrypted_json):
    json_text = decrypt(encrypted_json, options.wuba_secret_key)  # '2a6f8f2c')
    return json.loads(json_text, object_hook=json_hook)
