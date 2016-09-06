# -*- coding: utf-8 -*-
from tornado.httputil import url_concat
import tornado.web
from .. import BaseHandler
from datetime import datetime
from autumn.torn.paginator import Paginator


class Comment(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        sql = """select wc.star, wc.content, wc.created_at, m.id
                 from wx_comment wc, member m
                 where wc.mem_id = m.id and m.sp_id = %s order by wc.created_at desc """

        comments = self.db.query(sql, self.current_user.sp_id)

        exist = False
        today = datetime.today().replace(hour=0, minute=0, second=0)
        for comment in comments:
            if comment.id == self.current_user.id:
                if comment.created_at > today:
                    exist = True
                break
        # todo 潜在的风险，倒序很慢
        page = Paginator(self, sql, [self.current_user.sp_id], page_size=9)

        self.render('comment/comment.html', page=page, exist=exist)

    @tornado.web.authenticated
    def post(self):
        star = self.get_argument('mount', 0)
        content = self.get_argument('content', '')

        self.db.execute('insert into wx_comment(mem_id, content, star, created_at) values(%s, %s, %s, NOW())',
                        self.current_user.id, content, star)

        self.redirect(url_concat(self.reverse_url('comment'), {'wx_id': self.current_user.wx_id}))
