# -*- coding: utf-8 -*-
from .. import BaseHandler, require
from datetime import datetime
from voluptuous import Schema
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator


list_schema = Schema(
    {
        'supplier': str,
        'supplier_name': str,
        'short_name': str,
    }, extra=True)


class DelayList(BaseHandler):
    @require()
    def get(self):
        form = Form(self.request.arguments, list_schema)
        sql = """select id, sales_price, purchase_price, short_name, expire_at from goods
                 where deleted = 0 and type = 'E' """
        params = []
        if form.supplier.value:
            sql += 'and supplier_id = %s '
            params.append(form.supplier.value)

        if form.short_name.value:
            sql += 'and short_name like %s '
            params.append('%' + form.short_name.value + '%')

        sql += ' order by id desc'

        page = Paginator(self, sql, params)

        self.render("coupon/delay_list.html", page=page, form=form, now=datetime.now())

    @require('operator')
    def post(self):
        delay_date = self.get_argument('delay', '').encode('utf-8')
        goods_id = self.get_argument('goods_id', 0).encode('utf-8')

        delay_date = datetime.strptime(delay_date, '%Y-%m-%d %H:%M:%S')

        self.db.execute('update item_coupon ic, item i set ic.expire_at=%s where ic.item_id=i.id and i.status=1 '
                        'and i.goods_id=%s and ic.expire_at < %s ', delay_date, goods_id, delay_date)

        self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                        'values (NOW(), 3, %s, %s, %s)', self.current_user.name,
                        '物品id:%s, 对应的券延期至 %s' % (goods_id, delay_date), goods_id)

