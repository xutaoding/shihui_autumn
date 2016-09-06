# -*- coding: utf-8 -*-

from . import BaseHandler, authenticated
from autumn.torn.paginator import Paginator


class SupplierMoney(BaseHandler):
    @authenticated
    def get(self):
        sql = """
            select em.amount, em.created_at, s.name, s.short_name
            from external_money em, supplier s
            where em.uid=s.id and em.type=1 and em.source=3 and s.agent_id=%s
            order by em.id desc
         """

        page = Paginator(self, sql, [self.current_user.id])
        self.render('finance/supplier_money.html', page=page)


class Sequence(BaseHandler):
    @authenticated
    def get(self):
        start_at = self.get_argument('start_at', '')
        end_at = self.get_argument('end_at', '')

        sql = 'select s.* from account_sequence s, account a ' \
              'where s.account_id=a.id and a.type=3 and a.uid=%s '
        params = [self.current_user.id]
        if start_at:
            sql += 'and s.created_at >= %s '
            params.append(start_at)
        if end_at:
            sql += 'and s.created_at <= %s '
            params.append(end_at)

        sql += 'order by id desc'

        page = Paginator(self, sql, params, page_size=10)
        self.render('finance/sequence.html', page=page, start_at=start_at, end_at=end_at)

        self.render('finance/sequence.html', page=page)


class WithdrawList(BaseHandler):
    @authenticated
    def get(self):
        sql = 'select w.* from withdraw_bill w, account a ' \
              'where w.account_id=a.id and a.type=3 and a.uid=%s order by id desc'
        params = [self.current_user.id]

        page = Paginator(self, sql, params)
        self.render('finance/withdraw/list.html', page=page)


class WithdrawApply(BaseHandler):
    @authenticated
    def get(self):
        self.render('finance/withdraw/apply.html')

    @authenticated
    def post(self):
        pass
