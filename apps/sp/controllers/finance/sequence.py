# -*- coding: utf-8 -*-
from voluptuous import Schema

from autumn.torn.paginator import Paginator
from .. import BaseHandler
from .. import require
from autumn.torn.form import Form

list_schema = Schema({
    'shop_id': str,
    'start_date': str,
    'end_date': str,
    'type': str,
}, extra=True)


class List(BaseHandler):
    @require('finance')
    def get(self):
        """ 商户财务明细 """
        form = Form(self.request.arguments, list_schema)

        sql = """select ass.created_at,a.type, ass.remark, ass.type, ass.trade_type, ass.amount,ass.status
                 from account_sequence ass left join account a on a.id = ass.account_id where display <> 2 """
        supplier = self.db.get('select * from supplier where id =%s and deleted=0', self.current_user.supplier_id)
         #查找商户门店对应的账户信息
        account_sql = 'select account_id from supplier_shop where 1=1 '
        account_sql += 'and id = %s ' if supplier.separate_account == '1' and self.current_user.shop_id != 0 else 'and supplier_id = %s '
        account_params = [self.current_user.shop_id if supplier.separate_account == '1' and self.current_user.shop_id != 0 else supplier.id]
        
        accounts = self.db.query(account_sql, *account_params)

        sql += 'and ass.account_id in (%s) ' % ','.join(['%s'] * len(accounts))

        params = [str(i.account_id) for i in accounts]

        if form.start_date.value:
            sql += "and ass.created_at >= %s "
            params.append(form.start_date.value)
        if form.end_date.value:
            sql += "and ass.created_at <= %s "
            params.append(form.end_date.value)
        if form.type.value:
            sql += "and ass.type = %s "
            params.append(form.type.value)

        sql += "order by ass.created_at desc"
        page = Paginator(self, sql, params)

        self.render("finance/sequence.html", form=form, page=page, supplier_user=self.current_user)