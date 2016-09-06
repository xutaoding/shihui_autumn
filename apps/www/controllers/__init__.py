# -*- coding: utf-8 -*-
import tornado.web
from tornado.httputil import url_concat


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        """ :rtype: torndb.Connection """
        return self.application.db

    def render(self, template, **kwargs):
        kwargs['current_user'] = self.get_current_user()
        kwargs['url_concat'] = url_concat
        kwargs['default'] = lambda v, d: v if v else d
        super(BaseHandler, self).render(template, **kwargs)
