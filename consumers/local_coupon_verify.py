# -*- coding: utf-8 -*-

import common
import logging
import json
from datetime import datetime, timedelta
from autumn.utils import json_hook
from tornado.options import options
from autumn.coupon import local_verify

"""美团、点评、糯米的券在一百券上验证处理"""

common.set_up()

db = common.db_client()
redis = common.redis_client()

while common.running():
    coupon = redis.brpoplpush(options.queue_coupon_local_verify, options.queue_coupon_local_verify_processing)
    task = json.loads(coupon, object_hook=json_hook)
    logging.info('local coupon verify pop %s ,shop_id:%s ' % (task.coupon, task.shop_id))

    #开始对外部券进行本地验证
    verify_result = local_verify(db, task.coupon, task.shop_id, '系统', verified_at=task.used_at)

    ok, msg = (verify_result.ok, verify_result.msg)
    if ok:
        # 外部券验证处理完成，从处理队列移除
        redis.lrem(options.queue_coupon_local_verify_processing, 0, coupon)
        logging.info('local coupon verify finish,coupon_sn:%s' % task.coupon)
    else:
        logging.info('local coupon verify failed,coupon_sn:%s' % task.coupon)
