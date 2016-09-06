# -*- coding: utf-8 -*-

from ... import BaseHandler, require
from autumn.torn.paginator import Paginator
import json


class List(BaseHandler):
    @require()
    def get(self):
        sql = """select wx.*, ss.name sname, wbs.info
                 from wx_booking wx join supplier_shop ss on wx.shop_id = ss.id
                    join wx_booking_setting wbs on wx.wbs_id = wbs.id
                 where wx.sp_id = %s order by wx.created_at desc """

        args = [self.current_user.supplier_id]
        date = ''
        shop = 0
        if 'date' in self.request.arguments and self.get_argument('date'):
            date = self.get_argument('date')
            sql += 'and wx.date = %s '
            args.append(self.get_argument('date'))
        if 'shop' in self.request.arguments and self.get_argument('shop'):
            shop = self.get_argument('shop')
            sql += 'and wx.shop_id = %s '
            args.append(self.get_argument('shop'))

        orders = Paginator(self, sql, args)
        shops = self.db.query('select id, name from supplier_shop where supplier_id = %s',
                              self.current_user.supplier_id)

        params = {
            'orders': orders,
            'shops': shops,
            'date': date,
            'shop': shop,
            'json': json
        }
        self.render('wx/book/order.html', **params)


class Handle(BaseHandler):
    @require()
    def post(self):
        oid = self.get_argument('oid', 0)
        status = self.get_argument('status', 1)
        book = self.db.get('select status from wx_booking where id = %s and sp_id = %s',
                           oid, self.current_user.supplier_id)
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        if book and book.status == 1:
            self.db.execute('update wx_booking set status = %s where id = %s and sp_id = %s',
                            status, oid, self.current_user.supplier_id)

            self.write({'ok': True})
        else:
            self.write({'ok': False})
