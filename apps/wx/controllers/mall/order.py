# -*- coding: utf-8 -*-

from .. import BaseHandler
from tornado.web import authenticated
from autumn.torn.paginator import Paginator


class List(BaseHandler):
    """所有订单显示"""
    @authenticated
    def get(self):
        sql = """select g.short_name, oi.num, o.status, o.created_at, o.payment, o.id
                from orders o, order_item oi, goods g
                where o.id = oi.order_id and oi.goods_id = g.id and o.distributor_user_id = %s
                order by o.created_at desc"""
        params = [self.current_user.wx_id]

        page = Paginator(self, sql, params)

        self.render('mall/order_list.html', page=page)


class Detail(BaseHandler):
    """显示订单详情"""
    @authenticated
    def get(self):
        order_id = self.get_argument('order_id')

        sql = """select g.short_name, oi.num, o.status, o.created_at, o.payment, o.id, g.id gid, g.type, o.mobile,
                oi.shipping_info_id, o.post_fee
                from orders o join order_item oi on o.id = oi.order_id
                join goods g on oi.goods_id = g.id
                where o.distributor_user_id = %s and o.id = %s """

        order = self.db.get(sql, self.current_user.wx_id, order_id)

        shipping_info = {}
        sn = {}
        if order.type == 'E' and order.status == 2:
            sn_sql = """select ic.sn
                        from item i join item_coupon ic on i.id = ic.item_id
                        where i.order_id = %s"""
            sn = self.db.query(sn_sql, order.id)
        else:
            shipping_info_sql = """select osi.receiver, osi.zip_code, ec.name express, osi.address, osi.express_number
                                   from order_shipping_info osi left join express_company ec
                                      on osi.express_company_id = ec.id
                                   where osi.id = %s"""
            shipping_info = self.db.get(shipping_info_sql, order.shipping_info_id)

        self.render('mall/order_detail.html', order=order, shipping_info=shipping_info, sn=sn)
