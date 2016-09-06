# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from voluptuous import Schema, Any
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator


class SkuList(BaseHandler):
    @require()
    def get(self):
        sql = 'select * from sku where deleted = 0 '

        name = self.get_argument('name', '')
        params = []
        if name:
            sql += 'and name like %s '
            params.append('%' + name + '%')

        sql += 'order by created_at desc'
        page = Paginator(self, sql, params)

        self.render('real/sku_list.html', page=page, name=name)


add_list = Schema({
    'name': str,
    'price': str,
    'action': Any('edit', 'add'),
}, extra=True)


class SkuAdd(BaseHandler):
    @require('storage')
    def get(self):
        form = Form(self.request.arguments, add_list)
        form.action.value = 'add'

        self.render('real/sku.html', form=form)

    @require('storage')
    def post(self):
        form = Form(self.request.arguments, add_list)
        form.action.value = 'add'
        if not form.validate():
            return self.render('real/sku.html', form=form)

        supplier = self.db.get('select id from supplier where name = "视惠" limit 1')
        self.db.execute('insert into sku(name, price, supplier_id, created_at) values(%s, %s, %s, NOW())',
                        form.name.value, form.price.value, supplier["id"])

        self.redirect(self.reverse_url('real.show_sku'))


class SkuEdit(BaseHandler):
    @require('storage')
    def get(self):
        sku = self.db.get('select name, price from sku where id = %s', self.get_argument('id'))
        form = Form(sku, add_list)
        form.action.value = 'edit'

        self.render('real/sku.html', form=form, id=self.get_argument('id'))

    @require('storage')
    def post(self):
        form = Form(self.request.arguments, add_list)
        form.action.value = 'edit'
        if not form.validate():
            return self.render('real/sku.html', form=form, id=self.get_argument('id'))

        self.db.execute('update sku set name = %s, price = %s where id = %s',
                        form.name.value, form.price.value, self.get_argument('id'))

        self.redirect(self.reverse_url('real.show_sku'))


class SkuDelete(BaseHandler):
    @require('storage')
    def post(self):
        id = self.get_argument('id')
        self.db.execute('update sku set deleted = 1 where id = %s', id)

        self.redirect(self.reverse_url('real.show_sku'))