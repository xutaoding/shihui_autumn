# -*- coding: utf-8 -*-
import functools
import urlparse
import tornado.web
from tornado.httputil import url_concat
from tornado.web import urlencode, HTTPError


class BaseHandler(tornado.web.RequestHandler):
    @property
    def current_user(self):
        uid = self.get_secure_cookie('_ag')
        if uid and uid.isdigit():
            user = self.db.get('select * from agent where id=%s and deleted = 0', uid)
            return user

    @property
    def db(self):
        """ :rtype: torndb.Connection """
        return self.application.db

    def render(self, template, **kwargs):
        kwargs['url_concat'] = url_concat
        kwargs['default'] = lambda v, d='': v if v else d
        super(BaseHandler, self).render(template, **kwargs)


class PageNotFoundHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_status(404)
        self.render('404.html')

    def post(self):
        self.get()


def authenticated(method):
    """Decorate methods with this to require that the user be logged in.

    If the user is not logged in, they will be redirected to the configured
    `login url <RequestHandler.get_login_url>`.
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.current_user:
            if self.request.method in ("GET", "HEAD"):
                url = self.get_login_url()
                if "?" not in url:
                    if urlparse.urlsplit(url).scheme:
                        # if login url is absolute, make next absolute too
                        next_url = self.request.full_url()
                    else:
                        next_url = self.request.uri
                    url += "?" + urlencode(dict(next=next_url))
                self.redirect(url)
                return
            raise HTTPError(403)
        return method(self, *args, **kwargs)
    return wrapper
