# -*- coding: utf-8 -*-

from .. import BaseHandler
from autumn.torn.paginator import Paginator
from autumn.torn.form import Form
from voluptuous import Schema, Length
from .. import require


list_schema = Schema({
    'supplier':         str,
    'received_type':    str,
}, extra=True)

add_schema = Schema({
    'supplier':         Length(min=1),
    'fee':              Length(min=1),
    'received_at':      Length(min=1),
    'received_type':    Length(min=1),
    'remark':           str,
}, extra=True)


class FeeList(BaseHandler):
    @require()
    def get(self):
        form = Form(self.request.arguments, list_schema)
        sql = """select s.short_name,sa.id sid, sa.fee, sa.received_at, sa.type, sa.created_at
                 fee_created_at, sa.remark, o.name sale_name
                 from supplier s left join supplier_ads_fee sa on s.id = sa.supplier_id
                 left join operator o on s.sales_id = o.id
                 where s.deleted = 0 and sa.deleted = 0 """

        params = []
        if form.supplier.value:
            sql += 'and s.short_name like %s '
            params.append('%' + form.supplier.value + '%')
        if form.received_type.value:
            sql += 'and sa.type = %s '
            params.append(form.received_type.value)

        sql += 'order by sa.id desc'
        page = Paginator(self, sql, params)
        self.render('supplier/fee_list.html', page=page, form=form)


class FeeAdd(BaseHandler):
    @require('operator')
    def get(self):
        form = Form(self.request.arguments, add_schema)
        self.render('supplier/fee_add.html', form=form)

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, add_schema)
        if not form.validate():
            return self.render('supplier/fee_add.html', form=form)
        #是否有该用户
        supplier = self.db.get('select id from supplier where short_name = %s', form.supplier.value)
        if supplier is None:
            form.supplier.error = u'没有该用户，请修改'
            return self.render('supplier/fee_add.html', form=form)

        #执行语句中的deleted默认为0,返回当前广告费id
        trade_id = self.db.execute('insert into supplier_ads_fee(supplier_id, fee, created_at, deleted, received_at,'
                                   'type, remark) values(%s, %s, NOW(), 0, %s, %s, %s)',
                                   supplier.id, form.fee.value, form.received_at.value,
                                   form.received_type.value, form.remark.value)
        #将该广告费加入对应销售的帐下
        account_sequence_remark = '添加广告费'
        self.db.execute('insert into account_sequence(type, account_id, trade_id, trade_type, created_at, amount, '
                        'remark) values("SUPPLIER_ADS_FEE", 3, %s, "ADS_FEE", NOW(), %s, %s)', trade_id,
                        form.fee.value, account_sequence_remark)
         # 记录订单日志
        self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                        'values (NOW(), 5, %s, %s, %s)',
                        self.current_user.name, "广告费添加 fee_id:%s" % trade_id,
                        trade_id)

        self.redirect(self.reverse_url('supplier.show_ads_fee'))


class FeeDelete(BaseHandler):
    @require('operator')
    def post(self):
        fee_id = self.get_argument('id')
        #从supplier_ads_fee删除对应行
        fee = self.db.get('select * from supplier_ads_fee where id = %s', fee_id)
        self.db.execute('update supplier_ads_fee set deleted = 1 where id = %s', fee_id)

        #同时也要在account_sequence中添加一条
        fee_amount = -fee.fee
        self.db.execute('insert into account_sequence(type, account_id, trade_id, trade_type, created_at, amount, '
                        'remark) values("SUPPLIER_ADS_FEE", 3, %s, %s, NOW(), %s, "删除广告费")',
                        fee.id, fee.type, fee_amount)
        # 记录订单日志
        self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                        'values (NOW(), 5, %s, %s, %s)',
                        self.current_user.name, "广告费删除 fee_id:%s" % fee_id,
                        fee_id)
        self.redirect(self.reverse_url('supplier.show_ads_fee'))