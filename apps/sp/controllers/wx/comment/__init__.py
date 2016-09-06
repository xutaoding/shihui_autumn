# -*- coding: utf-8 -*-

from ... import BaseHandler
from ... import require
from autumn.torn.paginator import Paginator


class List(BaseHandler):
    @require()
    def get(self):
        sql = 'select wc.*, m.name, m.mobile from wx_comment wc, member m where wc.mem_id = m.id and m.sp_id = %s '
        params = [self.current_user.supplier_id]
        comments = Paginator(self, sql, params)

        self.render('wx/comment/list.html', comments=comments)