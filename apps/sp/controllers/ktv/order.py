# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from datetime import datetime, timedelta, date


class OrderList(BaseHandler):
    @require('clerk')
    def get(self):
        day = self.get_argument('day', '')
        ten_minutes_ago = datetime.now() - timedelta(seconds=600)
        today = date.today()

        sql = """select o.*, g.duration, (select ss.name from supplier_shop ss where ss.id = o.shop_id) name ,
                 (select osi.mobile from order_item oi left join orders osi on oi.order_id = osi.id
                 where oi.id = o.order_item_id ) phone
                 from ktv_order o left join ktv_product g
                 on o.product_id = g.id where o.scheduled_day = %s and (o.status = "DEAL" or
                 (o.status = "LOCK" and o.created_at >= %s)) and g.supplier_id = %s """
        params = [self.get_argument('day', today), ten_minutes_ago, self.current_user.supplier_id]
        shop = self.get_argument('shop', '')
        if shop != '':
            sql += 'and o.shop_id = %s '
            params.append(shop)

        sql += 'order by o.scheduled_time '
        order_list = self.db.query(sql, *params)
        order_range_list = {}
        for order in order_list:
            time_duration = str(order.scheduled_time) + u'至' + str(order.scheduled_time + order.duration)
            if time_duration not in order_range_list.keys():
                order_range_list[time_duration] = {'MINI': [], 'SMALL': [], 'MIDDLE': [], 'LARGE': [], 'DELUXE': []}
            order_info = order.name + '(' + (order.phone if order.phone else '') + ')'
            order_range_list[time_duration][order.room_type].append(order_info)
        shop_list = self.db.query('select id, name from supplier_shop where supplier_id = %s', self.current_user.supplier_id)

        self.render('ktv/daily/show.html', order_range_list=order_range_list, shop_list=shop_list, shop=shop, day=day)


class CouponList(BaseHandler):
    @require('clerk')
    def get(self):
        phone = self.get_argument('number', '')
        if not phone:
            self.render('ktv/daily/book_coupon.html', coupon_list=[])
            return

        sql = """select ic.sn, i.status, ic.expire_at, i.created_at,k.room_type,k.scheduled_day,ss.name shop_name,
                k.scheduled_time,kp.name from item i, item_coupon ic,ktv_order k,ktv_product kp,supplier_shop ss
                where i.id = ic.item_id and k.order_item_id=i.order_item_id and k.product_id=kp.id and
                ss.id=k.shop_id and ic.mobile = %s and i.sp_id = %s order by i.id desc"""
        params = [phone, self.current_user.supplier_id]
        coupon_list = self.db.query(sql, *params)

        self.render('ktv/daily/book_coupon.html', coupon_list=coupon_list, now=datetime.now(), phone=phone)

