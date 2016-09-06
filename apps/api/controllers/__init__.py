# -*- coding: utf-8 -*-
import tornado.web
from tornado.httputil import url_concat


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        """ :rtype: torndb.Connection """
        return self.application.db

    @property
    def redis(self):
        """ :rtype: redis.StrictRedis """
        return self.application.redis
