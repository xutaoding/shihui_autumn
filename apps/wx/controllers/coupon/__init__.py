# -*- coding: utf-8 -*-

from .. import BaseHandler
from tornado.web import authenticated
from autumn.goods import img_url
from autumn.torn.paginator import Paginator
import json


class List(BaseHandler):
    @authenticated
    def get(self):
        list_type = self.get_argument('type', 'unused')

        sql = """select i.goods_name, g.img_paths, i.created_at, i.id
                 from orders o join item i on o.id = i.order_id
                    join item_coupon ic on i.id = ic.item_id
                    join goods g on i.goods_id = g.id
                 where o.distributor_user_id = %%s and i.used_at is %s null order by i.created_at desc"""

        add_str = '' if list_type == 'unused' else 'not'

        coupons = Paginator(self, sql % add_str, [self.current_user.wx_id], page_size=10)

        self.render('coupon/list.html', type=list_type, coupons=coupons, img_url=img_url, json=json)


class Detail(BaseHandler):
    @authenticated
    def get(self):
        coupon_id = self.get_argument('coupon')

        sql = """select i.used_at, ic.sn, i.goods_id, g.detail, i.goods_name, g.img_path, ic.expire_at
                 from item i join item_coupon ic on i.id = ic.item_id
                    join orders o on i.order_id = o.id
                    join goods g on i.goods_id = g.id
                 where i.id = %s and o.distributor_user_id = %s"""
        coupon = self.db.get(sql, coupon_id, self.current_user.wx_id)

        self.render('coupon/detail.html', coupon=coupon, img_url=img_url)