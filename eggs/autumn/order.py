# -*- coding: utf-8 -*-
import random
import string
import logging
from autumn import const
from autumn.utils import PropDict
from decimal import Decimal


def new_distributor_order(db, distributor_shop_id, order_amount, payment, mobile):
    """
    生成订单，返回订单id 和 订单号
    :param db: torndb.Connection
    :param distributor_shop_id: int
    :param order_amount: float
    :return: int
    """

    # 生成订单
    while True:
        order_no = '%s%s' % (random.choice('123456789'), ''.join([random.choice(string.digits) for i in range(7)]))
        # 没有重复，停止
        if not db.get('select id from orders where order_no=%s', order_no):
            break
    order_id = db.execute(
        'insert into orders(distributor_shop_id, order_no, '
        'total_fee, payment, paid_at, created_at, status, mobile) values(%s, %s, %s, %s, NOW(), NOW(), 1, %s)',
        distributor_shop_id, order_no, order_amount, payment, mobile
    )

    # 记录订单日志
    db.execute('insert into journal (created_at, type, created_by, message, iid)'
               'values (NOW(), 1, %s, %s, %s)',
               "System", "生成新订单", order_id)

    return order_id, order_no


def new_distributor_item(db, order_id, order_no, sales_price, count, goods_info, mobile,
                         distributor_shop_id, distributor_goods_id, distributor_coupons, use_distributor_coupon):
    """ 创建订单项
        返回: {'ok': True, 'msg': 'good ', 'order_id': 123, 'coupons':[
            {'coupon_sn': '111', 'id': 123, 'distributor_coupon_sn': 'abc', 'distributor_coupon_pwd'},{}] }
    """

    if sales_price is None:
        sales_price = goods_info.sales_price

    if goods_info.generate_type == 'IMPORT':
        coupon_imported = db.query('select * from coupon_imported where goods_id=%s and used=0 '
                                   'limit %s', goods_info.id, count)

        # 库存不足（暂时只有导入券才判断库存）
        if len(coupon_imported) < count:
            logging.error('导入券库存不足-商品：%s' % goods_info.short_name)
            return PropDict(ok=False, msg='stock not enough: %s' % goods_info.id)

        imported_ids = [c.id for c in coupon_imported]
        db.execute('update coupon_imported set used=1 where id in (%s)'
                   % ','.join(['%s']*len(imported_ids)), *imported_ids)
        coupon_sns = [c.coupon_sn for c in coupon_imported]
        coupon_pwds = [c.coupon_pwd for c in coupon_imported]

    # 更新库存与销量
    db.execute('update goods set stock=stock-%s, sales_count=sales_count+%s, '
               'virtual_sales_count=sales_count+%s where id=%s', count, count, count, goods_info.id)

    # 生成 订单项
    order_item_id = db.execute(
        'insert into order_item(distributor_shop_id, goods_id, num, order_id, sales_price, '
        'distributor_goods_no) values (%s, %s, %s, %s, %s, %s)',
        distributor_shop_id, goods_info.id, count, order_id, sales_price, distributor_goods_id
    )

    coupons = []
    distributor_shop = db.get('select name, distributor_id, distributor_name from distributor_shop where id=%s',
                              distributor_shop_id)
    supplier = db.get('select * from supplier where id=%s', goods_info.supplier_id)

    #取得商品佣金比例
    goods_commission = db.get('select ratio from goods_distributor_commission '
                              'where goods_id=%s and distr_shop_id=%s', goods_info.id, distributor_shop_id)
    commission = goods_commission.ratio * sales_price * Decimal('0.01') if goods_commission else 0

    # 生成券
    for i in range(count):
        if use_distributor_coupon:
            coupon_sn = distributor_coupons[i]['coupon_sn']
            coupon_pwd = distributor_coupons[i]['coupon_pwd']
        elif goods_info.generate_type == 'IMPORT':
            coupon_sn = coupon_sns[i]
            coupon_pwd = coupon_pwds[i]
        else:
            coupon_pwd = ''
            while True:
                coupon_sn = ''.join([random.choice(string.digits) for z in range(10)])
                # 没有重复，停止
                if not db.get('select id from item_coupon where sn=%s', coupon_sn):
                    break

        item_field = {
            'status':                   const.status.BUY,
            'goods_name':               goods_info.short_name,
            'goods_id':                 goods_info.id,
            'distr_id':                 distributor_shop.distributor_id,
            'distr_shop_id':            distributor_shop_id,
            'sp_id':                    goods_info.supplier_id,
            'sales_id':                 supplier.sales_id,
            'order_item_id':            order_item_id,
            'order_id':                 order_id,
            'order_no':                 order_no,
            'face_value':               goods_info.face_value,
            'payment':                  sales_price,
            'sales_price':              sales_price,
            'purchase_price':           goods_info.purchase_price,
            'commission':               commission,
        }

        item_coupon_field = {
            'mobile':                   mobile,
            'sn':                       coupon_sn,
            'distr_sn':                 distributor_coupons[i]['coupon_sn'] if distributor_coupons else None,
            'distr_pwd':                distributor_coupons[i]['coupon_pwd'] if distributor_coupons else None,
            'sms_sent_count':           0,
            'expire_at':                goods_info.expire_at,
            'pwd':                      coupon_pwd
        }

        #  生成券信息
        item_id = db.execute(
            'insert into item(%s, created_at) values (%s, NOW())'
            % (','.join(item_field.keys()), ','.join(['%s']*len(item_field))), *item_field.values())

        coupon_id = db.execute(
            'insert into item_coupon(%s, item_id) values (%s, %s)'
            % (','.join(item_coupon_field.keys()), ','.join(['%s']*len(item_coupon_field)), item_id), *item_coupon_field.values())

        coupons.append({'id': coupon_id, 'coupon_sn': coupon_sn,
                        'distributor_coupon_sn': item_coupon_field['distr_sn'],
                        'distributor_coupon_pwd': item_coupon_field['distr_pwd']})

    return PropDict(ok=True, msg='ok', order_id=order_id, coupons=coupons)

