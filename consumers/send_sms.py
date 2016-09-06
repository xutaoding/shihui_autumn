# -*- coding: utf-8 -*-

import common
import logging
import json
from tornado.options import options
from autumn.api.zhutong import Zhutong
from autumn.utils import json_hook


def main_loop():
    redis = common.redis_client()
    logging.info('----- coupon sms send consumer starts -----')

    while common.running():
        message_raw = redis.brpoplpush(options.queue_coupon_send, options.queue_coupon_send_processing)
        logging.info('get sms task: %s' % message_raw)
        task = json.loads(message_raw, object_hook=json_hook)
        mobile = task.mobile
        content = task.sms.encode('utf-8')

        # 检查手机号码长度
        if len(mobile) != 11:
            logging.error('coupon sms send consumer error: mobile number %s is not valid' % mobile)
            continue

        # 发送请求
        zt = Zhutong()
        try:
            response = zt.sync_fetch(mobile=mobile, content=content, xh='')
            zt.parse_response(response)

            if zt.is_ok():
                redis.lrem(options.queue_coupon_send_processing, 0, message_raw)
                logging.info('send sms successfully: %s' % content)
            elif int(zt.message) == 13:
                redis.lrem(options.queue_coupon_send_processing, 0, message_raw)
                logging.info('send sms faied, 30分钟重复提交')
            else:
                redis.lpush(options.queue_coupon_send_emay, message_raw)
                logging.error('send sms failed, zhutong response error: %s', response)
        except:
            redis.lpush(options.queue_coupon_send_emay, message_raw)
            logging.error('send sms failed, zhutong connection reset')

    logging.info('----- coupon sms sender consumer shut down -----')


if __name__ == '__main__':
    common.set_up()

    main_loop()
