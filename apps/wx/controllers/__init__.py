# -*- coding: utf-8 -*-
import tornado.web
from tornado.httputil import url_concat


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        wx_id = self.get_argument('wx_id', '')
        subhost = self.request.host.split('.')[0].split(':')[0]

        if wx_id and subhost:
            user = self.db.get('select m.*,s.name sp_name from member m, supplier s '
                               'where m.sp_id=s.id and m.wx_id=%s and s.id=%s', wx_id, subhost)
            return user
        return None

    @property
    def db(self):
        """ :rtype: torndb.Connection """
        return self.application.db

    @property
    def redis(self):
        """ :rtype: redis.StrictRedis """
        return self.application.redis

    def render(self, template, **kwargs):
        kwargs['url_concat'] = url_concat
        kwargs['default'] = lambda v, d: v if v else d
        super(BaseHandler, self).render(template, **kwargs)


class PageNotFoundHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_status(404)
        self.render('404.html')

    def post(self):
        self.get()


class Unauthorized(tornado.web.RequestHandler):
    def get(self):
        self.set_status(403)
        self.write('unauthorized')
