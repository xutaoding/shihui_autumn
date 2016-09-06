# -*- coding: utf-8 -*-
import json
import common
import logging
import smtplib
from autumn.utils import json_hook
from tornado.options import options
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def main_loop():
    redis = common.redis_client()

    while common.running():
        email_raw = redis.brpoplpush(options.queue_email, options.queue_email_processing)
        email_json = json.loads(email_raw, object_hook=json_hook)

        smtp = smtplib.SMTP()
        smtp.connect(options.mail_smtp_host, 25)
        smtp.starttls()
        smtp.login(options.mail_smtp_user, options.mail_smtp_pwd)

        msg = MIMEMultipart('alternative')
        msg['From'] = options.mail_smtp_from
        msg['Subject'] = email_json.subject
        msg['To'] = email_json.to_list

        if 'text' in email_json:
            plain_part = MIMEText(email_json.text.encode('utf-8'), 'plain', 'utf-8')
            plain_part['Accept-Language'] = 'zh-CN'
            plain_part['Accept-Charset'] = 'ISO-8859-1,utf-8'
            msg.attach(plain_part)

        html_part = MIMEText(email_json.html.encode('utf-8'), 'html', 'utf-8')
        html_part['Accept-Language'] = 'zh-CN'
        html_part['Accept-Charset'] = 'ISO-8859-1,utf-8'
        msg.attach(html_part)

        receivers = email_json.to_list.split(',')
        smtp.sendmail(options.mail_smtp_from, receivers, msg.as_string())

        redis.lrem(options.queue_email_processing, 0, email_raw)
        logging.info(email_raw)

        smtp.close()


if __name__ == '__main__':
    common.set_up()

    main_loop()