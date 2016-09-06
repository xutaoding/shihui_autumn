# -*- coding: utf-8 -*-

import common
import logging
import json
from tornado.options import options
from autumn.api.taobao import Taobao
from autumn.utils import json_hook


def express_auto_push(db, redis, message_raw, distr_shop_id):
    express_info = json.loads(message_raw, object_hook=json_hook)
    logging.info('taobao_express_update consumer pop taobao tid =%s ' % express_info.tid)
    app_info = json.loads(db.get('select taobao_api_info from distributor_shop where id = %s',
                                 distr_shop_id).taobao_api_info, object_hook=json_hook)
    express_company = Taobao('taobao.logistics.offline.send')
    express_company.set_app_info(app_info.app_key, app_info.app_secret_key)
    express_company.set_session(app_info.session)

    response = express_company.sync_fetch(**express_info)
    express_company.parse_response(response)

    if express_company.is_ok():
        logging.info('outer order express info update success. order %s', express_info.tid)
        redis.lrem(options.queue_taobao_express_processing, 0, express_info)
    else:
        logging.error('outer order express info update failure. order %s', express_info.tid)


def main_loop():
    redis = common.redis_client()
    db = common.db_client()
    logging.info('----- express consumer starts -----')

    while common.running():
        #淘宝订单发货信息
        message_raw = redis.brpoplpush(options.queue_taobao_express, options.queue_taobao_express_processing)
        task = json.loads(message_raw, object_hook=json_hook)
        if task.tid:
            shop = db.get('select distributor_shop_id from distributor_order where order_no = %s limit 1', task.tid)
            if shop and shop.distributor_shop_id == options.shop_id_taobao:
                #淘宝自动发货
                express_auto_push(db, redis, message_raw, options.shop_id_taobao)
            elif shop and shop.distributor_shop_id == options.shop_id_tmall:
                #天猫自动发货
                express_auto_push(db, redis, message_raw, options.shop_id_tmall)
            else:
                logging.info("can't find order in taobao and tmall. order_no = %s", task.tid)

    logging.info('----- express consumer shut down -----')

if __name__ == '__main__':
    common.set_up()

    main_loop()