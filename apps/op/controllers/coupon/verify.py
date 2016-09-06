# -*- coding: utf-8 -*-

import logging
from autumn.utils import json_dumps
from .. import BaseHandler
from .. import require
from voluptuous import Schema
import tornado
from autumn.torn.form import Form
from autumn.coupon import partner_api_verify
from autumn.sms import CouponConsumedMessage
from datetime import datetime
from autumn.coupon import local_check, local_verify
from autumn import const
from decimal import Decimal
from autumn.utils.dt import ceiling
import tornado.gen


class CouponVerifyQuery(BaseHandler):
    @require('service')
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        coupon_sn = self.get_argument('coupon')
        if not coupon_sn:
            return self.write(json_dumps({'error': '请输入券号'}))
        coupon = self.db.get('select i.sp_id, i.goods_id, i.goods_name as gsname, i.sales_price, c.expire_at, i.status,'
                             ' c.id from item i, item_coupon c where c.sn = %s and i.id=c.item_id', coupon_sn)
        if not coupon:
            return self.write(json_dumps({'error': '券号不存在，请检查输入'}))

        if coupon.expire_at < datetime.now():
            return self.write(json_dumps({'error': '券号已过期', 'coupon': coupon}))

        if coupon.status != const.status.BUY:
            return self.write(json_dumps({'error': '券已使用或已退款', 'coupon': coupon}))

        # 查找可验证店铺
        all_shops = self.db.get('select all_shop from goods where id=%s', coupon.goods_id).all_shop
        if all_shops == '1':
            # 所有店铺
            shops = self.db.query('select s.id, s.name, s.supplier_name as spname from supplier_shop s '
                                  'where supplier_id=%s', coupon.sp_id)
        else:
            # 指定店铺
            shop_ids = self.db.query('select supplier_shop_id from goods_supplier_shop '
                                     'where goods_id=%s', coupon.goods_id)
            ids = ','.join([str(item.supplier_shop_id) for item in shop_ids])
            shops = self.db.query('select s.id, s.name, s.supplier_name as spname from supplier_shop s '
                                  'where s.id in (' + ids + ')')
        self.write(json_dumps({'coupon': coupon, 'shops': shops}))


class CouponVerify(BaseHandler):
    @require('service')
    def get(self):
        self.render('coupon/verify.html')

    @tornado.gen.coroutine
    @require('service')
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        coupon_sn = self.get_argument('coupon', '')
        shop_id = self.get_argument('shop', '')
        # 检查请求的参数
        if not coupon_sn or not shop_id:
            self.write(json_dumps({'error': '请输入正确参数'}))
            return

        # 检查电子券
        coupon = self.db.get('select * from item i, item_coupon c where c.sn=%s and i.id=c.item_id', coupon_sn)
        if not coupon:
            self.write(json_dumps({'error': '券号不存在'}))
            return

        # 查找可验证店铺
        all_shops = self.db.get('select all_shop from goods where id=%s', coupon.goods_id).all_shop
        if all_shops == '1':
            # 所有店铺
            shops = self.db.query('select s.id, s.name, s.supplier_name as spname from supplier_shop s '
                                  'where supplier_id=%s', coupon.sp_id)
        else:
            # 指定店铺
            shop_ids = self.db.query('select supplier_shop_id from goods_supplier_shop '
                                     'where goods_id=%s', coupon.goods_id)
            ids = ','.join([str(item.supplier_shop_id) for item in shop_ids])
            shops = self.db.query('select s.id, s.name, s.supplier_name as spname from supplier_shop s '
                                  'where s.id in (' + ids + ')')
        if int(shop_id) not in [i.id for i in shops]:
            self.write({'ok': False, 'msg': '验证门店错误'})
            return

        #  本地检测
        check_result = local_check(self.db, coupon_sn, shop_id)
        if not check_result.ok:
            self.write(json_dumps({'error': check_result.msg}))
            return

        #  合作伙伴API验证
        api_result = yield partner_api_verify(self.db, coupon_sn)
        if not api_result.ok:
            ok, msg = (False, api_result.msg)
        else:
            #  本地验证
            verify_result = local_verify(self.db, coupon_sn, shop_id, self.get_current_user().name)
            ok, msg = (verify_result.ok, verify_result.msg)

        if not ok:
            self.write(json_dumps({'error': '错误,原因:%s' % msg}))
        else:
            # 发送验证确认短信
            shop_name = self.db.get('select name from supplier_shop where id=%s', shop_id).name
            CouponConsumedMessage(self.redis, [coupon.sn], shop_name, coupon.mobile).send()
            self.write(json_dumps({'ok': '验证成功'}))


virtual_verify_list_schema = Schema({
    'mobile': str,
    'coupon': str,
    'order': str,
    'end_date': str,
    'start_date': str,
    'resaler_coupon': str,
}, extra=True)


class VirtualVerify(BaseHandler):
    """标记刷单"""
    @require()
    def get(self):
        form = Form(self.request.arguments, virtual_verify_list_schema)
        params = []
        #首次刷新返回空页面，加快速度
        if len(self.request.arguments) == 0:
            return self.render('coupon/virtual_verify.html', form=form, items=[], now=datetime.now())

        # 没有筛选参数，也返回空页面
        if not (form.mobile.value or form.order.value or form.end_date.value or form.start_date.value):
            return self.render('coupon/virtual_verify.html', form=form, items=[], now=datetime.now())

        sql = """select c.id, c.sn coupon_sn, c.expire_at, c.mobile, c.sp_sn spcoupon, c.distr_sn dcoupon,
        i.sales_price, i.status, i.order_no, i.order_id, i.goods_name, i.created_at,
        i.goods_id gid from item i, item_coupon c where i.status=1 and i.id=c.item_id """

        if form.mobile.value:
            sql += ' and c.mobile = %s '
            params.append(form.mobile.value)

        if form.order.value:
            sql += ' and i.order_no=%s '
            params.append(form.order.value)

        if form.end_date.value:
            sql += 'and i.created_at <= %s '
            params.append(form.end_date.value)

        if form.start_date.value:
            sql += 'and i.created_at > %s '
            params.append(form.start_date.value)

        sql += ' order by i.created_at desc'
        items = self.db.query(sql, *params)

        self.render('coupon/virtual_verify.html', form=form, items=items, now=datetime.now())

    @require('finance')
    @tornado.gen.coroutine
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        coupon_sn = self.get_argument('coupon_sn', '').encode('utf-8')
        logging.info('执行刷单, 券号: %s', coupon_sn)

        coupon = self.db.get('select c.id cid, i.*, c.* from item i, item_coupon c '
                             'where i.id=c.item_id and c.sn=%s', coupon_sn)
        # 券号错误，直接报错返回
        if not coupon:
            logging.error('刷单错误，券号%s不存在', coupon_sn)
            self.write({'ok': False})
            return

        # 商户刷单，获得手续费费率
        is_op = int(self.get_argument('is_op', ''))
        if not is_op:
            rate = Decimal(self.get_argument('rate', '')) / 100

        # 获得商户的第一个门店，在此门店验证
        shop = self.db.query(
            'select ss.* from supplier_shop ss,goods g where ss.supplier_id=g.supplier_id and g.id=%s and ss.deleted=0 '
            'and (g.all_shop=1 or ss.id in (select supplier_shop_id from goods_supplier_shop where goods_id=%s) ) ',
            coupon.goods_id, coupon.goods_id
        )[0]

        #  本地检测
        check_result = local_check(self.db, coupon_sn, shop.id)
        if not check_result.ok:
            logging.error('刷单错误，券号合法性检查失败')
            self.write({'ok': False})
            return
        else:
            # 发送第三方验证请求
            api_result = yield partner_api_verify(self.db, coupon_sn)
            if not api_result.ok:
                logging.info('刷单提醒，券号%s第三方验证未通过', coupon_sn)
                self.write({'ok': False})
                return
                # 本地验证
            verify_result = local_verify(self.db, coupon_sn, shop.id, self.get_current_user().name)
            if not verify_result.ok:
                logging.error('刷单错误，券号%s本地验证失败', coupon_sn)
                # 验证失败，返回
                self.write({'ok': False})
                return

            # 记录一条门店账务明细
            supplier_shop_account_id = self.db.get('select account_id from supplier_shop '
                                                   'where id=%s', shop.id).account_id
            if is_op:
                # 我们刷单，直接减去进价
                amount = - coupon.purchase_price
                remark = '刷单收回:%s, 商品:%s,售价:%s,付款:%s,' \
                         % (amount, coupon.goods_name, coupon.sales_price, coupon.payment)
                fee = Decimal(0)
            else:
                # 商户自己刷单，把扣除手续费后的差价还给商户
                diff = coupon.payment - coupon.purchase_price  # 差价
                fee = (coupon.payment * rate).quantize(Decimal('0.01'))  # 按付款金额的百分比收手续费
                amount = diff - fee  # 应返还
                remark = '协助商户刷单-扣除手续费:%s, 返还差价:%s, 合计返还:%s, 验证门店:%s, 商品:%s,售价:%s,付款:%s' \
                         % (fee, diff, amount, shop.name, coupon.goods_name, coupon.sales_price, coupon.payment)
            self.db.execute('insert into account_sequence(type, account_id, item_id,trade_type,trade_id,'
                            'amount,created_at,remark, status)'
                            'values (%s, %s, %s, 1, %s, %s, NOW(),%s,1)',
                            const.seq.CHEAT_ORDER, supplier_shop_account_id, coupon.item_id,
                            coupon.order_id, amount, remark)

            # 更新 item 状态
            cheat_value = coupon.purchase_price + fee  # 记录加上手续费后的进价，方便以后算刷单手续费
            self.db.execute('update item set cheat_value=%s, cheat_at=NOW() where item.id=%s',
                            cheat_value, coupon.item_id)

            # 如果是我们刷单，商户后台的账户流水中不予显示
            if is_op:
                logging.info('%s %s', supplier_shop_account_id, coupon.item_id)
                self.db.execute('update account_sequence set display=2 where account_id=%s and item_id=%s',
                                supplier_shop_account_id, coupon.item_id)

            # 记录虚拟验证日志
            record = """insert into journal (created_at, type, created_by, message, iid)
                        values (now(), 2, %s, %s, %s)"""
            user = self.get_current_user()
            message = "券 %s 刷单, 备注: %s" % (coupon_sn, remark)
            self.db.execute(record, user.name, message, coupon.cid)
            logging.info('刷单成功')
            self.write({'ok': True})
            return


class DistributorVerify(BaseHandler):
    @require('developer')
    def get(self):
        self.render('coupon/distributor_verify.html', result_list=[])

    @require('developer')
    @tornado.gen.coroutine
    def post(self):
        coupon_list = self.get_argument('coupons', '').splitlines()
        result_list = []
        for coupon in coupon_list:
            result = yield partner_api_verify(self.db, coupon)
            result_list.append(result)
        self.render('coupon/distributor_verify.html', result_list=result_list)
