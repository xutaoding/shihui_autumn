# -*- coding: utf-8 -*-

import logging
import re
from tornado.options import options
from autumn import const
from autumn.utils import json_dumps
from datetime import datetime, timedelta, date, time


class SMSMessage(object):
    """
    短信（可群发）对象, 用于推到短信发送队列中
    """

    SIGN = '【一百券】'

    def __init__(self, content, phone_numbers, **kwargs):
        self.content = content
        self.phone_numbers = phone_numbers.split(',')
        self.code = kwargs.get('code', '0000')
        self.set_content_sign()

    def get_content(self):
        return self.content

    def get_phone_numbers(self):
        return self.phone_numbers

    def get_code(self):
        return self.code

    def set_content_sign(self):
        if not self.content.endswith(self.SIGN):
            self.content += self.SIGN

    def send(self, redis):
        self.set_content_sign()
        # 放入短信发送队列
        for number in self.phone_numbers:
            redis.lpush(options.queue_coupon_send, json_dumps({'sms': self.content, 'mobile': number, 'retry': 0}))

    def to_string(self):
        result = 'SMSMessage [content=' + self.content + ',code=' + self.code \
                 + ',phones=' + ','.join(self.phone_numbers) + ']'
        return result


class CouponConsumedMessage(object):
    """
    根据券号列表和验证门店生成券消费确认短信，并推送到发送队列
    用法：CouponConsumedMessage(redis,coupon_sns,shop, mobile).send()
    """

    def __init__(self, redis, coupon_sns, shop, mobile):
        self.redis = redis
        self.coupon_sns = coupon_sns
        self.shop = shop
        self.mobile = mobile

    def send(self):
        if not self.mobile:
            logging.info('发送券号%s消费确认短信失败：手机号码为空', ','.join(self.coupon_sns))
            return

        now = datetime.now().strftime('%m月%d日%H时%M分')
        message = '您' + ','.join(['尾号%s' % sn[-4:] for sn in self.coupon_sns]) + '的券于' + now + '成功消费,' \
                  '验证门店:' + self.shop + ',客服4006865151【一百券】'
        logging.info('发送给手机%s消费确认短信：%s' % (self.mobile, message))
        self.redis.lpush(options.queue_coupon_send, json_dumps({'mobile': self.mobile, 'sms': message, 'retry': 0}))


class CouponSMSMessage(object):
    """
    生成订单和券相关的短信内容,并推送到短信发送队列
    用法：
        根据券发送 CouponSMSMessage(db,redis,coupon=coupon).mobile(13812341234).remark('重发').operator(user).send()
        根据订单项目发送 CouponSMSMessage(db.redis, order_item=item).mobile(13812341234).remark('重发').operator(user).send()
    """
    KEFU = ',客服4006865151【一百券】'

    def __init__(self, db, redis, **kwargs):
        """
        根据 传入参数不同，初始化不同的短信内容构造器
        :type db: torndb.Connection
        :type redis: redis.client.StrictRedis
        :param kwargs: coupon 或者 order_item
        """
        self.db = db
        self.redis = redis
        self.params = {
            'mobile': None,
            'target_mobile': None,
            'operator': 'System',
            'remark': '',
            'sms_content': [],
        }
        if kwargs.get('coupon'):
            self.coupon = kwargs.get('coupon')
            # 为了防止传入的coupon 不能获得id
            self.cid = self.db.get('select id from item_coupon where sn=%s', self.coupon.sn).id
            self.is_coupon = True
        elif kwargs.get('order_item'):
            self.order_item = kwargs.get('order_item')
            self.is_coupon = False

    def mobile(self, mobile):
        """
        非必须
        :param mobile: 指定一个短信接受手机，可以与Coupon的mobile 不同
        """
        self.params['mobile'] = str(mobile)
        return self

    def remark(self, remark):
        """
        非必须
        :param remark: 记录日志时的备注
        """
        self.params['remark'] = remark
        return self

    def operator(self, operator):
        """
        非必须
        :param operator: 记录发送短信指令的操作员
        """
        self.params['operator'] = operator
        return self

    def create_coupon_sms(self):
        """
        根据券，生成单条短信内容
        """
        if can_send_by_operator(self.db, self.coupon):
            order_item = self.db.get('select * from order_item where id=%s', self.coupon.order_item_id)
            self.params['sms_content'] = [self.get_content(order_item, [self.coupon])]
            self.params['sms_id'] = '1' + str(self.cid)
            return self
        else:
            logging.error('Coupon id=%s status is not UNCONSUMED, cannot send SMS', self.cid)
            return self

    def create_order_item_sms(self):
        """
        根据订单项目，生成多条对应的短信内容
        """
        coupons = self.db.query('select *, c.id as cid from item i, item_coupon c '
                                'where i.id=c.item_id and i.order_item_id=%s', self.order_item.id)
        if not coupons:
            # 订单项下面不存在coupon，直接返回
            logging.error('no coupon found under order_item id =%s', self.order_item.id)
            return self

        send_coupons = []
        # 筛选可以发送短信的券
        for coupon in coupons:
            if can_send_by_operator(self.db, coupon):
                send_coupons.append(coupon)
        if len(send_coupons) == 0:
            logging.error('order_item id=%s does not have sendable coupon(s)', self.order_item.id)
            return self

        # 如果没密码18张券一个长短信，有密码则8张一个长短信
        if send_coupons[0].pwd:
            sms_coupon_size = 8
        else:
            sms_coupon_size = 18
        # 把所有券根据sms_coupon_size分组
        groups = [send_coupons[x:x+sms_coupon_size] for x in xrange(0, len(send_coupons), sms_coupon_size)]
        # 生成短信
        for group in groups:
            self.params['sms_content'].append(self.get_content(self.order_item, group))

        self.params['sms_id'] = '2' + str(self.order_item.id)

        return self

    def get_content(self, order_item, coupons_list):
        """
        拼接单条短信内容
        :param order_item: 单个订单项目
        :param coupons_list: 该订单项目下所有的券的列表
        """
        # 没有传入电子券，直接返回
        room_types = {'MINI': '迷你包', 'SMALL': '小包', 'MIDDLE': '中包', 'LARGE': '大包', 'DELUXE': '豪华包'}
        if len(coupons_list) == 0:
            logging.error('OrderItem id=%s does not contains any e-coupons!')
            return

        ktv_order = self.db.get('select k.*, p.duration from ktv_order k, ktv_product p '
                                'where k.order_item_id=%s and k.product_id=p.id',
                                order_item.id)
        is_ktv = True if ktv_order else False

        coupon_sns = []
        expire = ''
        content = ''
        for coupon in coupons_list:
            # 获得券关联的接受手机
            self.params['target_mobile'] = coupon.mobile
            # 更新短信已发送条数
            self.db.execute('update item_coupon set sms_sent_count=sms_sent_count+1 where sn=%s', coupon.sn)
            # 券有密码，生成带密码的券格式
            if coupon.pwd:
                coupon_sns.append('券号' + coupon.sn + '密码' + coupon.pwd)
            else:
                # KTV 订单，添加包厢时间
                if is_ktv:
                    supplier_short_name = self.db.get('select short_name from supplier where id=%s',
                                                      coupon.sp_id).short_name
                    content = content + supplier_short_name + ':'
                    duration = timedelta(hours=ktv_order.duration)
                    hour = timedelta(hours=ktv_order.scheduled_time)
                    day = ktv_order.scheduled_day
                    clock = time(0, 0)
                    start_time = datetime.combine(day, clock) + hour
                    end_time = start_time + duration
                    coupon_sns.append('券号' + coupon.sn + '预约日期' + start_time.strftime('%m月%d日%H时')
                                      + '至' + end_time.strftime('%H时') + ',' +
                                      room_types.get(ktv_order.room_type) + str(coupon.payment) + '元')
                else:
                    coupon_sns.append('券号' + coupon.sn)
            expire = coupon.expire_at.strftime('%Y年%m月%d日')

        coupon_info = ','.join(coupon_sns)
        # if len(coupon_sns) > 1:
        #     coupon_info += '[共' + str(len(coupon_sns)) + '张]'

        goods = self.db.get('select sms_name,short_name from goods where id=%s', order_item.goods_id)
        sms_name = goods.sms_name if goods.sms_name else goods.short_name

        # 拼接内容
        content = content + sms_name + ',' + coupon_info
        if not is_ktv:
            content = content + ',' + '至' + expire + '有效'
        content += self.KEFU
        logging.info('generate SMS content: %s' % content)
        return content

    def send(self):
        # 根据传入类型，生成对应短信内容
        if self.is_coupon:
            self.create_coupon_sms()
        else:
            self.create_order_item_sms()

        if not self.params['sms_content']:
            logging.error('failed to generate sms contents')
        else:
            if self.params['mobile'] and str(self.params['mobile']) != str(self.params['target_mobile']):
                # 发送到指定手机
                self.params['target_mobile'] = self.params['mobile']
                self.params['remark'] += ' 发送到新手机: %s' % self.params['mobile']

            for content in self.params['sms_content']:
                # 推入短信发送队列
                self.redis.lpush(options.queue_coupon_send, json_dumps({'mobile': self.params['target_mobile'],
                                                                        'sms': content,
                                                                        'retry': 0,
                                                                        'sms_id': self.params['sms_id']}))
                if self.is_coupon:
                    # 记录券发送日志
                    self.db.execute('insert into journal set created_at=now(), type=2, created_by=%s, '
                                    'message=%s, iid=%s', self.params['operator'],
                                    '发送电子券短信到%s, 内容：%s， 备注：%s' %
                                    (self.params['target_mobile'], hide_coupon_sn(content), self.params['remark']),
                                    self.cid)
                    logging.info('push to redis: send coupon(id=%s) sms to %s, content=%s ' %
                                 (self.cid, self.params['target_mobile'], content))
                else:
                    # 记录订单发送日志
                    self.db.execute('insert into journal set created_at=now(), type=1, created_by=%s, '
                                    'message=%s, iid=%s', self.params['operator'],
                                    '发送电子券短信到手机%s, 内容：[%s]， 备注：%s' %
                                    (self.params['target_mobile'], hide_coupon_sn(content), self.params['remark']),
                                    self.order_item.order_id)

                    # 同时记录到订单下所有券上
                    cids = self.db.query('select c.id from item i, item_coupon c where i.id = c.item_id '
                                         'and i.order_item_id=%s', self.order_item.id)
                    for c in cids:
                        self.db.execute('insert into journal set created_at=now(), type=2, created_by=%s, '
                                        'message=%s, iid=%s', self.params['operator'],
                                        '发送电子券短信到%s, 内容：%s， 备注：%s' %
                                        (self.params['target_mobile'], hide_coupon_sn(content), self.params['remark']),
                                        c.id)

                    logging.info('push to redis: send order_item(id=%s) sms to %s, content=%s ' %
                                 (self.order_item.id, self.params['target_mobile'], content))


def hide_coupon_sn(content):
    ptn = re.compile('券号\d+')
    tags = re.findall(ptn, content)
    for tag in tags:
        content = re.sub(tag, '券号(隐藏)', content)
    return content


def can_send_by_operator(db, coupon):
    goods = db.get('select g.generate_type from goods as g where g.id=%s', coupon.goods_id)
    return coupon.status == const.status.BUY or goods.generate_type == 'IMPORT' and coupon.status == const.status.USED

