# -*- coding: utf-8 -*-

import tornado.web
from tornado.httputil import url_concat


class BackModule(tornado.web.UIModule):
    def render(self, wx_id):
        return self.render_string('ui_modules/member.html', wx_id=wx_id, url_concat=url_concat)