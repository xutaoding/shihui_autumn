# -*- coding: utf-8 -*-
from .. import BaseHandler
from .. import require
import hashlib
import random
import string
from voluptuous import Schema, Length, All
from autumn.torn.form import Form, Decode
from autumn.torn.paginator import Paginator


list_schema = Schema({
    'login_name': str,
    'user_name': str,
}, extra=True)

add_schema = Schema({
    'login_name': str,
    'name': str,
    'id': str,
    'email': str,
    'password': str,
    'action': str,
    'roles': str,
}, extra=True)


class List(BaseHandler):
    @require('developer')
    def get(self):
        form = Form(self.request.arguments, list_schema)
        sql = """select o.* from operator o where o.deleted =0 """
        params = []
        if form.login_name.value:
            sql += "and o.login_name = %s"
            params.append(form.login_name.value)

        if form.user_name.value:
            sql += "and o.name like %s"
            params.append("%" + form.user_name.value + "%")
        sql += "order by o.id desc"
        page = Paginator(self, sql, params)
        self.render("operator/list.html", form=form, page=page)


class Add(BaseHandler):
    @require('developer')
    def get(self):
        form = Form(self.request.arguments, add_schema)
        form.action.value = 'add'
        self.render("operator/user.html", form=form)

    @require('developer')
    def post(self):
        form = Form(self.request.arguments, add_schema)
        role_ids = self.get_arguments('roles')
        if not role_ids:
            return self.render('operator/user.html', form=form)
        roles = ','.join(role_ids)

        if not form.validate():
            return self.render('operator/user.html', form=form)

        #判断用户名和工号是否存在,如存在则返回
        is_login_name_exist = self.db.query('select * from operator where login_name = %s ', form.login_name.value)
        if is_login_name_exist:
            form.login_name.error = u'用户名已存在，请重新输入'
            return self.render('operator/user.html', form=form)

        #生成密码的盐
        password_salt = ''.join(random.sample(string.ascii_letters + string.digits, 6))
        en_password = hashlib.new('md5', form.password.value + password_salt).hexdigest().lower()
        self.db.execute('insert into operator(login_name, password, pwd_salt, name, email, roles,'
                        'deleted, created_at, last_active) values(%s, %s, %s, %s, %s, %s, 0, NOW(), NOW())',
                        form.login_name.value.strip(), en_password, password_salt, form.name.value,
                        form.email.value.strip(), roles)

        self.redirect("/operator")


class Edit(BaseHandler):
    @require('developer')
    def get(self):
        operator = self.db.get('select id,name,email,login_name,roles from operator '
                               'where deleted = 0 and id = %s', self.get_argument('id'))
        form = Form(operator, add_schema)
        form.action.value = 'edit'
        self.render("operator/user.html", form=form)

    @require('developer')
    def post(self):
        form = Form(self.request.arguments, add_schema)
        uid = self.get_argument('id')
        role_ids = self.get_arguments('roles')
        if not role_ids:
            return self.render('operator/user.html', form=form)
        roles = ','.join(role_ids)

        if not form.validate():
            return self.render('operator/user.html', form=form)

        #更新操作员信息
        self.db.execute('update operator set name=%s,email=%s,roles=%s where id =%s',
                        form.name.value, form.email.value, roles, uid)
        password = form.password.value.lower()
        if password and password != '******':
            #生成密码的盐
            password_salt = ''.join(random.sample(string.ascii_letters + string.digits, 6))
            en_password = hashlib.new('md5', password + password_salt).hexdigest()
            self.db.execute('update operator set password = %s,pwd_salt=%s where id = %s',
                            en_password, password_salt, uid)

        self.redirect("/operator")


class Delete(BaseHandler):
    @require('developer')
    def post(self):
        self.db.execute('update operator set deleted =1 where id = %s', self.get_argument("id"))
        self.redirect("/operator")