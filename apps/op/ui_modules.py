# -*- coding: utf-8 -*-
import tornado.web
from menu import menu_data


class MenuModule(tornado.web.UIModule):
    def render(self, menu_key):
        return self.render_string('ui_modules/menu.html', menu_data=menu_data, menu_key=menu_key)


class SupplierSelect(tornado.web.UIModule):
    def render(self, action, method='get', goods_id=''):
        return self.render_string('ui_modules/supplier_select.html', action=action, goods_id=goods_id, method=method)


class SupplierMenu(tornado.web.UIModule):
    def render(self, menu_key, supplier_id):
        return self.render_string('ui_modules/supplier_menu.html', menu_key=menu_key, supplier_id=supplier_id)


class CouponDelay(tornado.web.UIModule):
    def render(self, action):
        return self.render_string('ui_modules/coupon_delay.html', action=action)
