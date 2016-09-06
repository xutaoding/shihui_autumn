# -*- coding: utf-8 -*-
import tornado.web
import functools
from datetime import datetime
from tornado.httputil import url_concat
from tornado.web import urlparse, urlencode
from tornado.options import options


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        uid = self.get_secure_cookie('_opu')
        if uid and uid.isdigit():
            return self.db.get('select * from operator where id=%s and deleted=0', uid)

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
        kwargs['default'] = lambda v, d='': v if v else d
        kwargs['options'] = options
        super(BaseHandler, self).render(template, **kwargs)


class PageNotFoundHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_status(404)
        self.render('404.html')

    def post(self):
        self.get()


def require(*required_roles):
    def wwrapper(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            """ @type self BaseHandler """
            #  如果没有登录，强制登录
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
                raise tornado.web.HTTPError(403)
            #  如果1小时内不活跃，强制退出
            if (datetime.now() - self.current_user.last_active).total_seconds() >= 60*60:
                self.redirect(url_concat(self.reverse_url('logout'), {'next': self.request.uri}))
                return
            self.db.execute('update operator set last_active=NOW() where id=%s', self.current_user.id)
            #  检查权限
            if required_roles:
                roles = self.current_user.roles.split(',')
                passed = False
                if required_roles == ('developer_mgr',):
                    #  如果标明只有开发主管可以访问，那么真的你需要 developer_mgr 这个角色才能访问
                    if 'developer_mgr' in roles:
                        passed = True
                else:
                    for role in roles:
                        if role == 'developer' or role in required_roles:
                            passed = True
                            break
                if not passed:
                    self.render('403.html')
                    return
            return method(self, *args, **kwargs)
        return wrapper
    return wwrapper