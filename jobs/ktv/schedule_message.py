#-*- coding: utf-8 -*-
"""给每个店的经理发送当天的ktv预订信息"""

from conf import load_app_options
import torndb
from datetime import date
from tornado.options import options
import redis


def new_message(schedule_day, shop_name):
    message = str(schedule_day) + shop_name + ' 预定'
    return message


def schedule_time(start_time, duration):
    return str(start_time) + '点至' + str((start_time + duration)) + '点'


def message_append(order_info):
    message = '【' + order_info.mobile + \
        {'MINI': '迷你包', 'SMALL': '小包', 'MIDDLE': '中包', 'LARGE': '大包', 'LUXURY': '豪华包'}.get(order_info.room_type) + \
        ' (' + str(order_info.num) + '间) ' + schedule_time(order_info.scheduled_time, order_info.duration) + '】'
    return message


load_app_options()
today = date.today()
db = torndb.Connection(
    host=options.mysql_host, database=options.mysql_database,
    user=options.mysql_user, password=options.mysql_password)

redis_connect = redis.StrictRedis(host=options.redis_host, port=options.redis_port, db=options.redis_db)

#查找出当天的所有的预订ktv订单
order_list = db.query('select k.shop_id, k.room_type, kp.duration, o.mobile, oi.num, ss.name shop_name, '
                      'ss.manager_mobile, k.scheduled_time  '
                      'from ktv_order k join ktv_product kp on k.product_id = kp.id '
                      'join order_item oi on k.order_item_id = oi.id '
                      'join orders o on oi.order_id = o.id '
                      'join supplier_shop ss on k.shop_id = ss.id '
                      'where k.scheduled_day = %s and k.status = "DEAL" order by k.shop_id', today)

shop_list = set()  # 当天订单的所含有的店铺

for shop_info in order_list:
    shop_list.add(shop_info.shop_id)

for shop in shop_list:
    message = ''
    mobile = ''
    count = 0
    for order in order_list:
        mobile = order.manager_mobile
        if order.shop_id != shop:
            continue
        count += 1
        if not message:
            message += new_message(today, order.shop_name)
        message += message_append(order)

        if count >= 12:
            count = 0
            redis_connect.lpush(options.queue_coupon_send,
                                {'mobile': mobile, 'sms': message, 'retry': 0})
            message = ''

    #如果没有满12条时的情况
    redis_connect.lpush(options.queue_coupon_send,
                        {'mobile': mobile, 'sms': message, 'retry': 0})