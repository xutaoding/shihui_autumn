# -*- coding: utf-8 -*-

import tornado.httputil
from voluptuous import Schema
from autumn.torn.form import Form
from .. import BaseHandler
from .. import require

search_schema = Schema({
                       'endpoint': str,
                       'value': str,
                       }, required=True)


class Welcome(BaseHandler):
    @require()
    def get(self):
        """获得欢迎页面"""
        # 显示行政通知十条
        notice = self.db.query('select * from news where deleted = 0 and type = 1 order by created_at desc limit 10')
        self.render('welcome.html', notice=notice)


class QuickSearch(BaseHandler):
    @require()
    def post(self):
        form = Form(self.request.arguments, search_schema)
        if form.validate():
            endpoint, name = form.endpoint.value.split('|')
            return self.redirect(tornado.httputil.url_concat(self.reverse_url(endpoint), {name: form.value.value}))
        self.redirect(self.reverse_url('welcome'))
