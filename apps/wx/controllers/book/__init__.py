# -*- coding: utf-8 -*-

from .. import BaseHandler
from tornado.httputil import url_concat
from tornado.web import authenticated
import json
from autumn.goods import img_url
from voluptuous import Schema
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator
from autumn.utils import json_hook

order = Schema({
    'custom': str,
    'phone': str,
    'date': str,
    'time': str,
    'remark': str,
    'shop_id': str
})


class List(BaseHandler):
    @authenticated
    def get(self):
        user = self.current_user
        if user.level == 0:
            # 不是会员，先跳转到加入会员页面
            self.redirect(url_concat(self.reverse_url('member_join'), {'wx_id': user.wx_id}))
        else:
            # 查询有效的预约信息
            sql = 'select id, info from wx_booking_setting where sp_id = %s and deleted=0'
            page = Paginator(self, sql, [user.sp_id], page_size=10)
            lists = [{'id': b.id, 'info': json.loads(b.info, object_hook=json_hook)} for b in page.rows]
            # 查询用户已提交的预约
            orders = self.db.get('select count(*) num from wx_booking where wx_id = %s',
                                 self.current_user.wx_id)['num']
            self.render('book/list.html', lists=lists, orders=orders, img_url=img_url, links=page.boot_links())


class Info(BaseHandler):
    @authenticated
    def get(self, book_id):
        book = self.db.get('select * from wx_booking_setting where sp_id = %s and id = %s and deleted=0 ',
                           self.current_user.sp_id, book_id)
        shops = []
        if book:
            book.info = json.loads(book.info)
            shops_id = book.shops.split(',')
            shops = self.db.query('select * from supplier_shop where supplier_id = %%s and id in (%s) ' %
                                  ','.join(['%s'] * len(shops_id)), self.current_user.sp_id, *shops_id)

        self.render('book/book.html', book=book, shops=shops, img_url=img_url)

    @authenticated
    def post(self, book_id):
        form = Form(self.request.arguments, order)

        self.db.execute('insert into wx_booking(sp_id, wx_id, phone, name, shop_id, remark, date, '
                        'time, status, created_at, wbs_id) '
                        'values(%s, %s, %s, %s, %s, %s, %s, %s, 1, NOW(), %s)',
                        self.current_user.sp_id, self.current_user.wx_id, form.phone.value, form.custom.value,
                        form.shop_id.value, form.remark.value, form.date.value, form.time.value, book_id)

        self.redirect(url_concat(self.reverse_url('book_list'), {'wx_id': self.current_user.wx_id}))


class Orders(BaseHandler):
    @authenticated
    def get(self):
        sql = """select wb.id, wb.name, wb.phone, wb.remark, wb.time, wb.date, wb.status,
                    wb.created_at, ss.name sname, wb.wbs_id
                 from wx_booking wb
                    join supplier_shop ss on wb.shop_id = ss.id
                 where wb.wx_id = %s order by wb.created_at desc"""
        page = Paginator(self, sql, [self.current_user.wx_id], page_size=10)

        self.render('book/orders.html', orders=page.rows, links=page.boot_links())


class Cancel(BaseHandler):
    @authenticated
    def post(self):
        order_id = self.get_argument('order_id')
        order = self.db.get('select status from wx_booking where id = %s and sp_id = %s',
                            order_id, self.current_user.sp_id)
        if order and order.status == 1:
            self.db.execute('update wx_booking set status=2 where id = %s and sp_id = %s',
                            order_id, self.current_user.sp_id)

        self.redirect(url_concat(self.reverse_url('book.orders'), {'wx_id': self.current_user.wx_id}))
