# -*- coding: utf-8 -*-

from ... import BaseHandler
from ... import require
from autumn.torn.paginator import Paginator


class Show(BaseHandler):
    """消息管理"""
    @require()
    def get(self):
        user = self.current_user
        sql = 'select wm.*, m.wx_name, m.mobile, m.id mid from wx_msg wm, member m ' \
              'where wm.sent_from=m.id and sent_to=%s order by id desc'
        page = Paginator(self, sql, [user.supplier_id])

        self.render('wx/msg/show.html', page=page)
