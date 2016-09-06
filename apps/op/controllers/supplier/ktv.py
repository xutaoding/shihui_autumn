# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from voluptuous import Schema
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator

add_edit_list = Schema({
    'name': str,
    'duration': str,
    'supplier': str,
    'action': str,
    'id': str,
})


class Show(BaseHandler):
    @require()
    def get(self, supplier_id):
        sql = """select kp.*, s.short_name supplier_name from ktv_product kp left join supplier s
                 on kp.supplier_id = s.id where kp.deleted = 0 and s.id=%s"""
        params = [supplier_id]
        page = Paginator(self, sql, params)
        supplier = self.db.get('select * from supplier where id=%s', supplier_id)

        self.render('supplier/ktv_show.html', page=page, supplier=supplier)


class Add(BaseHandler):
    @require('developer')
    def get(self):
        form = Form(self.request.arguments, add_edit_list)
        form.action.value = 'add'
        supplier = self.db.get('select * from supplier where id=%s', self.get_argument('supplier_id'))

        self.render('supplier/ktv.html', form=form, supplier=supplier)

    @require('developer')
    def post(self):
        form = Form(self.request.arguments, add_edit_list)
        form.action.value = 'add'

        if not form.validate():
            return self.render('supplier/ktv.html', form=form)

        self.db.execute('insert into ktv_product(created_at, created_by, duration, name, supplier_id) '
                        'values(now(), %s, %s, %s, %s)', self.current_user.name, form.duration.value,
                        form.name.value, form.supplier.value)

        self.redirect(self.reverse_url('supplier.ktv', form.supplier.value))


class Edit(BaseHandler):
    @require('developer')
    def get(self, ktv_product_id):
        ktv_product = self.db.get('select * from ktv_product where id=%s', ktv_product_id)
        form = Form(ktv_product, add_edit_list)
        form.action.value = 'edit'
        supplier = self.db.get('select * from supplier where id=%s', ktv_product.supplier_id)

        self.render('supplier/ktv.html', form=form, supplier=supplier)

    @require('developer')
    def post(self, ktv_product_id):
        form = Form(self.request.arguments, add_edit_list)

        if not form.validate():
            return self.redirect(self.reverse_url('supplier.edit_ktv', ktv_product_id))

        self.db.execute('update ktv_product set name = %s, duration = %s, '
                        'where id = %s',
                        form.name.value, form.duration.value, self.current_user.name, ktv_product_id)
        ktv_product = self.db.get('select * from ktv_product where id=%s', ktv_product_id)

        self.redirect(self.reverse_url('supplier.ktv', ktv_product.supplier_id))


class Delete(BaseHandler):
    @require('developer')
    def post(self):
        ktv_product_id = self.get_argument('ktv_product_id')

        goods = self.db.get('select goods_id from ktv_product_goods where product_id = %s limit 1', ktv_product_id)
        if goods:
            self.db.execute('update goods_distributor_shop set deleted = 1 where goods_id = %s', goods.goods_id)

        self.db.execute('update ktv_product set deleted = 1 where id = %s', ktv_product_id)

        self.redirect(self.reverse_url('supplier.ktv'))
