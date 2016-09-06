# -*- coding: utf-8 -*-
import tornado.web
import functools
from tornado.httputil import url_concat
from tornado.web import urlparse, urlencode
from autumn.utils import PropDict
import hashlib

class BaseHandler(tornado.web.RequestHandler):
    @property
    def current_user(self):
        uid = self.get_secure_cookie('_spu')
        if uid and uid.isdigit():
            user = self.db.get('select su.*, s.short_name supplier_short_name, s.properties sp_properties, '
                               's.account_id sp_account_id, s.separate_account '
                               'from supplier_user su,supplier s where su.supplier_id = s.id and su.id = %s '
                               'and su.deleted = 0', uid)
            sp_props = self.db.query('select * from supplier_property where sp_id=%s', user.supplier_id)
            user['sp_props'] = PropDict([(sp_prop.name, sp_prop.value) for sp_prop in sp_props])
            return user

    @property
    def db(self):
        """ :rtype: torndb.Connection """
        return self.application.db

    @property
    def redis(self):
        """ :rtype: redis.StrictRedis """
        return self.application.redis

    def render(self, template, **kwargs):
        kwargs['current_user'] = self.current_user
        kwargs['url_concat'] = url_concat
        kwargs['default'] = lambda v, d='': v if v else d
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
            #  如果是已登录用户，但账号被禁止，强制退出
            if self.current_user.deleted == '1':
                self.redirect(self.reverse_url('logout'))
                return
            #  检查微信是否绑定,未绑定跳转到设置页面
            if self.request.uri.startswith('/wx'):
                if 'sp_props' in self.current_user:
                    if not 'wx_type' in self.current_user.sp_props:
                        return self.redirect(self.reverse_url('wx.setting'))
            #  检查权限
            if required_roles:
                roles = self.current_user.roles.split(',')
                passed = False
                for role in roles:
                    if role == 'manager' or role in required_roles:
                        passed = True
                        break
                if not passed:
                    self.render('403.html')
                    return

            # if self.current_user.password.lower() == hashlib.md5('123456' + self.current_user.pwd_salt).hexdigest():
            #     if self.request.uri not in ('/password', '/message/unread'):
            #         return self.redirect(self.reverse_url('password'))
            return method(self, *args, **kwargs)
        return wrapper
    return wwrapper


