# -*- coding: utf-8 -*-
import re
import json
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from autumn.utils import json_hook
from tornado.options import options
from autumn.order import new_distributor_order, new_distributor_item
from autumn.api.taobao import Taobao
from autumn.ktv import TaobaoSku
from autumn.sms import CouponSMSMessage, SMSMessage


def taobao_order(db, redis, distributor_order_id, message_raw):
    """
    处理淘宝的分销订单队列
    :param db
    :param redis
    :param distributor_order_id: 分销订单id
    :param message_raw: redis 队列元素值
    :type db:torndb.Connection
    :type redis:redis.client.StrictRedis
    :type distributor_order_id: int
    """

    distributor_order = db.get('select * from distributor_order where id=%s', distributor_order_id)
    params = json.loads(distributor_order.message, object_hook=json_hook)
    shop = db.get('select * from distributor_shop where taobao_seller_id=%s', params.taobao_sid)
    api_info = json.loads(shop.taobao_api_info, object_hook=json_hook)
    if not distributor_order.order_id:
        # 如果还没生成一百券订单
        goods_link_id = int(params.outer_iid)
        # 找到关联的商品
        goods_info = db.get('select g.* from goods g, goods_distributor_shop gds '
                            'where g.id = gds.goods_id and distributor_shop_id=%s and goods_link_id=%s',
                            shop.id, goods_link_id)
        if not goods_info and goods_link_id < 20000:
            goods_info = db.get('select g.* from goods g where g.type="E" and g.id=%s', goods_link_id)

        if not goods_info:
            logging.error('taobao order consume failed: goods not found. link_id: %s', goods_link_id)
            return

        taobao = Taobao('taobao.trade.get')
        taobao.set_app_info(api_info.app_key, api_info.app_secret_key)
        taobao.set_session(api_info.session)
        response = taobao.sync_fetch(tid=distributor_order.order_no,
                                     fields='total_fee,payment,orders.payment,orders.num,'
                                            'orders.sku_properties_name,orders.price')
        taobao.parse_response(response)

        order_payment = Decimal(taobao.message.trade.payment)
        # 创建订单
        order_id, order_no = new_distributor_order(db, shop.id, Decimal(taobao.message.trade.total_fee),
                                                   order_payment, params.mobile)
        result = new_distributor_item(db, order_id, order_no, order_payment / int(params.num),
                                      int(params.num), goods_info, params.mobile, shop.id, params.num_iid, None, False)

        if not result.ok:
            logging.error('taobao order consume failed. %s', result.msg)
            return
        else:
            db.execute('update orders set distributor_order_id=%s where id = %s',
                       distributor_order_id, result.order_id)
            db.execute('update distributor_order set order_id=%s where id=%s',
                       result.order_id, distributor_order_id)
        ktv_order_result = create_ktv_order(db, order_id, params)
    else:
        order_id = distributor_order.order_id
        ktv_order_result = []

    coupons = db.query('select c.sn as coupon_sn from item i, item_coupon c where i.id=c.item_id and i.order_id=%s',
                       order_id)

    # 告诉淘宝我们已发货
    taobao = Taobao('taobao.vmarket.eticket.send')
    taobao.set_app_info(api_info.app_key, api_info.app_secret_key)
    if api_info.app_key == options.taobao_kunran_app_key:  # 如果是码商，要加上码商的信息
        taobao.add_field('codemerchant_id', options.taobao_kunran_id)
        taobao.set_session(api_info.merchant_session)
    else:
        taobao.set_session(api_info.session)
    response = taobao.sync_fetch(order_id=params.order_id, token=params.token,
                                 verify_codes=','.join(['%s:1' % item.coupon_sn for item in coupons]))
    logging.info('tell taobao coupon send response: %s', response)
    taobao.parse_response(response)

    if taobao.is_ok():
        logging.info('taobao order complete. distributor_order_id: %s', distributor_order_id)
        all_order_items = db.query('select * from order_item where order_id=%s', order_id)
        for item in all_order_items:
            CouponSMSMessage(db, redis, order_item=item).remark('淘宝订单短信发送').send()
        redis.lrem(options.queue_distributor_order_processing, 0, message_raw)
        #只要ktv预订时间有，就给门店经理发送ktv预订的包厢信息
        for ktv_info in ktv_order_result:
            sku = ktv_info['sku']
            phone_numbers = ktv_info['manager_mobile']
            for phone in (phone_numbers.split(',') if phone_numbers else []):
                content = str(sku.date) + ktv_info['shop_name'] + '预订【' + str(params.mobile) + \
                    sku.room_name + " （" + str(params.num) + "间）" + sku.human_time_range + "】"
                #给经理发送短信告知预订信息
                logging.info('send message to manager,phone:%s,content:%s', phone, content)
                SMSMessage(content, phone).send(redis)
    else:
        logging.error('tell taobao coupon send failed: %s', taobao.error)


def create_ktv_order(db, order_id, params):
    order_items = db.query('select * from order_item where order_id=%s', order_id)
    # "sku_properties":"包厢房型:小包;欢唱时间:17点至20点;日期:6月1日(周三)"
    ktv_order_result = []

    if not 'sku_properties' in params:
        return ktv_order_result

    sku = TaobaoSku('', None, 0, 0, 0, 0, 0)
    tmp = re.split(r'[:;]', params.sku_properties)
    sku.parse_taobao_property(tmp[1].encode('utf-8'), tmp[3].encode('utf-8'), tmp[5].encode('utf-8'))

    # 7天内过期
    expire_at = datetime.fromordinal(sku.date.toordinal())
    expire_at = expire_at + timedelta(days=7, seconds=-1)

    for order_item in order_items:
        is_ktv = db.get('select 1 from ktv_product_goods where goods_id=%s', order_item.goods_id)
        if not is_ktv:
            continue
        db.execute('update item_coupon ic, item i set ic.expire_at=%s where ic.item_id=i.id and i.order_item_id=%s',
                   expire_at, order_item.id)
        product_goods = db.get('select kp.shop_id, kp.product_id, ss.name shop_name, ss.manager_mobile '
                               'from ktv_product_goods kp left join supplier_shop ss '
                               'on kp.shop_id = ss.id where kp.goods_id=%s', order_item.goods_id)

        db.execute('insert into ktv_order set created_at=NOW(), deal_at=NOW(), '
                   'room_type=%s, scheduled_day=%s, scheduled_time=%s, status="DEAL",'
                   'goods_id=%s, order_item_id=%s, shop_id=%s, product_id=%s',
                   sku.room_type, sku.date, sku.start_time, order_item.goods_id,
                   order_item.id, product_goods.shop_id, product_goods.product_id)

        ktv_order_params = {
            'shop_name': product_goods.shop_name,
            'manager_mobile': product_goods.manager_mobile,
            'sku': sku
        }
        ktv_order_result.append(ktv_order_params)

    return ktv_order_result
