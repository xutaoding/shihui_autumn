# -*- coding: utf-8 -*-

import torndb
from conf import load_app_options
import logging
from tornado.options import options
from datetime import datetime, timedelta

load_app_options()  # 加载配置
logging.info("start check expire order ")
logging.basicConfig(level=logging.INFO,
                    format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')

db = torndb.Connection(
    host=options.mysql_host, database=options.mysql_database,
    user=options.mysql_user, password=options.mysql_password)

expire_at = datetime.now() + timedelta(hours=-2)
orders = db.query('select oi.goods_id, oi.num from order_item oi, orders o where oi.order_id = o.id '
                  'and o.created_at < %s and status = 0 and created_at > "2014-02-11 00:00:00"', expire_at)
db.execute('update orders set status = 8 where created_at < %s and status = 0 '
           'and created_at > "2014-02-11 00:00:00" ', expire_at)

for order in orders:
    db.execute('update goods set stock = stock + %s where id = %s', order.num, order.goods_id)

logging.info('end check expire order')
db.close()
