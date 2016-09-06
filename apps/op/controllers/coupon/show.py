# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from voluptuous import Schema

from .. import BaseHandler
from .. import require
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator
from autumn.sms import CouponSMSMessage, can_send_by_operator


list_schema = Schema({
         'mobile': str,
         'coupon': str,
         'order': str,
         'end_date': str,
         'short_name': str,
         'start_date': str,
         'resaler_coupon': str,
         'start_used_at': str,
         'end_used_at': str,
         'start_refund_at': str,
         'end_refund_at': str,
         'start_cheat_at': str,
         'end_cheat_at': str,
}, extra=True)


class CouponList(BaseHandler):
    @require()
    def get(self):
        sql = """select c.id, c.sn coupon_sn, c.expire_at, c.mobile, c.sp_sn spcoupon, c.distr_sn dcoupon,
        i.sales_price, i.status, i.order_no, i.order_id, i.goods_name, i.created_at, i.distr_id,
        i.goods_id gid from item i, item_coupon c where i.id=c.item_id """

        form = Form(self.request.arguments, list_schema)
        params = []

        if form.mobile.value:
            sql += 'and c.mobile  = %s '
            params.append(form.mobile.value)

        if form.coupon.value:
            sql += 'and c.sn=%s '
            params.append(form.coupon.value)
        if form.order.value:
            sql += 'and i.order_no=%s '
            params.append(form.order.value)
        if form.short_name.value:
            sql += 'and i.goods_name like %s '
            params.append('%' + form.short_name.value + '%')

        if form.resaler_coupon.value:
            sql += 'and c.distr_sn=%s '
            params.append(form.resaler_coupon.value)

        if form.end_date.value:
            sql += 'and i.created_at <= %s '
            params.append(form.end_date.value)

        if form.start_date.value:
            sql += 'and i.created_at > %s '
            params.append(form.start_date.value)

        if form.end_used_at.value:
            sql += 'and i.used_at <= %s '
            params.append(form.end_used_at.value)

        if form.start_used_at.value:
            sql += 'and i.used_at > %s '
            params.append(form.start_used_at.value)

        if form.end_refund_at.value:
            sql += 'and i.refund_at <= %s '
            params.append(form.end_refund_at.value)

        if form.start_refund_at.value:
            sql += 'and i.refund_at > %s '
            params.append(form.start_refund_at.value)

        if form.end_cheat_at.value:
            sql += 'and i.cheat_at <= %s '
            params.append(form.end_cheat_at.value)

        if form.start_cheat_at.value:
            sql += 'and i.cheat_at > %s '
            params.append(form.start_cheat_at.value)

        sql += ' order by c.id desc'

        page = Paginator(self, sql, params)
        self.render('coupon/list.html', page=page, now=datetime.now(), form=form)


class CouponDetail(BaseHandler):
    """ 显示券详情 """
    @require()
    def get(self, id):
        # 券信息
        coupon = self.db.get('select i.*, c.*, c.id as cid, d.name as distributor_shop_name, d.distributor_name from '
                             'item i, item_coupon c, distributor_shop d '
                             'where c.id=%s and i.id=c.item_id and d.id = i.distr_shop_id', long(id))

        # 券验证操作信息
        verify_coupon = self.db.query('select * from journal where iid= %s and type=2 order by id desc', coupon.cid)

        # 重发短信要求：为消费的或者已消费的导入券， 并且未过期的，并且有手机号（去除导出券）的, 并且没超过发送次数限制10次的
        resend = can_send_by_operator(self.db, coupon) and datetime.now() < coupon.expire_at and coupon.mobile and coupon.sms_sent_count < 10

        self.render('coupon/detail.html', coupon=coupon, verify_coupon=verify_coupon, resend=resend)


class ResendSn(BaseHandler):
    """重发券号短信"""
    @require('sales', 'operator', 'finance', 'service')
    def post(self):
        coupon_sn = self.get_argument('coupon_sn', '')
        if not coupon_sn:
            self.write({'error': '券号为空'})
            return

        coupon = self.db.get('select i.*, c.* from item i, item_coupon c where i.id=c.item_id and c.sn=%s', coupon_sn)
        if not coupon:
            self.write({'error': '电子券不存在'})
            return

        if not datetime.now() < coupon.expire_at:
            self.write({'error': '过期电子券不能重发'})
            return

        if not coupon.mobile:
            self.write({'error': '手机号码为空，发送失败'})
            return

        if not coupon.sms_sent_count < 10:
            self.write({'error': '发送次数超过10次限制'})
            return

        if not can_send_by_operator(self.db, coupon):
            self.write({'error': '电子券当前状态不能执行重发操作'})
            return

        CouponSMSMessage(self.db, self.redis, coupon=coupon).remark('运营后台重发短信').operator(self.current_user.name).send()


class Journal(BaseHandler):
    @require('sales', 'operator', 'finance', 'service')
    def post(self):
        self.db.execute('insert into journal(created_at, type, created_by, iid, message) values(NOW(), 2, %s, %s, %s)',
                        self.current_user.name, self.get_argument('coupon_id'),
                        u'用户%s' % self.current_user.name.decode('utf-8') + u'查看了该券的完整券号')