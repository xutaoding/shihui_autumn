#-*- coding: utf-8 -*-

from .. import BaseHandler, require
from autumn.torn.form import Form
from autumn.utils.dt import timedelta
from datetime import datetime
from autumn.torn.paginator import Paginator
from voluptuous import Schema
from voluptuous import Any
from autumn import const

find_list = Schema({
    'goods_name': str,
    'status': Any('', 'RETURNED', 'RETURNING'),
}, extra=True)


class ReturnManage(BaseHandler):
    @require('manager')
    def get(self):
        form = Form(self.request.arguments, find_list)
        sql = """select i.* from item i,goods g where g.id=i.goods_id and g.type='R'
        and i.status in (%s,%s) and i.sp_id= %s """
        params = [const.status.REFUND, const.status.RETURNING, self.current_user.supplier_id]

        if form.goods_name.value:
            sql += 'and i.goods_name like %s'
            params.append('%' + form.goods_name.value + '%')
        if form.status.value:
            sql += 'and i.status = %s '
            params.append(form.status.value)

        sql += 'order by i.id desc'
        page = Paginator(self, sql, params)
        self.render('real/return.html', form=form, page=page)