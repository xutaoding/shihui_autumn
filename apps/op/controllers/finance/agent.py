# -*- coding: utf-8 -*-
from .. import BaseHandler
from .. import require
import logging
from voluptuous import Schema
from autumn import const
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator
from autumn.utils import PropDict
from decimal import Decimal

list_schema = Schema({
    'agent_name': str,
    'agent_id': str,
    'agent_type': str,
    'start_date': str,
    'end_date': str,
    'status': str,
    'action': str
}, extra=True)


class AgentSequence(BaseHandler):
    """代理商资金明细"""
    @require()
    def get(self):
        form = Form(self.request.arguments, list_schema)
        sql = 'select s.short_name, em.amount eamount, em.remark eremark, ac.amount aamount, ac.remark aremark, ' \
              'em.created_by, em.created_at ' \
              'from external_money em left join account_sequence ac ' \
              'on em.id=ac.trade_id and ac.type=6 join supplier s ' \
              'where em.source=3 and em.flag=0 and em.deleted=0 and s.id=em.uid '
        params = []
        if form.agent_id.value:
            sql += ' and s.agent_id = %s '
            params.append(form.agent_id.value)
        if form.start_date.value:
            sql += ' and em.created_at > %s '
            params.append(form.start_date.value)
        if form.end_date.value:
            sql += ' and em.created_at < %s '
            params.append(form.end_date.value)

        page = Paginator(self, sql, params)
        self.render('finance/agent/sequence.html', form=form, page=page)


class PayList(BaseHandler):
    """代理商充值明细"""
    @require()
    def get(self):
        form = Form(self.request.arguments, list_schema)
        sql = 'select a.short_name, em.* from external_money em, agent a where em.deleted=0 ' \
              'and em.type=2 and em.uid=a.id '
        params = []
        if form.agent_id.value:
            sql += ' and em.uid=%s '
            params.append(form.agent_id.value)
        if form.start_date.value:
            sql += ' and em.created_at > %s'
            params.append(form.start_date.value)
        if form.end_date.value:
            sql += ' and em.created_at < %s'
            params.append(form.end_date.value)

        sql += ' order by id desc '
        page = Paginator(self, sql, params)
        self.render('finance/agent/pay_list.html', form=form, page=page)


class DepositCheck(BaseHandler):
    """代理商定金查询"""
    @require('finance')
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        agent_id = self.get_argument('agent_id', '')
        if not agent_id:
            self.write({'error': '没有找到代理商'})
            return
        agent = self.db.get('select * from external_money where type=2 and deleted=0 and uid=%s and '
                            'expire_at>NOW() and source=1 and flag=1', agent_id)
        if not agent:
            self.write({'error': '该代理商还没有交保证金, 如果已支付, 请先添加保证金'})
        if agent:
            self.write({'ok': '保证金:%s' % agent.amount})


class Deposit(BaseHandler):
    """添加代理商定金"""
    @require()
    def get(self):
        self.render('finance/agent/deposit.html')
        pass

    @require('finance')
    def post(self):
        agent_id = self.get_argument('agent', '')
        expire_at = self.get_argument('expire_at', '')
        amount = self.get_argument('amount', '')
        remark = self.get_argument('remark', '')
        if agent_id and expire_at and amount:
            # 记录到 external_money, flag 为1，表示保证金
            sql = """insert into external_money (amount, uid, source, expire_at, created_at, created_by, remark,
            flag, deleted, type) values (%s,%s,1,%s,now(),%s,%s,1,0,2)"""
            self.db.execute(sql, amount, agent_id, expire_at, self.current_user.name, remark)
            self.redirect(self.reverse_url('finance.agent_pay_list'))
        else:
            self.redirect(self.reverse_url('finance.agent_deposit'))


class Credit(BaseHandler):
    """代理商预付款入账"""
    @require()
    def get(self):
        self.render('finance/agent/credit.html')

    @require('finance')
    def post(self):
        agent_id = self.get_argument('agent', '')
        set_type = self.get_argument('set_type', '')
        amount = self.get_argument('amount', '')
        expire_at = self.get_argument('expire_at', '')
        remark = self.get_argument('remark', '')
        stock = self.get_argument('stock', '')
        if agent_id and set_type and amount and expire_at:
            # 记录到 external_money, flag 为0，表示预付款
            sql = """insert into external_money (amount, uid, source, expire_at, created_at, created_by, remark,
            flag, deleted, type) values (%s,%s,1,%s,now(),%s,%s,0,0,2)"""
            self.db.execute(sql, amount, agent_id, expire_at, self.current_user.name,
                            u'充值%s套，备注：%s' % (stock, remark))
            # 更新库存
            self.db.execute('update agent set stock=stock+%s where id=%s', stock, agent_id)
            self.redirect(self.reverse_url('finance.agent_pay_list'))
        else:
            self.redirect(self.reverse_url('finance.agent_credit'))

        self.render('finance/agent/credit.html')


class SupplierCheck(BaseHandler):
    """根据商户去查对应的代理商"""
    @require('finance')
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        sp_id = self.get_argument('sp_id', '')
        aid = self.db.get('select agent_id from supplier where deleted=0 and id=%s', sp_id)
        if not aid:
            self.write({'error': '该商户不属于任何代理商，如需开通微信，请至外部资金添加'})
            return
        agent = self.db.get('select id, short_name, stock, type from agent where deleted=0 and id=%s', aid.agent_id)
        if not agent:
            self.write({'error': '该商户所对应的代理商不正确，可能已经删除'})
            return
        else:
            t = agent.pop('type')
            sale_type = {1: '预付款模式(该模式下，库存为0时，商户不能入账)', 2: '零售模式'}.get(t)
            agent.update({'type': sale_type})
            self.write(agent)
            return


class AddSupplier(BaseHandler):
    """收取商户微信开通费"""
    @require()
    def get(self):
        self.render('finance/agent/add_supplier.html')

    @require('finance')
    def post(self):
        agent_id = self.get_argument('agent_id', '')
        sp_id = self.get_argument('supplier_id', '')
        amount = Decimal(self.get_argument('amount', ''))
        expire_at = self.get_argument('expire_at', '')
        remark = self.get_argument('remark', '')
        sp = self.db.get('select id, agent_id, short_name from supplier where deleted=0 and id=%s', sp_id)
        if not sp or str(sp.agent_id) != str(agent_id):
            logging.error('add supplier wx fee from agent failed: wrong sp_id %s or wrong agent_id %s'
                          % (sp_id, agent_id))
            self.redirect(self.reverse_url('finance.agent_add_supplier'))
            return
        agent = self.db.get('select at.short_name, at.id, at.type, ac.id as account_id from agent at, account ac '
                            'where at.id=ac.uid and ac.type=3 and deleted=0 and at.id=%s', agent_id)
        if not agent:
            logging.error('add supplier wx fee from agent failed: can not find agent_id %s', agent_id)
            self.redirect(self.reverse_url('finance.agent_add_supplier'))
            return

        # 商户记一笔外部资金
        sql = """insert into external_money (amount, uid, source, expire_at, created_at, created_by, remark,
        flag, deleted, type) values (%s,%s,%s,%s,now(),%s,%s,%s,0,1)"""
        flag = 0  # 暂时记为微信服务费
        source = 3  # 来源记为3
        trade_id = self.db.execute(sql, amount, sp_id, source,
                                   expire_at, self.current_user.name, u'微信服务费,备注：%s'%remark, flag)

        # 如果是预付款代理商， 更新代理商库存， 同时记一条account_sequence, 金额为3888的基数，加上超出3888的部分*70%
        if agent.type == 1:
            self.db.execute('update agent set stock=stock-1 where id=%s', sp_id)

            agent_amount = Decimal(3888) + (amount - Decimal(3888)) * Decimal(0.7)
            self.db.execute('insert into account_sequence(type, trade_id, account_id,created_at, amount,remark, status)'
                            ' values(%s, %s, %s, NOW(), %s, %s, 1)', const.seq.WX, trade_id, agent.account_id,
                            agent_amount, "收到商户 %s 的微信CRM系统付款，所属代理商 %s" % (sp.short_name, agent.short_name))
        self.redirect(self.reverse_url('finance.agent_sequence'))





