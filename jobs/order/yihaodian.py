# -*- coding: utf-8 -*-

import logging
import torndb
import redis
from datetime import datetime, timedelta
from conf import load_app_options
from tornado.options import options
from autumn.api.yihaodian import Yihaodian
from autumn.utils import json_dumps


def yihaodian_order_listener(db, redis):
    """
    定时从一号店获得新生成的订单, 筛选未处理订单，并放入订单处理队列
    :type db:torndb.Connection
    :type redis:redis.StrictRedis
    """

    # 生产环境运行
    # if not options.app_mode == 'prod':
    #    logging.info("yihaodian order listener quit: not in prod mode")
    #    return

    end_time = datetime.now() + timedelta(minutes=10)  # 当前时间往后10分钟
    start_time = end_time - timedelta(days=14)  # 初始时间推前14天,因为一号店api支持的最大跨度是15天
    end = end_time.strftime('%Y-%m-%d %H:%M:%S')
    start = start_time.strftime('%Y-%m-%d %H:%M:%S')
    # 获得一号店订单列表
    orders = fetch_yihaodian_order(start, end)

    if orders:
        # 查询已经存在的订单
        result = db.query('select order_no from distributor_order where distributor_shop_id=%s and order_no in ('
                          + ','.join(['%s']*len(orders)) + ')',
                          options.shop_id_yihaodian, *orders)
        exist_orders = [row['order_no'] for row in result]
        # 插入不存在的订单
        for order in orders:
            if not exist_orders or exist_orders and order not in exist_orders:
                distributor_order_id = db.execute('insert into distributor_order (order_no, created_at, message, '
                                                  'distributor_shop_id) values (%s, now(), "", %s)',
                                                  order, options.shop_id_yihaodian)
                logging.info('insert new distributor order_no: %s', order)
                # 推进 redis 处理队列
                redis.lpush(options.queue_distributor_order,
                            json_dumps({'distributor_order_id': distributor_order_id, 'distributor': 'YHD', 'retry': 0}))


def fetch_yihaodian_order(start_time, end_time):
    """
    发送一号店订单获取请求，返回订单列表
    :return: list: 一号店order_code列表
    """

    yihaodian = Yihaodian('yhd.orders.get')
    orders_list = []
    page = 0

    while True:
        page += 1
        # 发送请求
        response = yihaodian.sync_fetch(
            orderStatusList='ORDER_WAIT_SEND',
            dataType='1',
            startTime=start_time,
            endTime=end_time,
            pageRows='100',
            cutPage=page,
        )
        logging.info('yihaodian fetch order response: %s' % response)
        # 解析应答
        yihaodian.parse_response(response)
        if not yihaodian.is_ok():
            # 没有数据，返回
            return orders_list
        else:
            total = int(yihaodian.message.findtext('totalCount'))
            if total == 0:
                # 订单总数为零，返回
                return orders_list
            orders = yihaodian.message.find('orderList').findall('order')
            for order in orders:
                orders_list.append(order.findtext('orderCode'))
            if len(orders_list) >= total:
                # 获得所有订单，返回，可以少执行一次
                return orders_list


if __name__ == '__main__':
    load_app_options()  # 加载配置
    logging.info("start yihaodian order fetch")
    logging.basicConfig(level=logging.INFO,
                        format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')

    db = torndb.Connection(
        host=options.mysql_host, database=options.mysql_database,
        user=options.mysql_user, password=options.mysql_password)

    redis = redis.StrictRedis(host=options.redis_host, port=options.redis_port, db=options.redis_db)
    yihaodian_order_listener(db, redis)
    db.close()
