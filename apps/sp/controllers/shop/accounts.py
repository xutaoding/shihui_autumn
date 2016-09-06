# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from tornado.web import authenticated
from voluptuous import Schema
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator
import random
import string
import hashlib


add_edit_list = Schema({
    'supplier': str,
    'login_name': str,
    'password': str,
    'name': str,
    'supplier_shop': str,
    'action': str,
}, extra=True)


class Show(BaseHandler):
    @require()
    def get(self):
        # 独立结算门店只能管理该门店账户
        if self.current_user.shop_id != 0 and self.current_user.separate_account == '1':
            shop_ids = [str(self.current_user.shop_id)]
        else:
            shops = self.db.query('select id from supplier_shop where supplier_id=%s and deleted=0',
                                  self.current_user.supplier_id)
            shop_ids = [str(shop.id) for shop in shops] + ['0']

        sql = 'select su.* ,ss.name shop_name from supplier_user su left join supplier_shop ss on su.shop_id =ss.id ' \
              'where su.deleted = 0 and su.supplier_id=%s and su.shop_id in ' \
              '(' + ','.join(['%s']*len(shop_ids)) + ') order by su.id desc'

        params = [self.current_user.supplier_id] + shop_ids
        page = Paginator(self, sql, params)

        self.render('shop/accounts_show.html', page=page)


class Add(BaseHandler):
    @require('manager')
    def get(self):
        form = Form(self.request.arguments, add_edit_list)
        form.action.value = 'add'

        sid = self.current_user.supplier_id

        # 独立结算门店只能添加该门店下的账户
        if self.current_user.shop_id != 0 and self.current_user.separate_account == '1':
            shop_list = self.db.query('select id, name from supplier_shop where id=%s and deleted = 0',
                                      self.current_user.shop_id)
        else:
            shop_list = self.db.query('select id, name from supplier_shop where supplier_id = %s and deleted = 0', sid)

        self.render('shop/accounts.html', form=form, shop_list=shop_list, role='clerk', user=self.current_user)

    @authenticated
    @require('manager')
    def post(self):
        form = Form(self.request.arguments, add_edit_list)
        form.action.value = 'add'
        sid = self.current_user.supplier_id

        shop_list = self.db.query('select id, name from supplier_shop where supplier_id = %s', sid)
        supplier = self.db.get('select id supplier_id,short_name,separate_account from supplier where id = %s', sid)
        form.supplier.value = supplier.short_name
        if not form.validate():
            self.render('shop/accounts.html', form=form, shop_list=shop_list, role='clerk', user=self.current_user)
            return

        #判断用户名和工号是否存在，同一商户的操作员登录名不能相同，如存在则返回
        is_login_name_exist = self.db.query('select * from supplier_user where login_name = %s and supplier_id = %s',
                                            form.login_name.value, sid)
        role = self.get_argument('role')
        if is_login_name_exist:
            form.login_name.error = u'用户名已存在，请重新输入'
            self.render('shop/accounts.html', form=form, shop_list=shop_list, role=role, user=self.current_user)
            return

        shop_id = self.get_argument('shop_id')
        #生成密码的盐
        password_salt = ''.join(random.sample(string.ascii_letters + string.digits, 6))
        en_password = hashlib.new('md5', form.password.value + password_salt).hexdigest().lower()
        max_message_id = self.db.get('select id from notification order by id desc limit 1').id
        self.db.execute('insert into supplier_user(login_name, password, supplier_id, pwd_salt, name, '
                        'last_login, created_at, roles, shop_id, max_message_id) '
                        'values(%s, %s, %s, %s, %s, NOW(),NOW(), %s, %s, %s)',
                        form.login_name.value, en_password, sid, password_salt, form.name.value,
                        role, shop_id, max_message_id)

        self.redirect(self.reverse_url('accounts.show'))


class Edit(BaseHandler):
    @require('manager')
    def get(self, user_id):
        user = self.db.get('select su.*,s.separate_account from supplier_user su, supplier s '
                           'where su.supplier_id=s.id and su.id = %s', user_id)
        form = Form(user, add_edit_list)
        form.action.value = 'edit'
        #取出商户所有门店
        shop_list = self.db.query('select id, name from supplier_shop where supplier_id = %s and deleted = 0',
                                  user.supplier_id)
        role = self.db.get('select roles from supplier_user where id = %s', user.id)['roles']

        self.render('shop/accounts.html', form=form, shop_list=shop_list, user=user, role=role)

    @require('manager')
    def post(self, user_id):
        form = Form(self.request.arguments, add_edit_list)
        user = self.db.get('select su.*,s.separate_account from supplier_user su, supplier s '
                           'where su.supplier_id=s.id and su.id = %s', user_id)
        form.login_name.value = user.login_name
        form.action.value = 'edit'
        #取出商户所有门店
        shop_list = self.db.query('select id, name from supplier_shop where supplier_id = %s and deleted = 0',
                                  user.supplier_id)
        role = self.get_argument('role')

        if not form.validate():
            self.render('supplier/user.html', form=form, shop_list=shop_list, user=user, role=role)
            return
        #取出该管理员的角色

        #更新其余信息，不判断是否改变
        shop_id = self.get_argument('shop_id')
        self.db.execute('update supplier_user set name = %s, shop_id = %s, roles = %s where id = %s',
                        form.name.value, shop_id, role, user_id)

        self.redirect(self.reverse_url('accounts.show'))


class Delete(BaseHandler):
    @require('manager')
    def post(self):
        user_id = self.get_argument('user_id')
        self.db.execute('update supplier_user set deleted = 1 where id = %s', user_id)

        self.redirect(self.reverse_url('accounts.show'))
