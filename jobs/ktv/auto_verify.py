# -*- coding: utf-8 -*-
from tornado import gen
from autumn.coupon import local_check, partner_api_verify, local_verify

import torndb
import logging
from datetime import datetime
from tornado.ioloop import IOLoop
from conf import load_app_options
from tornado.options import options


# 加载配置
load_app_options()

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')


# 配置连接
db = torndb.Connection(
    host=options.mysql_host, database=options.mysql_database,
    user=options.mysql_user, password=options.mysql_password)


sql = """
    select ic.sn,kpg.shop_id from item_coupon ic, item i, ktv_order ko,ktv_product kp, ktv_product_goods kpg
    where ic.item_id = i.id and i.status=1 and ko.order_item_id=i.order_item_id and ko.product_id=kp.id
    and i.goods_id=kpg.goods_id
    and (   (ko.scheduled_day=%s and (ko.scheduled_time+kp.duration)<= %s)
         or (ko.scheduled_day<%s and (ko.scheduled_time+kp.duration-24)<=%s))"""

now = datetime.now()
today = now.date()
now_hour = now.hour

coupons = db.query(sql, today, now_hour, today, now_hour)


@gen.coroutine
def verify_coupon():
    for coupon in coupons:
        #  本地检测
        check_result = local_check(db, coupon.sn, coupon.shop_id)
        if not check_result.ok:
            logging.error('ktv auto verify failed. coupon:%s, msg:%s', coupon, check_result.msg)
            continue

        #  合作伙伴API验证
        api_result = yield partner_api_verify(db, coupon.sn)
        if not api_result.ok:
            ok, msg = (False, api_result.msg)
        else:
            #  本地验证
            verify_result = local_verify(db, coupon.sn, coupon.shop_id, '系统')
            ok, msg = (verify_result.ok, verify_result.msg)

        if not ok:
            logging.error('ktv auto verify failed. coupon:%s, msg:%s', coupon, msg)
        else:
            logging.info('ktv auto verify ok. coupon:%s', coupon)

IOLoop.instance().run_sync(verify_coupon)
