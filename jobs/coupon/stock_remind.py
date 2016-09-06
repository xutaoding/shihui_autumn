# -*- coding: utf-8 -*-
import datetime

import torndb
import logging
from conf import load_app_options
from tornado.options import options
import redis
from tornado.template import Template
from autumn.utils import send_email

# 加载配置
load_app_options()

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')


# 配置连接
db = torndb.Connection(
    host=options.mysql_host, database=options.mysql_database,
    user=options.mysql_user, password=options.mysql_password)
redis = redis.StrictRedis(host=options.redis_host, port=options.redis_port, db=options.redis_db)

sql = """select g.stock, g.id, g.short_name, o.name, o.email, o.id oid
         from goods g join supplier s on g.supplier_id = s.id
         join operator o on s.sales_id = o.id
         where g.generate_type = 'IMPORT' and g.deleted = 0 and g.expire_at > NOW() and g.stock < 10"""

stock_list = db.query(sql)

db.close()

# 如果没有要提醒的内容，退出
if not stock_list:
    import sys
    sys.exit()

email_list = {}
for item in stock_list:
    if item.email not in email_list.keys():
        email_list[item.email] = []
    email_list[item.email].append(item)

template = """<p> 亲，有<strong>{{len(goods_list)}}</strong>个货物库存不足，请注意！ </p>
              <table cellpadding='1' cellspacing='0' border='1' bordercolor='#000000'>
              <tr>
                  <th>商品名</th>
                  <th>库存</th>
              </tr>
              {% for goods in goods_list %}
              <tr>
                <td>{{ goods.short_name }}</td>
                <td>{{ goods.stock }}</td>
              </tr>
              {% end %}
              </table>"""

now = datetime.datetime.now().hour

if 18 >= now >= 9:
    for email, content in email_list.iteritems():
        html = Template(template).generate(goods_list=content)
        send_email(redis=redis, subject='库存不足提醒',
                   to_list=email + ',' + options.expiring_contract_receivers, html=html)



