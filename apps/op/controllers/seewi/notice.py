#-*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
import itertools


class Notice(BaseHandler):
    @require('operator')
    def get(self):
        self.render('seewi/notice.html')

    @require('operator')
    def post(self):
        title = self.get_argument('title', '')
        content = self.get_argument('content', '')
        type = self.get_argument('type', 0)
        is_all = self.get_argument('choice', '0')
        if is_all == '1':
            supplier = self.get_argument('supplier', '0').split(';')
            params = [i for item in zip([title] * len(supplier), [content] * len(supplier), type * len(supplier), supplier) for i in item]
            self.db.execute('insert into notification(title, content, created_at, type, url, uid, user_type) '
                            'values %s' % ','.join(['(%s, %s, NOW(), %s, "", %s, 0)'] * len(supplier)), *params)

        else:
            self.db.execute('insert into notification(title, content, created_at, type, url, uid, user_type) '
                            'values(%s, %s, NOW(), %s, "", 0, 0)', title, content, type)

        self.render('seewi/notice_result.html')