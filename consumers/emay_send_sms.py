# -*- coding: utf-8 -*-
from autumn.utils import json_hook, send_email

import common
import logging
import json
from tornado.options import options
from autumn.api.emay import EMay


def main_loop():

    redis = common.redis_client()
    logging.info('----- emay sms send consumer starts -----')

    while common.running():
        # 查余额
        emay = EMay('getBalance')
        response = emay.sync_fetch(
            serial_no=options.emay_serial_no,
            key=options.emay_key
        )
        emay.parse_response(response)
        if float(emay.message.findtext('.//return')) < 10.0:
            send_email(redis=redis, subject='亿美余额不足10元提醒',
                       to_list='dev@uhuila.com', html='亿美短信通道余额不足 10 元')

        message_raw = redis.brpoplpush(options.queue_coupon_send_emay, options.queue_coupon_send_processing)
        logging.info('get sms task: %s' % message_raw)
        task = json.loads(message_raw, object_hook=json_hook)
        mobile = task.mobile
        content = task.sms if isinstance(task.sms, unicode) else task.sms.decode('utf-8')
        content = content[:-5] + u',退订回复TD【一百券】'
        sms_id = task.sms_id if 'sms_id' in task else ''

        # 检查手机号码长度
        if len(mobile) != 11:
            logging.error('coupon sms send consumer error: mobile number %s is not valid' % mobile)
            continue

        emay = EMay('sendSMS')
        response = emay.sync_fetch(
            serial_no=options.emay_serial_no,
            key=options.emay_key,
            send_time='',
            mobiles=mobile,
            sms_content=content.encode('utf-8'),
            add_serial='',
            src_charset='utf-8',
            sms_priority='5',
            sms_id=sms_id,
        )
        emay.parse_response(response)
        if emay.is_ok():
            redis.lrem(options.queue_coupon_send_processing, 0, message_raw)
            logging.info('re-send sms successfully: %s' % content)
        else:
            logging.error('re-send sms failed, emay response error: %s', emay.message.findtext('.//return'))

    logging.info('----- coupon sms sender consumer shut down -----')

    # 短信通道注册 仅在第一次使用时需要
    #emay = EMay('registEx')
    #response = emay.sync_fetch(
    #    serial_no=options.emay_serial_no,
    #    key=options.emay_key,
    #    password=options.emay_password
    #)


    # 查询余额
    #emay = EMay('getBalae')
    #response = emay.sync_fetch(
    #serial_no=options.emay_serial_no,
    #key=options.emay_key)
    #emay.parse_response(response)
    #if emay.is_ok():
    #    print emay.message.findtext('.//return')


if __name__ == '__main__':
    common.set_up()

    main_loop()
