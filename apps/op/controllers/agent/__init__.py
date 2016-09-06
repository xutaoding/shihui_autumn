# -*- coding: utf-8 -*-

from .. import BaseHandler, require
from autumn.torn.paginator import Paginator
from voluptuous import Schema
from autumn.torn.form import Form
import random
import string
import hashlib

agent = Schema({
    'name': str,
    'short_name': str,
    'mobile': str,
    'sales_id': str,
    'contact': str,
    'type': str,
    'bank_account': str,
    'bank_head': str,
    'bank_branch': str,
    'bank_holder': str,
    'bank_city': str,
    'username': str,
    'password': str,
    'action': str
})


class List(BaseHandler):
    @require()
    def get(self):
        sql = 'select a.*, o.name sale from agent a join operator o on a.sales_id = o.id where a.deleted = 0 ' \
              'order by created_at desc '

        page = Paginator(self, sql, [])

        self.render('agent/list.html', page=page)


class Detail(BaseHandler):
    @require('operator')
    def get(self, agent_id):
        info = self.db.get('select a.*, o.name sales_name from agent a join operator o on a.sales_id = o.id '
                           'where a.id = %s', agent_id)

        self.render('agent/detail.html', info=info)


class Add(BaseHandler):
    @require('operator')
    def get(self):
        form = Form(self.request.arguments, agent)
        form.action.value = 'add'

        sales = self.db.query('select id, name from operator where deleted = 0')

        self.render('agent/agent.html', form=form, sales=sales)

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, agent)
        form.action.value = 'add'

        if not form.validate():
            sales = self.db.query('select id, name from operator where deleted = 0')
            self.render('agent/agent.html', form=form, sales=sales)
            return

        user = self.db.get('select * from agent where deleted = 0 and username = %s', form.username.value)
        if user:
            form.username.error = '已存在该登录名，请更改'
            sales = self.db.query('select id, name from operator where deleted = 0')
            self.render('agent/agent.html', form=form, sales=sales)
            return

        field = ('name', 'short_name', 'sales_id', 'contact', 'type', 'mobile', 'username', 'password',
                 'bank_account', 'bank_head', 'bank_branch', 'bank_holder', 'bank_city')
        #生成密码的盐
        password_salt = ''.join(random.sample(string.ascii_letters + string.digits, 6))
        form.password.value = hashlib.new('md5', form.password.value + password_salt).hexdigest().lower()
        sql = 'insert into agent set %s' % ','.join([key + '= %s' for key in field])
        params = [form.arguments.get(item).value for item in field]

        sql += ', pwd_salt = %s, created_at = NOW(), created_by = %s'
        params.append(password_salt)
        params.append(self.current_user.name)

        uid = self.db.execute(sql, *params)

        #新建代理商的account_id
        self.db.execute('insert into account(uid, type, amount, created_at) values(%s, 3, 0, NOW())', uid)

        self.redirect(self.reverse_url('agent.list'))


class Edit(BaseHandler):
    @require('operator')
    def get(self, agent_id):
        info = self.db.get('select * from agent where deleted = 0 and id = %s', agent_id)
        form = Form(info, agent)
        form.action.value = 'edit'

        sales = self.db.query('select id, name from operator where deleted = 0')

        self.render('agent/agent.html', form=form, sales=sales, agent_id=agent_id)

    @require('operator')
    def post(self, agent_id):
        form = Form(self.request.arguments, agent)
        form.action.value = 'edit'

        if not form.validate():
            sales = self.db.query('select id, name from operator where deleted = 0')
            self.render('agent/agent.html', form=form, sales=sales)
            return

        field = ('name', 'short_name', 'sales_id', 'contact', 'type', 'mobile',
                 'bank_account', 'bank_head', 'bank_branch', 'bank_holder', 'bank_city')
        sql = 'update agent set %s' % ','.join([key + '= %s' for key in field]) + ' where id = %s'
        params = [form.arguments.get(item).value for item in field]
        params.append(agent_id)

        self.db.execute(sql, *params)

        self.redirect(self.reverse_url('agent.list'))


class Delete(BaseHandler):
    @require('operator')
    def post(self):
        agent_id = self.get_argument('agent_id')
        self.db.execute('update agent set deleted = 1 where id = %s', agent_id)

        self.redirect(self.reverse_url('agent.list'))
