# -*- coding: utf-8 -*-

import torndb
import redis
import logging
from conf import load_app_options
from tornado.options import options
from tornado.template import Template
from autumn.utils import send_email
from datetime import datetime, timedelta


# 加载配置
load_app_options()

# 配置日志
logging.info('start to check expiring contract')
logging.basicConfig(level=logging.INFO,
                    format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')


# 配置连接
db = torndb.Connection(
    host=options.mysql_host, database=options.mysql_database,
    user=options.mysql_user, password=options.mysql_password)

redis = redis.StrictRedis(host=options.redis_host, port=options.redis_port, db=options.redis_db)

# 查询将要过期的合同
expiring_contract_list = db.query(
    'select sc.expire_at, sp.name sp_name, sp.short_name sp_short_name, sp.id sp_id, op.name sales_name '
    'from contract sc, supplier sp, operator op '
    'where sc.uid=sp.id and sc.type=1 and sp.sales_id=op.id and sc.deleted=0 and sc.expire_at>%s and sc.expire_at<%s',
    datetime.now(), datetime.now() + timedelta(days=10))

db.close()

logging.info('expiring contract count: %s', len(expiring_contract_list))


# 如果没有要提醒的内容，退出
if not expiring_contract_list:
    import sys
    sys.exit()

# 构建邮件内容
template = """<p> 亲，有<strong>{{len(contract_list)}}</strong>个商户合同在10天内到期（或已经过期），请注意！ </p> <table cellpadding='1' cellspacing='0' border='1' bordercolor='#000000'> <tr> <th>销售专员</th> <th>商户</th> <th>商户简称</th> <th>到期时间</th> <th>操作</th> </tr> {% for contract in contract_list %} <tr> <td>{{contract.sales_name}}</td> <td>{{contract.sp_name}}</td> <td>{{contract.sp_short_name}}</td> <td>{{contract.expire_at}}</td> <td><a href='http://{{options.operate_domain}}/supplier/{{contract.sp_id}}/contract'>点击查看</a></td> </tr> {% end %} </table>"""

# 发送邮件
html = Template(template).generate(contract_list=expiring_contract_list, options=options)
send_email(redis=redis, subject='合同到期提醒', to_list=options.expiring_contract_receivers, html=html)
