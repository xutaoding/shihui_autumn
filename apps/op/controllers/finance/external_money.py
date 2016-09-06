# -*- coding: utf-8 -*-
from .. import BaseHandler
from .. import require
from datetime import datetime
from autumn.torn.paginator import Paginator
from autumn.torn.form import Form
from autumn.utils.dt import ceiling
from decimal import Decimal
from voluptuous import Schema, Any, All, Coerce, Range
from autumn import const


class List(BaseHandler):
    @require()
    def get(self):
        """ 外部资金展示"""
        sql = """select em.id,em.uid supplier_id,em.amount,em.source,em.remark,em.settle_remark,em.created_at,em.created_by,
                 em.expire_at,em.used_amount, em.flag, s.short_name
                 from external_money em,supplier s
                 where em.deleted = 0 and s.id = em.uid and type=1 """
        form = Form(self.request.arguments, list_schema)
        params = []
        if form.supplier.value:
            sql += 'and em.uid = %s '
            params.append(form.supplier.value)

        if form.source.value:
            sql += 'and em.source = %s '
            params.append(form.source.value)

        sql += 'order by em.id desc'

        page = Paginator(self, sql, params)
        money_type = {
            0: {0: '预付款', 1: '保证金'},
            1: {0: '预付款', 1: '保证金'},
            2: {0: '上线费', 1: '广告费', 2: '代运营费'},
            3: {0: '微信服务费'}
        }
        self.render("finance/external_money_list.html", form=form, page=page, money_type=money_type)


class Add(BaseHandler):
    @require('finance')
    def get(self):
        form = Form(self.request.arguments, add_schema)
        form.action.value = 'add_external_money'
        self.render("finance/external_money.html", form=form)

    @require('finance')
    def post(self):
        form = Form(self.request.arguments, add_schema)
        # flag为2时表示广告费
        if self.get_argument('flag') == '2':
            fee_sql = """insert into external_money(amount, uid, source, expire_at, created_at, created_by, type,
                         remark, flag, deleted) values(%s, %s, %s, %s, NOW(), %s, 1, %s, %s, 0)"""
            flag = {'ONLINE_FEE': 0, 'ADS_FEE': 1, 'OPERATE_FEE': 2}.get(form.received_type.value, 'ONLINE_FEE')
            params = [form.fee.value, form.supplier.value, 2, form.received_at.value, self.current_user.name,
                      form.fee_remark.value, flag]
            trade_id = self.db.execute(fee_sql, *params)

            # #将该广告费加入对应销售的帐下
            self.db.execute('insert into supplier_ads_fee(supplier_id, created_at, fee, received_at, type, remark) '
                            'values(%s, NOW(), %s, %s, %s, %s)', form.supplier.value, form.fee.value,
                            form.received_at.value, flag, form.fee_remark.value)
             # 记录日志
            self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                            'values (NOW(), 5, %s, %s, %s)',
                            self.current_user.name, "广告费添加 fee_id:%s" % trade_id,
                            trade_id)
        # flag为3时表示微信收费, 后期可扩展, 目前只记一笔到外部资金, 插一条日志，type=6
        elif self.get_argument('flag') == '3':
            sql = """insert into external_money (amount, uid, source, expire_at, created_at, created_by, remark,
            flag, deleted, type) values (%s,%s,%s,%s,now(),%s,%s,%s,0,1)"""
            flag = 0  # 暂时记为微信服务费
            source = 3  # 来源记为3
            trade_id = self.db.execute(sql, form.amount.value.strip(), form.supplier.value, source,
                                       form.expire_at.value, self.current_user.name, form.remark.value, flag)
            # 记录日志
            self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                            'values (NOW(), 6, %s, %s, %s)',
                            self.current_user.name, "微信收费.trade_id:%s" % trade_id,
                            trade_id)

        else:
            form.expire_at.value = ceiling(datetime.strptime(form.expire_at.value, '%Y-%m-%d'), today=True)
            #我们给商户时，给flag设值
            if form.source.value == '0':
                form.flag.value = form.type.value
            sql = """ insert into external_money (amount,uid,source,expire_at,created_at,created_by,remark,flag,
            deleted,type) values (%s,%s,%s,%s,now(),%s,%s,%s,0,1) """
            trade_id = self.db.execute(sql, form.amount.value.strip(), form.supplier.value, form.source.value,
                                       form.expire_at.value, self.current_user.name, form.remark.value, form.flag.value)

            # 查找商户及门店的账户
            supplier_shop_account_id = self.db.get('select ss.account_id from supplier s,supplier_shop ss '
                                                   'where s.id=ss.supplier_id and s.deleted =0 and s.id=%s limit 1',
                                                   form.supplier.value).account_id
            #我们给商户场合，预付款（前期销售额不能提现）或者商户给我的保证金从销售额中扣除的场合，都要记一笔资金
            if (form.source.value == '0' and form.type.value == '0') or \
                    (form.source.value == '1' and form.type.value == '0'):
                #seq 中加一条 负资金
                self.db.execute('insert into account_sequence(type, trade_id, account_id,created_at, amount,remark) '
                                'values(%s, %s, %s, NOW(), %s, %s)', const.seq.PRE_PAYMENT, trade_id,
                                supplier_shop_account_id, -Decimal(form.amount.value), "付给商户的预付款(前期销售额不能提现)")

        self.redirect('/external-money')


class Edit(BaseHandler):
    @require('finance')
    def get(self):
        id = self.get_argument('id')
        external_money = self.db.get('select em.*,s.short_name from external_money em,supplier s '
                                     'where s.id =em.supplier_id and em.id = %s', id)
        form = Form(external_money, add_schema)
        form.action.value = 'edit_external_money'
        self.render("finance/external_money.html", form=form)


    @require('finance')
    def post(self):
        id = self.get_argument('id')
        form = Form(self.request.arguments, add_schema)
        form.expire_at.value = ceiling(datetime.strptime(form.expire_at.value, '%Y-%m-%d'), today=True)
        #我们给商户时，给flag设值
        if form.source.value == '0':
            form.flag.value = form.type.value

        sql = """ update external_money set amount =%s, remark=%s, expire_at=%s,updated_at=now(),updated_by=%s
        where id=%s"""
        self.db.execute(sql, form.amount.value.strip(), form.remark.value, form.expire_at.value,
                        self.current_user.name, id)
        #我们给商户场合，预付款（前期销售额不能提现）或者商户给我的保证金从销售额中扣除的场合，都要记一笔资金
        if (form.source.value == '0' and form.type.value == '0') or \
                (form.source.value == '1' and form.type.value == '0'):
            #更新seq 负资金
            self.db.execute('update account_sequence set amount = %s '
                            'where trade_id = %s and type = %s and amount > 0',
                            Decimal(form.amount.value).copy_negate(), const.seq.PRE_PAYMENT, id)
        self.redirect('/external-money')


class Delete(BaseHandler):
    @require('finance')
    def post(self):
        """ 删除资金记录 """
        id = self.get_argument('id')
        self.db.execute('update external_money set deleted = 1 where id = %s ', id)
        external_money = self.db.get('select em.* from external_money em where em.id = %s ', id)

        # 查找商户及门店的账户
        supplier_shop_account_id = self.db.get('select ss.account_id from supplier s,supplier_shop ss '
                                               'where s.id=ss.supplier_id and s.deleted =0 and s.id=%s limit 1',
                                               external_money.supplier_id).account_id
        #添加对应的seq 资金
        self.db.execute('insert into account_sequence(type, trade_id, account_id,created_at, amount,remark) '
                        'values(%s, %s, %s, NOW(), %s, %s)', const.seq.PRE_PAYMENT, id,
                        supplier_shop_account_id, external_money.amount, "减去给商户的预付款(前期销售额不能提现)")

        self.redirect('/external-money')


list_schema = Schema({
    'supplier': str,
    'source': str,
}, extra=True)

add_schema = Schema({
    'supplier': str,
    'amount': All(Coerce(Decimal), Range(min=Decimal(0.1))),
    'source': str,
    'flag': str,
    'id': str,
    'type': str,
    'expire_at': str,
    'remark': str,
    'short_name': str,
    'action': Any('add_external_money', 'edit_external_money'),
    'fee': str,
    'received_at': str,
    'fee_remark': str,
    'received_type': Any('OPERATE_FEE', 'ADS_FEE', 'ONLINE_FEE')
}, extra=True)
