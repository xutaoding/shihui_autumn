# -*- coding: utf-8 -*-

import logging
from autumn.api.yihaodian import Yihaodian
from tornado.options import options
from autumn.order import new_distributor_order, new_distributor_item
from autumn.sms import CouponSMSMessage
from decimal import Decimal

def yihaodian_order(db, redis, distributor_order_id, message_raw):
    """
    一号店分销订单处理
    :param db:
    :param redis:
    :param distributor_order_id:
    :param message_raw:
    :type db:torndb.Connection
    :type redis:redis.client.StrictRedis
    :type distributor_order_id: int
    """
    distributor_order = db.get('select * from distributor_order where id=%s', distributor_order_id)
    distributor_order_no = distributor_order.order_no

    # 分销订单号不存在，结束
    if not distributor_order:
        logging.error('yihaodian job consume cannot find distributor order: order_no=%s', distributor_order_no)
        return

    # 重新刷新订单信息
    yihaodian = Yihaodian('yhd.order.detail.get')
    response = yihaodian.sync_fetch(orderCode=distributor_order_no)
    logging.info('yihaodian response for distributor_order_no %s : %s' % (distributor_order_no, response))
    yihaodian.parse_response(response)

    # 一号店请求失败，结束
    if not yihaodian.is_ok():
        logging.error('yihaodian job consume fetch order failed, distributor order_no=%s', distributor_order_no)
        return

    order_status = yihaodian.message.findtext('./orderInfo/orderDetail/orderStatus').strip()

    # 一号店订单已取消，从队列移除，结束
    if order_status == 'ORDER_CANCEL':
        # 队列移除
        redis.lrem(options.queue_distributor_order_processing, 0, message_raw)
        logging.info(' yihaodian order_no %s cancelled ', distributor_order_no)
        return
    # 一号店订单状态为‘可以发货’， 则处理该订单
    elif order_status == 'ORDER_TRUNED_TO_DO':
        # 更新分销订单message, 如果distributor_order表中message为空，则该分销订单已在分销商处取消
        db.execute('update distributor_order set message=%s where order_no=%s', response, distributor_order_no)

        # 筛选电子券订单
        order_items = yihaodian.message.findall('./orderInfo/orderItemList/orderItem')
        coupon_items = []
        for item in order_items:
            goods_link_id = item.findtext('./outerId')
            if goods_link_id:
                goods = db.get('select g.* from goods as g, goods_distributor_shop as gds '
                               'where g.id = gds.goods_id and gds.distributor_shop_id=%s and gds.goods_link_id=%s',
                               options.shop_id_yihaodian, goods_link_id)
                if not goods and int(goods_link_id) < 20000:
                    goods = db.get('select g.* from goods g where g.type="E" and g.id=%s', goods_link_id)
                # 当商品类型为电子券时，才处理
                if goods and goods.type == options.goods_type_electronic:
                    coupon_items.append((item, goods))
                else:
                    logging.warning('yihaodian job consume warning: goods_link_id=%s not found or goods type is real'
                                    % goods_link_id)

        if len(coupon_items) == 0:
            # 分销订单没有电子券，从处理队列移除
            redis.lrem(options.queue_distributor_order_processing, 0, message_raw)
            logging.info('yihaodian job consume exits for no real goods, distributor order_no: %s' % distributor_order_no)
            return

        # 生成一百券订单
        if distributor_order.order_id == 0 and check_stock(coupon_items):
            mobile = yihaodian.message.findtext('./orderInfo/orderDetail/goodReceiverMoblie')
            order_amount = yihaodian.message.findtext('./orderInfo/orderDetail/orderAmount')
            payment = Decimal(yihaodian.message.findtext('./orderInfo/orderDetail/realAmount'))
            order_id, order_no = new_distributor_order(db, options.shop_id_yihaodian, order_amount, payment, mobile)

            # 生成订单项
            for item in coupon_items:
                order_item = item[0]
                goods_info = item[1]
                sales_price = Decimal(order_item.findtext('./orderItemPrice'))
                count = int(order_item.findtext('./orderItemNum'))
                distributor_goods_id = order_item.findtext('./productId')
                result = new_distributor_item(db, order_id, order_no, sales_price, count, goods_info, mobile,
                                              options.shop_id_yihaodian, distributor_goods_id, [], False)
                if not result.ok:
                    logging.error('failed to generate order items for distributor_order_id=%s of goods_id=%s'
                                  % (distributor_order_id, goods_info.id))
                    return
                logging.info('create new yibaiquan order id=%s for yihaodian distributor order id=%s'
                             % (order_id, distributor_order_id))

            # 相互更新分销订单和订单
            db.execute('update orders set distributor_order_id=%s where id = %s',
                       distributor_order_id, order_id)
            db.execute('update distributor_order set order_id=%s where id=%s',
                       order_id, distributor_order_id)

            # 按order_item发送券短信
            all_order_items = db.query('select * from order_item where order_id=%s', order_id)
            for item in all_order_items:
                CouponSMSMessage(db, redis, order_item=item).remark('一号店订单发送券号短信').send()

            # 通知一号店，已发货
            yihaodian = Yihaodian('yhd.logistics.order.shipments.update')
            response = yihaodian.sync_fetch(orderCode=distributor_order_no,
                                            deliverySupplierId=options.yhd_delivery,
                                            expressNbr=distributor_order_no
                                            )
            yihaodian.parse_response(response)

            if yihaodian.is_ok():
                # 分销订单处理完成，从处理队列移除
                redis.lrem(options.queue_distributor_order_processing, 0, message_raw)
                logging.info('yihaodian distributor order (id=%s) finish' % distributor_order_id)
            else:
                logging.error('update yihaodian distributor order (id=%s) shipments failed' % distributor_order_id)


def check_stock(coupon_items):
    """
    检查需要生成券的商品库存是否充足
    :type: coupon_items:list
    :return: bool
    """
    for item in coupon_items:
        count = int(item[0].findtext('./orderItemNum').strip())
        stock = int(item[1].stock)
        # 判断库存
        if stock < count:
            logging.error('库存不足-商品id=%s-%s' % (item[1].id, item[1].short_name))
            return False

    return True
