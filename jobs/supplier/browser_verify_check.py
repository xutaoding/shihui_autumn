# -*- coding: utf-8 -*-

import sys
import json
import time
import redis
import torndb
import logging
import traceback
from cStringIO import StringIO
from conf import load_app_options
from tornado.options import options
from autumn.utils import json_obj_hook, send_email
from autumn.api import DianpingBrowser, NuomiBrowser, MeituanBrowser, LashouBrowser

data = [
    {
        'partner': 'nuomi',
        'shop': 2452,
        'params': {
            'code': '166191776425',
        },
    },
    {
        'partner': 'meituan',
        'shop': 2452,
        'params': {
            'code': '102449669951',
            'poiid': 1584325,
        },
    },
    {
        'partner': 'dianping',
        'shop': 4210,
        'params': {
            'serialNums': '2727481075',
        }
    },
    {
        'partner': 'lashou',
        'shop': 2452,
        'params': {
            'password':     '28987760',
            'class':        'Check',
            'act':          'submit_one',
            'three_status': 0,
            'random':       int(time.time()*1000),
        }
    },
]


def do_check(rdb, partner, client, req_params):
    resp = ''
    try:
        resp = client.sync_fetch(**req_params)
        logging.info('%s browser verify check response: %s', partner, resp)
        client.parse_response(resp)
        client.is_ok()
        logging.info('%s browser verify check ok.', partner)
    except Exception:
        t = StringIO()
        traceback.print_exc(file=t)
        logging.info('%s browser verify check failed. %s', partner, t.getvalue())

        send_email(redis=rdb, subject='检查%s验证接口失败' % partner, to_list='dev@uhuila.com',
                   html='<p>%s browser verify check failed.</p> '
                        '<p>response: </p> <pre>%s</pre> '
                        '<p>exception:</p> <pre>%s</pre>'
                        % (partner, resp, t.getvalue()))


def main():
    # 配置连接
    db = torndb.Connection(
        host=options.mysql_host, database=options.mysql_database,
        user=options.mysql_user, password=options.mysql_password)
    rdb = redis.StrictRedis(host=options.redis_host, port=options.redis_port, db=options.redis_db)
    for item in data:
        key = '%s_params' % item['partner']
        partner_params = db.get('select %s from supplier_shop where id=%%s' % key, item['shop'])
        partner_params = json.loads(partner_params[key], object_hook=json_obj_hook)
        client = getattr(sys.modules[__name__], '%sBrowser' % item['partner'].title())('verify', partner_params)
        do_check(rdb, item['partner'], client, item['params'])

    db.close()


if __name__ == '__main__':
    # 加载配置
    load_app_options()

    # 配置日志
    logging.basicConfig(level=logging.INFO,
                        format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')
    main()

