# -*- coding: utf-8 -*-
from tornado.web import url, RequestHandler, UIModule
from autumn.utils import send_email


class Page(RequestHandler):
    def get(self, page):
        if not page:
            page = 'index'
        self.render('%s.html' % page)


class Message(RequestHandler):
    def post(self):
        name = self.get_argument('name', '').encode('utf-8')
        contact = self.get_argument('contact', '').encode('utf-8')
        content = self.get_argument('content', '').encode('utf-8')
        if name and contact and content:
            send_email(redis=self.application.redis, subject='%s 寻求合作 (来自 视惠官网)' % name,
                       to_list='bd@seewi.com.cn',
                       html='<p>联系方式： %s</p><p>留言： %s</p>' % (contact, content))
        self.write('{}')


class MenuModule(UIModule):
    def render(self, menu_key):
        return self.render_string('menu.html', menu_key=menu_key)

handlers = [
    url(r'/message',    Message,    name='message'),
    url(r'/(.*)',       Page,       name='page'),
]
