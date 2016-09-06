# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
import re


class CouponFreeze(BaseHandler):
    """批量券冻结"""
    @require('service_mgr')
    def get(self):
        self.render('coupon/freeze.html')

    @require('service_mgr')
    def post(self):
        text_type = self.get_argument('input', '')
        text = self.get_argument('text', '')
        # 输入内容为空，直接返回
        if not text:
            return self.render('coupon/freeze_result.html', type='coupon', invalid_lines=[],
                               coupon_success=[], coupon_fail=[])

        invalid_lines = []
        invalid_orders = []
        order_success = []
        order_fail = []
        coupon_success = []
        coupon_fail = []
        temp_lines = []
        lines = text.splitlines()

        if 'coupon' == text_type:
            ptn = re.compile(r'^[0-9]{10}$')  # 券号10位，纯数字
        else:
            ptn = re.compile(r'^[0-9]{8}$')  # 订单号8位， 纯数字

        # 过滤非法券号和订单号
        for line in lines:
            if re.match(ptn, line.strip()):
                temp_lines.append(line.strip())
            else:
                invalid_lines.append(line)

        freeze_sql = """update item i join item_coupon c set i.status=6 where i.id=c.item_id and c.sn=%s"""
        # 如果输入为订单号，查询订单号下所有券号,并冻结
        if 'order' == text_type:
            sql = """select c.sn as coupon_sn, c.id as cid from item i, item_coupon c where i.id=c.item_id and i.order_no = %s"""
            for order_no in temp_lines:
                # 获取订单下所有券号
                coupon_sns = self.db.query(sql, order_no)
                if not coupon_sns:
                    invalid_orders.append(order_no)
                # 冻结每一个券号
                for coupon in coupon_sns:
                    coupon_sn = coupon.get('coupon_sn')
                    freeze_result = self.db.execute_rowcount(freeze_sql, coupon_sn)
                    if freeze_result:
                        order_success.append((order_no, coupon_sn))
                        # 记录日志
                        self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                                        'values (NOW(), 2, %s, %s, %s)',
                                        self.get_current_user().name,
                                        '券 %s 冻结' % coupon_sn.encode('utf-8'),
                                        coupon.cid)
                    else:
                        order_fail.append((order_no, coupon_sn))

            return self.render('coupon/freeze_result.html', type='order', invalid_lines=invalid_lines,
                               invalid_orders=invalid_orders, order_success=order_success, order_fail=order_fail)
        else:
        # 如果输入为券号，直接冻结
            for coupon_sn in temp_lines:
                freeze_result = self.db.execute_rowcount(freeze_sql, coupon_sn)
                if freeze_result:
                    coupon_success.append(coupon_sn)
                    coupon_id = self.db.get('select id from item_coupon where sn=%s', coupon_sn).id
                    # 记录日志
                    self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                                    'values (NOW(), 2, %s, %s, %s)',
                                    self.get_current_user().name,
                                    '券 %s 冻结' % coupon_sn.encode('utf-8'),
                                    coupon_id)
                else:
                    coupon_fail.append(coupon_sn)

            return self.render('coupon/freeze_result.html', type='coupon', invalid_lines=invalid_lines,
                               coupon_success=coupon_success, coupon_fail=coupon_fail)