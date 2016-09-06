# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from autumn.torn.form import Form
from voluptuous import Schema, Length, Any
from autumn.torn.paginator import Paginator

account_schema = Schema({
    'user_name':        Length(min=1),
    'bank_name':        Length(min=1),
    'bank_city':        Length(min=1),
    'sub_bank_name':    Length(min=1),
    'card_number':      Length(min=1),
    'action':           Any('edit', 'add'),
    'supplier_id':      str,
    'uid':              str,
    'id':               str,
}, required=True, extra=True)


class List(BaseHandler):
    @require()
    def get(self, supplier_id):
        supplier = self.db.get('select * from supplier where id=%s', supplier_id)
        sql = """select wa.*, ss.name shop_name from withdraw_account wa
                 left join supplier_shop ss on wa.type="SUPPLIER_SHOP" and ss.id=wa.uid
                  where wa.deleted=0 and
                  ( (wa.type="SUPPLIER" and wa.uid=%s) or
                    (wa.type="SUPPLIER_SHOP" and wa.uid in
                      (select id from supplier_shop where deleted=0 and supplier_id=%s)))"""
        page = Paginator(self, sql, [supplier_id, supplier_id])

        self.render('supplier/bank/list.html', supplier=supplier, page=page)


class Add(BaseHandler):
    @require('operator')
    def get(self):
        form = Form(self.request.arguments, account_schema)
        form.action.value = 'add'
        supplier = self.db.get('select * from supplier where id = %s', form.supplier_id.value)

        shop_list = self.db.query('select id, name from supplier_shop where deleted=0 and supplier_id = %s',
                                  supplier.id)
        self.render('supplier/bank/bank.html', form=form, supplier=supplier, shop_list=shop_list, error='')

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, account_schema)
        supplier = self.db.get('select * from supplier where id = %s', form.supplier_id.value)
        if not form.validate():
            shop_list = self.db.query('select id, name from supplier_shop where deleted=0 and supplier_id = %s',
                                      supplier.id)
            return self.render('supplier/bank/bank.html', form=form, supplier=supplier, shop_list=shop_list,
                               error='error')

        #独立结算的门店
        account_type = 'SUPPLIER' if supplier.separate_account == '0' else 'SUPPLIER_SHOP'

        self.db.execute('insert into withdraw_account (user_name,bank_name,bank_city,sub_bank_name,card_number,'
                        'uid,type,created_at,created_by) values (%s,%s,%s,%s,%s,%s,%s,now(),%s) ',
                        form.user_name.value, form.bank_name.value, form.bank_city.value, form.sub_bank_name.value,
                        form.card_number.value, form.uid.value, account_type, self.current_user.name)

        self.redirect(self.reverse_url('supplier.bank', supplier.id))


class Edit(BaseHandler):
    @require('operator')
    def get(self):
        account = self.db.get('select * from withdraw_account where id = %s', self.get_argument('id'))
        form = Form(account, account_schema)
        form.action.value = 'edit'

        if account.type == 'SUPPLIER_SHOP':
            supplier = self.db.get('select * from supplier where id = '
                                   '(select supplier_id from supplier_shop where id=%s)', account.uid)
            shop_list = self.db.query('select id, name from supplier_shop where supplier_id = %s', supplier.id)
        else:
            supplier = self.db.get('select * from supplier where id = %s', account.uid)
            shop_list = []

        self.render('supplier/bank/bank.html', form=form, shop_list=shop_list, supplier=supplier, error='')

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, account_schema)
        account_id = self.get_argument('id')
        account = self.db.get('select * from withdraw_account where id = %s', account_id)

        if account.type == 'SUPPLIER_SHOP':
            supplier = self.db.get('select * from supplier where id = '
                                   '(select supplier_id from supplier_shop where id=%s)', account.uid)
            shop_list = self.db.query('select id, name from supplier_shop where supplier_id = %s', supplier.id)
        else:
            supplier = self.db.get('select * from supplier where id = %s', account.uid)
            shop_list = []

        if not form.validate():
            return self.render('supplier/bank/bank.html', form=form, shop_list=shop_list, supplier=supplier,
                               error='error')

        self.db.execute('update withdraw_account set uid=%s, user_name = %s,bank_name = %s,bank_city = %s,'
                        'sub_bank_name = %s,card_number=%s where id = %s',
                        form.uid.value, form.user_name.value, form.bank_name.value,
                        form.bank_city.value, form.sub_bank_name.value, form.card_number.value, account_id)

        self.redirect(self.reverse_url('supplier.bank', supplier.id))


class Delete(BaseHandler):
    @require('operator')
    def post(self):
        account_id = self.get_argument('id')
        self.db.execute('update withdraw_account set deleted = 1 where id = %s', account_id)
        account = self.db.get('select uid, type from withdraw_account where id = %s', account_id)

        if account.type == 'SUPPLIER_SHOP':
            supplier_id = self.db.get('select id from supplier where id = '
                                      '(select supplier_id from supplier_shop where id=%s)', account.uid).id
        else:
            supplier_id = self.db.get('select id from supplier where id = %s', account.uid).id

        self.redirect(self.reverse_url('supplier.bank', supplier_id))
