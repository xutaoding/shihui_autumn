# -*- coding: utf-8 -*-

import tornado.httputil
from tornado.httputil import url_concat
import re
from voluptuous import Schema, Length, Any

from autumn.torn.form import Form
from .. import BaseHandler
from .. import require
from autumn.torn.paginator import Paginator

shop_schema = Schema({
    'name':             Length(min=1),
    'taobao_nick':      str,
    'money_manager':    Length(min=1),
    'url':              str,
    'action':           Any('edit', 'add'),
    'id':               str,
    'distributor_id':   str,
}, extra=True)


class Add(BaseHandler):
    @require('operator')
    def get(self):
        form = Form(self.request.arguments, shop_schema)
        form.money_manager.value = 'PLATFORM'
        form.action.value = 'add'
        form.distributor_id.value = self.get_argument('distributor-id')

        self.render('distributor/shop.html', form=form, error='')

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, shop_schema)

        if not form.validate():
            return self.render('distributor/shop.html', form=form, error='error')

        if form.url.value:
            form.url.value = form.url.value.lower()
            if not re.match(r'https?', form.url.value):
                form.url.value = 'http://' + form.url.value

        distributor_id = self.get_argument('distributor-id')
        distributor = self.db.get('select name from distributor where id = %s', distributor_id)

        # 新建分销商铺
        shop_id = self.db.execute_lastrowid(
            'insert into distributor_shop (distributor_id,name,taobao_nick,money_manager,'
            'url,distributor_name,created_at,created_by) values (%s,%s,%s,%s,%s,%s,now(),%s)',
            distributor_id, form.name.value.strip(), form.taobao_nick.value.strip(),
            form.money_manager.value, form.url.value, distributor.name, self.current_user.name)

        self.redirect(url_concat(self.reverse_url('distributor.show_shop_list'), {'distributor_id': distributor_id}))


class Edit(BaseHandler):
    @require('operator')
    def get(self):
        shop_id = self.get_argument('id')
        shop = self.db.get('select name,taobao_nick,money_manager from distributor_shop where id = %s', shop_id)
        form = Form(shop, shop_schema)
        form.action.value = 'edit'
        form.id.value = shop_id

        self.render('distributor/shop.html', form=form, error='')

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, shop_schema)

        if not form.validate():
            return self.render('distributor/shop.html', form=form, error='error')

        if form.url.value:
            form.url.value = form.url.value.lower()
            if not re.match(r'https?', form.url.value):
                form.url.value = 'http://' + form.url.value

        shop_id = self.get_argument('id')
        distributor_shop = self.db.get('select * from distributor_shop where deleted =0 and id = %s', shop_id)
        distributor_id = distributor_shop.distributor_id

        self.db.execute(
            'update distributor_shop set name = %s,taobao_nick= %s,money_manager = %s,url = %s '
            'where id = %s',
            form.name.value.strip(), form.taobao_nick.value.strip(),
            form.money_manager.value, form.url.value, shop_id)

        self.redirect(url_concat(self.reverse_url('distributor.show_shop_list'), {'distributor_id': distributor_id, 'id': shop_id}))


class List(BaseHandler):
    @require()
    def get(self):
        sql = """select s.*  from distributor_shop s where deleted = 0 """

        distributor_id = self.get_argument('distributor-id', '')
        shop_id = self.get_argument('id', '')

        form = Form(self.request.arguments, shop_schema)
        params = []

        if form.name.value:
            sql += 'and s.distributor_name like %s '
            params.append('%' + form.name.value + '%')

        if distributor_id:
            sql += ' and s.distributor_id = %s '
            params.append(distributor_id)

        if shop_id:
            sql += 'and s.id = %s '
            params.append(shop_id)

        sql += 'order by s.id desc'
        page = Paginator(self, sql, params)
        self.render('distributor/shop_list.html', page=page, form=form)
