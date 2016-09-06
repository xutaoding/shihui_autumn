# -*- coding: utf-8 -*-
from datetime import datetime, date, timedelta
from decimal import Decimal
import json
from tornado.options import options


class PropDict(dict):
    """A dict that allows for object-like property access syntax."""
    def __getattr__(self, name):
        return self[name] if name in self else None


class EmptyDict(dict):
    """A dict that allows for object-like property access syntax."""
    def __getattr__(self, name):
        return self[name] if name in self else ''


des_padding = lambda s: s + (8 - len(s) % 8) * chr(8 - len(s) % 8)
aes_padding = lambda s: s + (16 - len(s) % 16) * chr(16 - len(s) % 16)
des_unpadding = aes_unpadding = lambda s: s[0:-ord(s[-1])]


def json_default(dt_fmt='%Y-%m-%d %H:%M:%S', date_fmt='%Y-%m-%d', decimal_fmt=str):
    def _default(obj):
        if isinstance(obj, datetime):
            return obj.strftime(dt_fmt)
        elif isinstance(obj, date):
            return obj.strftime(date_fmt)
        elif isinstance(obj, Decimal):
            return decimal_fmt(obj)
        else:
            raise TypeError('%r is not JSON serializable' % obj)
    return _default


def json_dumps(obj, dt_fmt='%Y-%m-%d %H:%M:%S', date_fmt='%Y-%m-%d', decimal_fmt=str, ensure_ascii=False):
    return json.dumps(obj, ensure_ascii=ensure_ascii, default=json_default(dt_fmt, date_fmt, decimal_fmt))


def json_hook(pairs):
        """ convert json object to python object """
        o = JsonDict()
        for k, v in pairs.iteritems():
            o[mix_str(k)] = v
        return o


def json_obj_hook(pairs):
    """ convert json object to python object
        这个版本的键、值都尝试转化为 utf-8
    """
    o = JsonDict()
    for k, v in pairs.iteritems():
        o[mix_str(k)] = mix_str(v) if isinstance(v, basestring) else v
    return o


def mix_str(s, ec='utf-8'):
    return s.encode(ec) if isinstance(s, unicode) else str(s)


class JsonDict(dict):
    """ general json object that allows attributes to be bound to and also behaves like a dict """

    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            raise AttributeError(r"'JsonDict' object has no attribute '%s'" % attr)

    def __setattr__(self, attr, value):
        self[attr] = value


def send_email(redis, subject, to_list, html, plain=''):
    """
    :param redis:   redis实例
    :param subject: 邮件标题
    :param to_list: 收件人列表，逗号 (,) 分割
    :param html:    富文本格式的内容
    :param plain:   纯文本格式的内容
    :return:
    """
    redis.lpush(options.queue_email, json_dumps({
        'subject': subject,
        'to_list': to_list,
        'html':    html,
        'plain':   plain
    }))


def generate_duration(start_arg, end_arg):
    """根据参数确定时间轴范围"""
    # 没指定日期，默认显示7天
    if not start_arg or not end_arg:
        today = date.today()
        start = today - timedelta(days=6)
        end = today - timedelta(days=0)
        duration = (end - start).days + 1
    else:
        start = datetime.strptime(start_arg, '%Y-%m-%d').date()
        end = datetime.strptime(end_arg, '%Y-%m-%d').date()
        duration = (end - start).days + 1
    # 根据时间间隔获得时间轴
    categories = [(start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(duration)]

    return categories, start, end


def format_chart_data(data, start, categories):
    """将data中的数据补全成catagories的长度，data中的时间必须是升序排列"""
    if not data:
        return [[cate, Decimal(0)] for cate in categories]

    result = []
    length = len(data)
    index = 0
    current_day = start
    for i in range(len(categories)):
        if index < length and current_day == data[index].archive_date:
            result.append(data[index].amount)
            index += 1
        else:
            result.append(Decimal(0))
        current_day += timedelta(days=1)

    return [[categories[i], result[i]] for i in range(len(categories))]