# -*- coding: utf-8 -*-

from ... import BaseHandler
from ... import require
import json
from autumn.utils import json_dumps
from autumn.torn.paginator import Paginator
from autumn.goods import img_url


class List(BaseHandler):
    @require()
    def get(self):
        sql = """select id, info from wx_booking_setting where sp_id = %s and deleted = 0 order by op_time desc """
        page = Paginator(self, sql, [self.current_user.supplier_id])
        for item in page.rows:
            item.info = json.loads(item.info)
            item.info['pic'] = img_url(item.info['pic'])

        self.render('wx/book/list.html', page=page)


class Add(BaseHandler):
    @require()
    def get(self):
        shops = self.db.query('select * from supplier_shop where deleted = 0 and supplier_id = %s',
                              self.current_user.supplier_id)
        params = {
            'shops': shops,
            'action': 'add'
        }
        self.render('wx/book/book.html', **params)

    @require()
    def post(self):
        params = dict([(name, self.get_argument(name).encode('utf-8')) for name in self.request.arguments])

        # 为了以后增加订单可预约类型，暂时未设置
        # book_type = self.request.arguments['received_type'] if 'received_type' in self.request.arguments else ''
        book_type = ''

        shops_id = self.request.arguments['shop']

        book_info = {
            'desc': params['order_info'],
            'pic': params['cover'],
            'title': params['title']
        }

        self.db.execute('insert into wx_booking_setting(sp_id, shops, info, type, deleted, op_time) '
                        'values(%s, %s, %s, %s, 0, NOW())',
                        self.current_user.supplier_id, ','.join(shops_id), json_dumps(book_info), ','.join(book_type))

        self.redirect(self.reverse_url('wx.book'))


class Edit(BaseHandler):
    @require()
    def get(self):
        book_id = self.get_argument('book_id')

        book = self.db.get('select * from wx_booking_setting where id = %s and sp_id = %s', book_id, self.current_user.supplier_id)
        book.info = json.loads(book.info)
        book.shops = book.shops.split(',')
        book.type = book.type.split(',')

        shops = self.db.query('select * from supplier_shop where deleted = 0 and supplier_id = %s',
                              self.current_user.supplier_id)
        params = {
            'shops': shops,
            'book': book,
            'img_url': img_url,
            'action': 'edit'
        }

        self.render('wx/book/book.html', **params)

    @require()
    def post(self):
        params = dict([(name, self.get_argument(name).encode('utf-8')) for name in self.request.arguments])

        # 以后增加订单可预约类型使用
        # book_type = self.request.arguments['received_type'] if 'received_type' in self.request.arguments else ''
        book_type = ''
        shops_id = self.request.arguments['shop']

        book_info = {
            'desc': params['order_info'],
            'pic': params['cover'],
            'title': params['title']
        }

        self.db.execute('update wx_booking_setting set shops = %s, info = %s, type = %s, op_time = NOW() '
                        'where id = %s and sp_id = %s', ','.join(shops_id), json_dumps(book_info), ','.join(book_type),
                        params['book_id'], self.current_user.supplier_id)

        self.redirect(self.reverse_url('wx.book'))


class Delete(BaseHandler):
    @require()
    def post(self):
        book_id = self.get_argument('book_id')
        self.db.execute('update wx_booking_setting set deleted = 1 where id = %s and sp_id = %s',
                        book_id, self.current_user.supplier_id)

        self.redirect(self.reverse_url('wx.book'))


class Detail(BaseHandler):
    @require()
    def get(self):
        book_id = self.get_argument('book_id')
        book = self.db.get('select info, shops from wx_booking_setting where id = %s', book_id)

        shops_id = book.shops.split(',')
        shops = self.db.query('select * from supplier_shop where supplier_id = %%s and id in (%s) ' %
                              ','.join(['%s'] * len(shops_id)), self.current_user.supplier_id, *shops_id)

        book = json.loads(book.info)

        self.render('wx/book/detail.html', book=book, img_url=img_url, shops=shops)