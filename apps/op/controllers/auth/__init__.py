# -*- coding: utf-8 -*-
import json
from tornado import gen
from tornado.httpclient import AsyncHTTPClient
from tornado.httputil import url_concat

from autumn.torn.form import Form
from voluptuous import Schema, Required
from autumn.utils import json_hook
from ..import BaseHandler
import hashlib


schema = Schema({
    Required('username'): str,
    Required('password'): str,
    'next':     str,
})


class Login(BaseHandler):
    @gen.coroutine
    def get(self):
        form = Form(self.request.arguments, schema)

        http_client = AsyncHTTPClient()
        response = yield http_client.fetch("http://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1")
        bg_img_url = json.loads(response.body, object_hook=json_hook).images[0].url

        self.render('auth/login.html', form=form, bg_img_url=bg_img_url)

    @gen.coroutine
    def post(self):
        form = Form(self.request.arguments, schema)
        if not form.validate():
            http_client = AsyncHTTPClient()
            response = yield http_client.fetch("http://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1")
            bg_img_url = json.loads(response.body, object_hook=json_hook).images[0].url
            self.render('auth/login.html', form=form, bg_img_url=bg_img_url)
            return

        user = self.db.get('select * from operator where login_name=%s and deleted=0', form.username.value)
        if not user or user.password.lower() != hashlib.md5(form.password.value + user.pwd_salt).hexdigest():
            http_client = AsyncHTTPClient()
            response = yield http_client.fetch("http://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1")
            bg_img_url = json.loads(response.body, object_hook=json_hook).images[0].url
            form.username.error = u'用户名密码不匹配'
            self.render('auth/login.html', form=form, bg_img_url=bg_img_url)
            return

        self.set_secure_cookie('_opu', unicode(user.id))
        self.db.execute('update operator set last_active=NOW() where id=%s', user.id)
        if form.next.value and form.next.value.startswith('/'):
            self.redirect(form.next.value)
            return
        self.redirect(self.reverse_url('welcome'))


class Logout(BaseHandler):
    def get(self):
        self.clear_cookie('_opu')
        next_url = self.get_argument('next', '')
        self.redirect(url_concat(self.reverse_url('login'), {'next': next_url}))
