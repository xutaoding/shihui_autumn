# -*- coding: utf-8 -*-
import httplib
import json

import logging
import urllib
import redis
from autumn.api import MeituanBrowser
from autumn.utils import json_obj_hook, send_email, json_dumps
import torndb
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
redis = redis.StrictRedis(host=options.redis_host, port=options.redis_port, db=options.redis_db)

shops = db.query('select id, nuomi_params from supplier_shop where deleted=0 and nuomi_params is not null')

logging.info('--------start update nuomi cookie--------')
for shop in shops:
    params = json.loads(shop.nuomi_params, object_hook=json_obj_hook)
    login_params = urllib.urlencode({
        'emailOrMobile': params.emailOrMobile,
        'password': params.password,
        'isAutoLogin': 'false',
    })
    login_headers = {'Content-type': 'application/x-www-form-urlencoded', 'Accept': 'text/plain'}
    login_conn = httplib.HTTPConnection('y.nuomi.com')
    login_conn.request('POST', '/login/loginto', login_params, login_headers)
    login_resp = login_conn.getresponse()
    login_cookie = login_resp.getheader('set-cookie')
    login_cookie = ';'.join(filter(lambda v: v.strip().split('=')[0] in ('lbc_tuan_user_key', 'tuan_user_ticket_key', 'JSESSIONID'),
                                   [p.split(',')[-1] for p in login_cookie.split(';')]))
    login_conn.close()
    if not login_cookie:
        logging.error('nuomi update cookie failed: login fail, supplier_shop_id=%s', shop.id)
        send_email(redis=redis, subject='糯米更新cookie失败提醒',
                   to_list='dev@uhuila.com', html='supplier_shop id: %s' % shop.id)
        continue
    params['cookie'] = login_cookie
    try:
        db.execute('update supplier_shop set nuomi_params=%s where id=%s', json_dumps(params), shop.id)
    except Exception:
        send_email(redis=redis, subject='糯米更新cookie失败提醒',
                   to_list='dev@uhuila.com', html='insert cookie into database failed, supplier_shop id: %s' % shop.id)

logging.info('--------end update nuomi cookie--------')

shops = db.query('select id, meituan_params from supplier_shop where deleted=0 and meituan_params is not null')
logging.info('--------start update meituan cookie--------')
for shop in shops:
    params = json.loads(shop.meituan_params, object_hook=json_obj_hook)
    login_params = urllib.urlencode({
        'login': params.login,
        'password': params.password,
        'remember_username': 1,
        'auto_login': 1
    })
    login_headers = {'Content-type': 'application/x-www-form-urlencoded', 'Accept': 'text/plain'}
    login_conn = httplib.HTTPConnection('e.meituan.com')
    login_conn.request('POST', '/account/login', login_params, login_headers)
    login_resp = login_conn.getresponse()
    login_cookie = login_resp.getheader('set-cookie')
    login_cookie = ';'.join(filter(lambda v: v.strip().split('=')[0] not in ('expires', 'path', 'domain'),
                                   [p.split(',')[-1] for p in login_cookie.split(';')]))
    login_conn.close()
    if not login_cookie:
        logging.error('nuomi update cookie failed: login fail, supplier_shop_id=%s', shop.id)
        send_email(redis=redis, subject='美团更新cookie失败提醒',
                   to_list='dev@uhuila.com', html='supplier_shop id: %s' % shop.id)
        continue
    params['cookie'] = login_cookie
    try:
        db.execute('update supplier_shop set meituan_params=%s where id=%s', json_dumps(params), shop.id)
    except Exception:
        send_email(redis=redis, subject='美团更新cookie失败提醒',
                   to_list='dev@uhuila.com', html='insert cookie into database failed, supplier_shop id: %s' % shop.id)

logging.info('--------end update meituan cookie--------')
