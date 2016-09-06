# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from autumn.torn.paginator import Paginator
from autumn.torn.form import Form
from voluptuous import Schema
import random
import string
import hashlib

search_list = Schema({
    'supplier_id': str,
    'supplier_short_name': str,
    'supplier_shop': str,
}, extra=True)

add_list = Schema({
    'id': str,
    'supplier_id': str,
    'login_name': str,
    'name': str,
    'shop_id': str,
    'roles': str,
    'action': str,
}, extra=True)


class List(BaseHandler):
    @require()
    def get(self, supplier_id):
        supplier = self.db.get('select * from supplier where id=%s', supplier_id)

        form = Form(self.request.arguments, search_list)
        sql = """select su.* ,ss.name shop_name from supplier_user su left join supplier_shop ss
        on su.shop_id =ss.id where su.deleted = 0 and su.supplier_id=%s order by su.id desc"""
        params = [supplier_id]
        page = Paginator(self, sql, params)

        self.render('supplier/user/list.html', page=page, form=form, supplier=supplier)


class Add(BaseHandler):
    @require('operator')
    def get(self):
        form = Form(self.request.arguments, add_list)
        form.action.value = 'add'

        sid = self.get_argument('supplier_id')
        supplier = self.db.get('select * from supplier where id = %s', sid)

        shop_list = self.db.query('select id, name from supplier_shop where deleted =0 and supplier_id = %s', sid)

        self.render('supplier/user/user.html', form=form, shop_list=shop_list, supplier=supplier)

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, add_list)
        form.action.value = 'add'
        sid = self.get_argument('supplier_id')

        shop_list = self.db.query('select id, name from supplier_shop where deleted =0 and supplier_id = %s', sid)
        supplier = self.db.get('select * from supplier where id = %s', sid)
        if not form.validate():
            return self.render('supplier/user/user.html', form=form, shop_list=shop_list,  supplier=supplier)

        #判断用户名和工号是否存在，同一商户的操作员登录名不能相同，如存在则返回
        if self.db.query('select * from supplier_user where login_name = %s and supplier_id = %s',
                         form.login_name.value, sid):
            form.login_name.error = u'用户名已存在，请重新输入'
            return self.render('supplier/user/user.html', form=form, shop_list=shop_list, supplier=supplier)

        max_message_id = self.db.get('select id from notification order by id desc limit 1').id
        #生成密码的盐
        password_salt = ''.join(random.sample(string.ascii_letters + string.digits, 6))
        en_password = hashlib.new('md5', '123456' + password_salt).hexdigest().lower()
        fields = {
            'login_name': form.login_name.value.strip(),
            'password': en_password,
            'pwd_salt': password_salt,
            'supplier_id': sid,
            'name': form.name.value.strip(),
            'roles': form.roles.value.strip(),
            'shop_id': form.shop_id.value,
            'max_message_id': max_message_id,
        }
        sql = 'insert into supplier_user set last_login=NOW(), created_at=NOW(), ' + '=%s,'.join(fields.keys()) + '=%s'
        self.db.execute(sql, *fields.values())

        self.redirect(self.reverse_url('supplier.user', self.get_argument('supplier_id')))


class Edit(BaseHandler):
    @require('operator')
    def get(self):
        user = self.db.get('select * from supplier_user where id=%s', self.get_argument('id'))
        form = Form(user, add_list)
        form.action.value = 'edit'
        shop_list = self.db.query('select id, name from supplier_shop where supplier_id = %s', user.supplier_id)
        supplier = self.db.get('select * from supplier where id = %s', user.supplier_id)
        self.render('supplier/user/user.html', form=form, shop_list=shop_list, supplier=supplier)

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, add_list)
        uid = self.get_argument('id')
        form.action.value = 'edit'
        #取出商户所有门店
        user = self.db.get('select * from supplier_user where id=%s', uid)
        shop_list = self.db.query('select id, name from supplier_shop where supplier_id = %s', user.supplier_id)
        supplier = self.db.get('select * from supplier where id = %s', user.supplier_id)
        if not form.validate():
            return self.render('supplier/user/user.html', form=form, shop_list=shop_list, supplier=supplier)

        #更新其余信息，不判断是否改变
        self.db.execute('update supplier_user set name = %s ,roles = %s, shop_id=%s where id = %s',
                        form.name.value, form.roles.value, form.shop_id.value, uid)

        self.redirect(self.reverse_url('supplier.user', user.supplier_id))


class Delete(BaseHandler):
    @require('operator')
    def post(self):
        user = self.db.get('select * from supplier_user where id=%s', self.get_argument('id'))
        self.db.execute('update supplier_user set deleted = 1 where id = %s', self.get_argument('id'))
        self.redirect(self.reverse_url('supplier.user', user.supplier_id))


class ResetPwd(BaseHandler):
    @require('service', 'operator')
    def post(self):
        uid = self.get_argument('id')
        user = self.db.get('select * from supplier_user where id=%s', uid)
        en_password = hashlib.new('md5', '123456' + user.pwd_salt).hexdigest()
        self.db.execute('update supplier_user set password=%s where id = %s', en_password, uid)
        self.redirect(self.reverse_url('supplier.user', user.supplier_id))
