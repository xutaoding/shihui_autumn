#-*- coding: utf-8 -*-

from . import BaseHandler
from voluptuous import Schema, Required
from autumn.torn.form import Form
import hashlib
from .. import require

password = Schema({
    Required('old_pw'): str,
    Required('pw'): str,
    Required('confirm_pw'): str
})


class Password(BaseHandler):
    @require()
    def get(self):
        form = Form(self.request.arguments, password)
        if self.current_user.password.lower() == hashlib.md5('123456' + self.current_user.pwd_salt).hexdigest():
            form.old_pw.error = u'密码强度太弱，请修改'

        self.render('auth/password.html', form=form)

    @require()
    def post(self):
        form = Form(self.request.arguments, password)
        if not form.validate():
            self.render('auth/password.html', form=form)
            return

        old_pw = hashlib.md5(form.old_pw.value.strip() + self.current_user.pwd_salt).hexdigest()
        if old_pw != self.current_user.password.lower():
            form.old_pw.error = u'输入的旧密码不正确，请重新输入'
            self.render('auth/password.html', form=form)
            return

        if form.pw.value.strip() != form.confirm_pw.value.strip():
            form.confirm_pw.error = u'新密码两次输入不一致，请确认'
            self.render('auth/password.html', form=form)
            return

        if form.pw.value.lower() == '123456':
            form.confirm_pw.error = u'新密码强度太弱，请修改'
            self.render('auth/password.html', form=form)
            return

        new_pw = hashlib.md5(form.pw.value.strip() + self.current_user.pwd_salt).hexdigest()
        self.db.execute('update supplier_user set password = %s where id = %s', new_pw, self.current_user.id)
        self.redirect(self.reverse_url('coupon.verify'))