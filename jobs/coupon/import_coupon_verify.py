#-*- coding: utf-8 -*-

from conf import load_app_options
import logging
import torndb
from tornado.options import options
from datetime import datetime, timedelta
from autumn.coupon import partner_api_verify
from autumn.coupon import local_verify
from tornado.gen import coroutine
from tornado.ioloop import IOLoop


@coroutine
def verify_import_coupon():
    """查找2天内，5分钟前的未消费的导入券"""
    logging.basicConfig(level=logging.INFO,
                        format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')

    now = datetime.now()
    start_time = now - timedelta(days=2)
    end_time = now - timedelta(minutes=5)

    db = torndb.Connection(
        host=options.mysql_host, database=options.mysql_database,
        user=options.mysql_user, password=options.mysql_password)

    coupon_list = db.query(
        'select ic.sn, '
        '(select min(id) from supplier_shop ss where ss.supplier_id=g.supplier_id and ss.deleted=0) shop_id '
        'from item i, item_coupon ic, goods g '
        'where i.id=ic.item_id and i.goods_id=g.id '
        'and i.created_at > %s and i.created_at < %s and i.distr_shop_id != %s '
        'and i.status=1 and g.generate_type="IMPORT"', start_time, end_time, options.shop_id_wuba)

    for coupon in coupon_list:
        response = yield partner_api_verify(db, coupon.sn)
        if not response.ok:
            ok, msg = (False, response.msg)
        else:
            verify_result = local_verify(db, coupon.sn, coupon.shop_id, '系统')
            ok, msg = (verify_result.ok, verify_result.msg)

        if not ok:
            logging.error('导入券%s验证失败，失败原因%s', coupon.sn, msg)
        else:
            logging.info('导入券%s验证成功', coupon.sn)


load_app_options()

IOLoop.instance().run_sync(verify_import_coupon)