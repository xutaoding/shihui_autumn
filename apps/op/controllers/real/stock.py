# -*- coding: utf-8 -*-
import string
from voluptuous import Schema, Length, Any

from autumn.torn.form import Form
from .. import BaseHandler
from .. import require
from autumn.torn.paginator import Paginator

stock_schema = Schema({
    'num': Length(min=1),
    'remark': Length(min=1),
    'action': Any('in', 'out'),
    'sku': str,
    'skuId': str,
}, extra=True)


class StockIn(BaseHandler):
    @require('storage')
    def get(self):
        form = Form(self.request.arguments, stock_schema)
        form.action.value = 'in'

        self.render('real/stock.html', form=form, error='')

    @require('storage')
    def post(self):
        form = Form(self.request.arguments, stock_schema)
        sku = self.db.get('select price from sku where id = %s', form.skuId.value)

        if not form.validate():
            return self.render('real/stock.html', form=form, error='error')

        self.db.execute('insert into stock_item (sku_id,num,price,remark,type,'
                        'created_at,created_by,deleted,remain_stock) '
                        'values (%s,%s,%s,%s,%s,now(),%s,0,%s)',
                        form.skuId.value, form.num.value, sku.price, form.remark.value,
                        'IN', self.current_user.name, form.num.value)

        stock = self.db.get('select sum(si.remain_stock) remain_stock from stock_item si '
                            'where si.sku_id = %s and si.deleted = 0 ', form.skuId.value)

        # 更新货品库存
        self.db.execute('update sku set stock = %s where id = %s', stock.remain_stock, form.skuId.value)

        self.redirect(self.reverse_url('real.stock_list'))


class StockOut(BaseHandler):
    @require('storage')
    def get(self):
        form = Form(self.request.arguments, stock_schema)
        form.action.value = 'out'

        self.render('real/stock.html', form=form, error='')

    @require('storage')
    def post(self):
        form = Form(self.request.arguments, stock_schema)
        sku_id = form.skuId.value
        sku = self.db.get('select price from sku where id = %s', sku_id)
        stock = self.db.get('select sum(si.remain_stock) remain_stock from stock_item si '
                            'where si.sku_id = %s and si.deleted = 0 ', sku_id)

        if string.atoi(form.num.value) > stock.remain_stock:
            form.num.error = '出库数量不能大于剩余库存'

        if not form.validate():
            return self.render('real/stock.html', form=form, error='error')

        out_num = 0 - string.atoi(form.num.value)

        self.db.execute('insert into stock_item (sku_id,num,price,remark,type,'
                        'created_at,created_by,deleted) '
                        'values (%s,%s,%s,%s,%s,now(),%s,0)',
                        sku_id, out_num, sku.price, form.remark.value,
                        'OUT', self.current_user.name)

        stocks = self.db.query('select * from stock_item where sku_id = %s and remain_stock>0 and type ="IN" '
                               'order by created_at', sku_id)
        abs_out_num = string.atoi(form.num.value)

        for stock in stocks:
            stock.remain_stock = stock.remain_stock - abs_out_num
            if stock.remain_stock < 0:
                abs_out_num = abs_out_num + stock.remain_stock
                self.db.execute('update stock_item set remain_stock = 0 where id = %s', stock.id)
            else:
                self.db.execute('update stock_item set remain_stock = %s where id = %s', stock.remain_stock, stock.id)
                break

        # 最新货品库存情况
        stock = self.db.get('select sum(si.remain_stock) remain_stock from stock_item si '
                            'where si.sku_id = %s and si.deleted = 0 ', sku_id)

        # 更新货品库存
        self.db.execute('update sku set stock = %s where id = %s', stock.remain_stock, sku_id)

        self.redirect(self.reverse_url('real.stock_list'))


class StockList(BaseHandler):
    @require()
    def get(self):
        sql = """select si.*,s.name sku_name from stock_item si,sku s where si.deleted = 0 and s.id = si.sku_id """
        form = Form(self.request.arguments, stock_schema)
        params = []

        if form.sku.value:
            sql += 'and s.name like %s '
            params.append('%' + form.sku.value + '%')

        sql += 'order by si.id desc'
        page = Paginator(self, sql, params)
        self.render('real/stock_list.html', page=page, form=form)






