# -*- coding: utf-8 -*-

from .. import BaseHandler
from tornado.web import authenticated
from datetime import datetime
from autumn.torn.paginator import Paginator


class Sign(BaseHandler):
    @authenticated
    def get(self):
        sql = 'select * from wx_points where mem_id = %s '
        page = Paginator(self, sql, [self.current_user.id], page_size=10)
        now = datetime.now().replace(hour=0, minute=0, second=0)

        sum = 0
        sign = False
        points = self.db.query('select * from wx_points where mem_id = %s', self.current_user.id)
        for point in points:
            if point.expire_type == '1' or (point.expire_type == '0' and point.expire_at >= now):
                sum += point.num
            if not sign and point.created_at >= now:
                sign = True
        params = {
            'points': page.rows,
            'sum': sum,
            'current_user': self.current_user,
            'sign': sign,
            'links': page.boot_links()
        }
        self.render('member/sign.html', **params)

    @authenticated
    def post(self):
        points = self.db.query('select * from wx_points where mem_id = %s', self.current_user.id)
        now = datetime.now().replace(hour=0, minute=0, second=0)

        sign = False
        for point in points:
            if not sign and point.created_at >= now:
                sign = True

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        if not sign:
            # 每次签到积一分，且是无限期的
            self.db.execute('insert into wx_points(num, mem_id, type, expire_type, expire_at, created_at) '
                            'values(%s, %s, %s, %s, %s, NOW()) ', 1, self.current_user.id, 1, 1, now)
            sum = self.db.get('select sum(num) account from wx_points where mem_id = %s and '
                              '(expire_type = 1 or (expire_type = 0 and expire_at > %s))',
                              self.current_user.id, now)

            self.db.execute('update member set points = %s where id = %s', sum.account, self.current_user.id)

            self.write({'ok': True})
        else:
            self.write({'ok': False})