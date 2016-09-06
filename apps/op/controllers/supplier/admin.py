# -*- coding: utf-8 -*-
from voluptuous import Schema, Length, Any

from autumn.torn.form import Form
from .. import BaseHandler
from .. import require
from autumn.torn.paginator import Paginator
from autumn.torn.form import EmptyList
from tornado.options import options
import hashlib
import random
import string

supplier_schema = Schema({
    'supplier': str,
    'name': Length(min=1),
    'short_name': Length(min=1),
    'separate_account': str,
    'domain_name': Length(min=1),
    'sales_id': Length(min=1),
    'properties': EmptyList(),
    'contact': str,
    'id': str,
    'agent_id': Length(min=1),
    'code': str,
    'action': Any('edit', 'add'),
}, extra=True)


class Add(BaseHandler):
    @require('operator')
    def get(self):
        form = Form(self.request.arguments, supplier_schema)
        form.action.value = 'add'

        operators = self.db.query('select * from operator where deleted = 0')
        agents = self.db.query('select id, short_name from agent where deleted = 0')

        self.render('supplier/supplier.html', form=form,  operators=operators, error='', agents=agents)

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, supplier_schema)

        operators = self.db.query('select * from operator where deleted = 0')
        agents = self.db.query('select id, short_name from agent where deleted = 0')
        if not form.validate():
            return self.render('supplier/supplier.html', form=form, operators=operators, error='请检查各项输入', agents=agents)
        if self.db.query('select * from supplier where domain_name=%s', form.domain_name.value):
            return self.render('supplier/supplier.html', form=form, operators=operators, error='已经有商户使用此域名', agents=agents)
        if not form.properties.value:
            return self.render('supplier/supplier.html', form=form, operators=operators, error='请至少选择一个商家属性', agents=agents)
        if not form.separate_account.value:
            form.separate_account.value = 0

        if form.code.value and self.db.get('select * from supplier where code = %s', form.code.value):
            return self.render('supplier/supplier.html', form=form, operators=operators, error='已经有商户使用此协议编号', agents=agents)

        supplier_id = self.db.execute(
            'insert into supplier set name=%s, short_name=%s, domain_name=%s, sales_id=%s, separate_account=%s, '
            'properties=%s, account_id=0, created_at=NOW(),created_by=%s,contact=%s,agent_id=%s, code=%s',
            form.name.value.strip(), form.short_name.value.strip(), form.domain_name.value.strip(),
            form.sales_id.value.strip(), form.separate_account.value, ','.join(form.properties.value),
            self.current_user.name, form.contact.value, form.agent_id.value, form.code.value)

        #添加商户账户
        account_id = self.db.execute(
            'insert into account set uid=%s, type=1, created_at=NOW(), amount=0', supplier_id)
        self.db.execute('update supplier set account_id = %s where id =%s', account_id, supplier_id)

        # 如果有微信的商家属性，则增加一个分销店铺，用以微信商城使用
        if 'weixin' in form.properties.value:
            distributor_shop_id = self.db.execute('insert into distributor_shop(distributor_id, name, money_manager, '
                                                  'created_at, created_by, distributor_name, deleted) values(%s, %s, '
                                                  '"SHOP", NOW(), %s, "微信", 1)', options.distributor_id_weixin,
                                                  form.short_name.value.strip() + '微信店', '系统')
            self.db.execute('insert into supplier_property(sp_id, name, value) values(%s, "wx_shop_id", %s)',
                            supplier_id, distributor_shop_id)

        self.redirect(self.reverse_url('supplier.detail', supplier_id))


class Edit(BaseHandler):
    @require('operator')
    def get(self):
        supplier = self.db.get('select * from supplier where id = %s', self.get_argument('id'))
        form = Form(supplier, supplier_schema)
        form.action.value = 'edit'
        operators = self.db.query('select * from operator where deleted = 0')
        agents = self.db.query('select * from agent where deleted = 0')

        self.render('supplier/supplier.html', form=form, operators=operators, error='', agents=agents)

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, supplier_schema)
        supplier_id = self.get_argument('id')

        operators = self.db.query('select * from operator where deleted = 0')
        agents = self.db.query('select * from agent where deleted = 0')
        if not form.validate():
            return self.render('supplier/supplier.html', form=form, operators=operators, error='请检查各项输入', agents=agents)
        if self.db.query('select * from supplier where domain_name=%s and id<>%s', form.domain_name.value, supplier_id):
            return self.render('supplier/supplier.html', form=form, operators=operators, error='已经有商户使用此域名', agents=agents)
        if not form.properties.value:
            return self.render('supplier/supplier.html', form=form, operators=operators, error='请至少选择一个商家属性', agents=agents)

        if form.code.value and self.db.get('select * from supplier where code = %s and id != %s', form.code.value, supplier_id):
            return self.render('supplier/supplier.html', form=form, operators=operators, error='已经有商户使用此协议', agents=agents)

        self.db.execute(
            'update supplier set name=%s, short_name=%s,domain_name=%s,sales_id=%s,properties=%s,'
            'contact=%s,agent_id=%s, code=%s where id = %s',
            form.name.value.strip(), form.short_name.value.strip(), form.domain_name.value.strip(),
            form.sales_id.value, ','.join(form.properties.value), form.contact.value, form.agent_id.value,
            form.code.value, supplier_id)

        distr_shop = self.db.get('select * from supplier_property where name="wx_shop_id" and sp_id = %s',
                                 supplier_id)
        if 'weixin' in form.properties.value and not distr_shop:
            distributor_shop_id = self.db.execute('insert into distributor_shop(distributor_id, name, money_manager, '
                                                  'created_at, created_by, distributor_name, deleted) values(%s, %s, '
                                                  '"SHOP", NOW(), %s, "微信", 1)', options.distributor_id_weixin,
                                                  form.short_name.value.strip() + '微信店', '系统')
            self.db.execute('insert into supplier_property(sp_id, name, value) values(%s, "wx_shop_id", %s)',
                            supplier_id, distributor_shop_id)

        self.redirect(self.reverse_url('supplier.detail', supplier_id))


class List(BaseHandler):
    @require()
    def get(self):
        sql = """select s.*,o.name sales_name, o.id sales_id from supplier s
                 left join operator o on s.sales_id = o.id where s.deleted=0 """
        form = Form(self.request.arguments, supplier_schema)
        params = []

        if form.id.value:
            sql += 'and s.id = %s '
            params.append(form.id.value)

        if form.sales_id.value:
            sql += 'and s.sales_id = %s '
            params.append(form.sales_id.value)

        if form.code.value:
            sql += 'and s.code = %s '
            params.append(form.code.value)

        sql += 'order by s.id desc'
        page = Paginator(self, sql, params)
        self.render('supplier/list.html', page=page, form=form)


class Detail(BaseHandler):
    @require()
    def get(self, supplier_id):
        """ 显示商户详情 """
        # 商户信息
        supplier = self.db.get('select s.*,o.name sales_name, a.short_name agent_name from supplier s '
                               'join operator o on o.id=s.sales_id '
                               'left join agent a on s.agent_id = a.id '
                               'where s.id = %s', supplier_id)
        max_withdraw = self.db.get('select * from supplier_property where name = "max_withdraw" and sp_id = %s',
                                   supplier_id)
        wx_commission = self.db.get('select * from supplier_property where name = "wx_commission" and sp_id = %s',
                                    supplier_id)
        wx_shop_max = self.db.get('select * from supplier_property where name = "wx_shop_max" and sp_id = %s',
                                  supplier_id)

        self.render('supplier/detail.html', supplier=supplier, max_withdraw=max_withdraw, wx_commission=wx_commission,
                    wx_shop_max=wx_shop_max)


class Delete(BaseHandler):
    @require('operator')
    def post(self):
        self.db.execute('update supplier set deleted=1 where id=%s', self.get_argument('id'))
        self.redirect(self.reverse_url('supplier.show_list'))


class Manual(BaseHandler):
    @require()
    def get(self, supplier_id):
        shops = self.db.query('select * from supplier_shop where supplier_id=%s', supplier_id)
        supplier = self.db.get('select * from supplier where id=%s', supplier_id)
        users = self.db.query(
            'select su.* ,ss.name shop_name from supplier_user su left join supplier_shop ss '
            'on su.shop_id =ss.id where su.deleted = 0 and su.supplier_id=%s order by su.id desc', supplier_id)

        self.render('supplier/train.html', supplier=supplier, shops=shops, users=users)


class MaxWithdrawEdit(BaseHandler):
    @require('finance', 'sales')
    def post(self):
        max_withdraw = self.get_argument('max_withdraw', 0)
        supplier_id = self.get_argument('supplier_id', 0)

        self.db.execute('delete from supplier_property where name = "max_withdraw" and sp_id = %s', supplier_id)

        self.db.execute('insert into supplier_property(sp_id, name, value) values(%s, "max_withdraw", %s)',
                        supplier_id, max_withdraw)

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write({'result': max_withdraw})


class WeixinCommission(BaseHandler):
    @require('finance', 'sales')
    def post(self):
        wx_commission = self.get_argument('max_withdraw', 0)
        supplier_id = self.get_argument('supplier_id', 0)

        self.db.execute('delete from supplier_property where name = "wx_commission" and sp_id = %s', supplier_id)

        self.db.execute('insert into supplier_property(sp_id, name, value) values(%s, "wx_commission", %s)',
                        supplier_id, wx_commission)

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write({'result': wx_commission})


class WeixinShopMax(BaseHandler):
    @require('finance', 'sales')
    def post(self):
        count = self.get_argument('max_withdraw', 0)
        supplier_id = self.get_argument('supplier_id', 0)

        self.db.execute('delete from supplier_property where name = "wx_shop_max" and sp_id = %s', supplier_id)

        self.db.execute('insert into supplier_property(sp_id, name, value) values(%s, "wx_shop_max", %s)',
                        supplier_id, count)

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        if count == '0':
            count = '无限制'
        else:
            count += u'间'
        self.write({'result': count})