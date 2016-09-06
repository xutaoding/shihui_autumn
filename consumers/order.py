# -*- coding: utf-8 -*-

import common
import logging
import json
from autumn.utils import json_hook
from tornado.options import options
from taobao_order import taobao_order
from yihaodian_order import yihaodian_order
from taobao_express_update import express_auto_push


def main_loop():
    redis = common.redis_client()
    db = common.db_client()
    logging.info('----- distributor order consumer starts -----')

    while common.running():

        # 移动一个订单到处理队列
        message_raw = redis.brpoplpush(options.queue_distributor_order, options.queue_distributor_order_processing)
        task = json.loads(message_raw, object_hook=json_hook)
        logging.info('distributor order consumer pop %s distributor order, id=%s '
                     % (task.distributor, task.distributor_order_id))

        # 淘宝订单
        if task.distributor == 'TB':
            taobao_order(db, redis, task.distributor_order_id, message_raw)
        # 一号店订单
        elif task.distributor == 'YHD':
            yihaodian_order(db, redis, task.distributor_order_id, message_raw)

    logging.info('----- distributor order consumer shut down -----')

if __name__ == '__main__':
    common.set_up()

    main_loop()