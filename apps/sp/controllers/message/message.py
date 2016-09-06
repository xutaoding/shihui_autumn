#-*- coding: utf-8 -*-

from .. import BaseHandler, require
from autumn.utils import json_dumps
from datetime import datetime, timedelta
from tornado.template import Template


class Message(BaseHandler):
    @require()
    def get(self):
        unread_message = self.db.query('select * from notification where user_type = 0 and (uid = 0 or uid = %s) and '
                                       'id > %s order by type desc, created_at desc',
                                       self.current_user.supplier_id, self.current_user.max_message_id)

        today = datetime.now().replace(hour=0, minute=0, second=0)
        week_ago = today - timedelta(days=7)

        sql = """select * from notification where user_type = 0 and (uid = 0 or uid = %%s) and id <= %%s
                %s order by created_at desc"""
        # 今天的信息
        today_message = self.db.query(sql % ' and created_at >= %s ', self.current_user.supplier_id,
                                      self.current_user.max_message_id, today)

        # 一周内的消息
        week_message = self.db.query(sql % ' and created_at < %s and created_at > %s', self.current_user.supplier_id,
                                     self.current_user.max_message_id, today, week_ago)

        max_id = max([v for i in unread_message for k, v in i.iteritems() if k == 'id'] if unread_message else [0])
        if max_id:
            self.db.execute('update supplier_user set max_message_id = %s where id = %s', max_id, self.current_user.id)

        params = {
            'unread_message': unread_message,
            'today_message': today_message,
            'week_message': week_message
        }
        self.render('message/message.html', **params)


class UpdateID(BaseHandler):
    @require()
    def post(self):
        mid = self.get_argument('mid', 0)
        self.db.execute('update supplier_user set max_message_id = %s where id = %s', mid, self.current_user.id)


class Unread(BaseHandler):
    @require()
    def get(self):
        message_count = self.db.get('select count(1) c from notification where user_type = 0 and (uid = 0 or uid = %s) '
                                    'and id > %s', self.current_user.supplier_id,
                                    self.current_user.max_message_id)

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps({'count': message_count.c}))


class Early(BaseHandler):
    @require()
    def get(self):
        sql = """select * from notification where user_type = 0 and (uid = 0 or uid = %s) and id <= %s
                 and created_at < %s order by created_at desc"""

        today = datetime.now().replace(hour=0, minute=0, second=0)
        week_ago = today - timedelta(days=7)

        early = self.db.query(sql, self.current_user.supplier_id, self.current_user.max_message_id, week_ago)

        html = ''
        obj = """<div class="block fn-clear {{ important }}">
                    <div class="title fn-clear" >
                        <h3 class="fn-left">{{ title }}</h3>
                        <p class="fn-right">{{ created_at }}</p>
                    </div>
                    <div class="content">
                        {{ content }}
                    </div>
                    <div class="fn-right">
                        <a href="{{ url }}">
                        {{ look }}
                        </a>
                    </div>
                </div>"""
        for item in early:
            html += Template(obj).generate(important='important' if item.type else '', title=item.title, created_at=item.created_at, content=item.content, url=item.url if item.url else '', look='点击查看' if item.url else '')

        self.write(html)