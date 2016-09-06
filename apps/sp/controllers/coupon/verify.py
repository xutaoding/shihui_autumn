# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
import tornado.gen
from tornado.options import options
from voluptuous import Schema
from autumn.coupon import local_verify, local_check, partner_api_verify, partner_browser_verify
from autumn.order import new_distributor_order, new_distributor_item
from autumn.torn.form import Form
from autumn.utils import json_dumps, PropDict
from autumn.torn.paginator import Paginator
from autumn.sms import CouponConsumedMessage
from autumn import const
from datetime import datetime
import re


class Verify(BaseHandler):
    @require('clerk', 'finance')
    def get(self):
        all_shops = self.db.query('select ss.* from supplier_shop ss, supplier_user su where ss.deleted = 0 and '
                                  'ss.supplier_id=%s and su.id=%s and su.supplier_id=ss.supplier_id and '
                                  '(su.shop_id=0 or ss.id=su.shop_id)',
                                  self.current_user.supplier_id, self.current_user.id)

        self.render('coupon/verify.html', all_shops=all_shops)

    @require('clerk', 'finance')
    @tornado.gen.coroutine
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        coupon_list = [i.strip() for i in self.get_argument('coupons', '').split(',') if i.strip()]
        if len(coupon_list) == 0:
            self.write({'ok': False, 'msg': u'请输入券号'})
            return
        shop_id = self.get_argument('shop_id', 0)
        #这一步是检查该操作员是否有权限验证券
        all_shops = self.db.query('select ss.* from supplier_shop ss, supplier_user su where ss.supplier_id=%s and '
                                  'ss.deleted=0 and su.id=%s and su.supplier_id=ss.supplier_id and '
                                  ' (su.shop_id=0 or ss.id=su.shop_id)',
                                  self.current_user.supplier_id, self.current_user.id)
        if int(shop_id) not in [i.id for i in all_shops]:
            self.write({'ok': False, 'msg': u'对不起，您无权执行此操作'})
            return

        is_our_coupon = False
        coupon_length = 0
        messages = PropDict()  # 用来存不同的手机号对应的券号
        #检测长度是否相同、是否是我们的券
        for coupon_sn in coupon_list:
            coupon = self.db.get('select id, sn, mobile from item_coupon where sn=%s', coupon_sn)
            if coupon:
                is_our_coupon = True
            if coupon_length == 0:
                coupon_length = len(coupon_sn)
            elif coupon_length != len(coupon_sn):
                coupon_length = -1
        if coupon_length == -1:
            self.write({'ok': False, 'msg': u'券号长度必须一致'})
            return

        result_list = []
        if is_our_coupon:
            # 我们自己的券
            for coupon_sn in coupon_list:
                #  本地检测
                check_result = local_check(self.db, coupon_sn, shop_id)
                if not check_result.ok:
                    ok, msg = (False, check_result.msg)
                else:
                    #  合作伙伴API验证
                    api_result = yield partner_api_verify(self.db, coupon_sn)
                    if not api_result.ok:
                        ok, msg = (False, api_result.msg)
                    else:
                        #  本地验证
                        verify_result = local_verify(self.db, coupon_sn, shop_id, self.current_user.name)
                        ok, msg = (verify_result.ok, verify_result.msg)
                        # 验证通过，记录需要发送确认短信的券
                        if ok:
                            if messages.get(str(check_result.coupon.mobile)):
                                # 手机号已存在，添加券号到对应手机号
                                messages.get(str(check_result.coupon.mobile)).append(str(coupon_sn))
                            else:
                                # 手机号不存在，新建K-V对
                                messages.update({str(check_result.coupon.mobile): [str(coupon_sn)]})

                result_list.append({'coupon_sn': coupon_sn, 'ok': ok, 'msg': msg})
        else:
            mobile = self.get_argument('mobile', '')
            # 检查手机号合法性
            mobile_ptn = re.compile('^1[\d+]{10}$')
            if not re.match(mobile_ptn, mobile):
                # 不合法手机号，不记录
                mobile = ''

            # 尝试外部验证
            results = yield partner_browser_verify(self.db, coupon_list, shop_id)
            for result in results:
                if result.ok:
                    goods_info = self.db.get('select g.* from goods g where id=%s', result.goods_id)
                    verify_infos = {'goods_id': result.goods_id, 'shop_id': shop_id}
                    #创建分销订单
                    distributor_order_id = self.db.execute(
                        'insert into distributor_order(order_no, message, distributor_shop_id, created_at) '
                        'values (%s, %s, %s, NOW())', result.coupon_sn, json_dumps(verify_infos), result.distributor_shop_id)
                    order_id, order_no = new_distributor_order(self.db, result.distributor_shop_id,
                                                               goods_info.sales_price, goods_info.sales_price, mobile)
                    #记录订单信息
                    new_order = new_distributor_item(
                        db=self.db,
                        order_id=order_id,
                        order_no=order_no,
                        sales_price=None,
                        count=1,
                        goods_info=goods_info,
                        mobile=mobile,
                        distributor_shop_id=result.distributor_shop_id,
                        distributor_goods_id='',
                        distributor_coupons=[{'coupon_sn': result.coupon_sn, 'coupon_pwd': result.coupon_pwd or ''}],
                        use_distributor_coupon=True
                    )
                    if new_order.ok:
                        #更新分销订单id
                        self.db.execute('update orders set distributor_order_id=%s where id = %s',
                                        distributor_order_id, order_id)
                        #更新订单id
                        self.db.execute('update distributor_order set order_id=%s where id=%s',
                                        order_id, distributor_order_id)
                        #更新该券验证的门店
                        self.db.execute('update item set sp_shop_id = %s where order_id=%s', shop_id, order_id)
                        self.redis.lpush(options.queue_coupon_local_verify, json_dumps({'coupon': result.coupon_sn,
                                         'shop_id': shop_id, 'retry': 0, 'used_at': datetime.now()}))
                result_list.append({'coupon_sn': result.coupon_sn, 'coupon_pwd': result.coupon_pwd or '',
                                    'ok': result.ok, 'msg': result.msg})

        # 如果有合法券号，发送确认短信
        if messages:
            shop_name = self.db.get('select name from supplier_shop where id=%s', shop_id).name
            for mobile, coupon_sns in messages.items():
                CouponConsumedMessage(self.redis, coupon_sns, shop_name, mobile).send()

        self.write({'ok': True, 'result': result_list})


class ShowList(BaseHandler):
    @require('clerk', 'finance')
    def get(self):
        form = Form(self.request.arguments, list_schema)
        sql = 'select i.*,c.sn,c.mobile,c.id cid,s.name, ds.name dsname from item i,item_coupon c,supplier_shop s, ' \
              'distributor ds where i.id=c.item_id and s.id=i.sp_shop_id and i.sp_id = %s and s.deleted =0 ' \
              'and ds.id=i.distr_id and i.cheat_at is null and i.status = %s '
        params = [self.current_user.supplier_id, const.status.USED]
        if form.sn.value:
            sql += ' and c.sn=%s'
            params.append(form.sn.value)
        if form.mobile.value:
            sql += ' and c.mobile=%s'
            params.append(form.mobile.value)
        if form.start_date.value:
            sql += ' and cast(i.used_at as Date) >= %s '
            params.append(form.start_date.value)
        if form.end_date.value:
            sql += ' and cast(i.used_at as Date) <= %s '
            params.append(form.end_date.value)

        sql += 'order by i.used_at desc'
        page = Paginator(self, sql, params)

        self.render('coupon/list.html', page=page, form=form)


list_schema = Schema({
    'sn': str,
    'mobile': str,
    'start_date': str,
    'end_date': str,
}, extra=True)
