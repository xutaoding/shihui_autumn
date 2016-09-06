# -*- coding: utf-8 -*-

from . import BaseHandler, authenticated
from datetime import date, timedelta


class Index(BaseHandler):
    @authenticated
    def get(self):
        aid = self.current_user.id
        yesterday = (date.today()-timedelta(days=1)).strftime('%Y-%m-%d')
        account_id = self.db.get('select id from account where type=3 and uid=%s', aid).id
        profit = self.db.get('select sum(amount) profit from account_sequence where account_id=%s ', account_id).profit
        profit_yesterday = self.db.get('select sum(amount) profit from account_sequence where account_id=%s and '
                                'CAST(created_at as DATE)=%s',
                                account_id, yesterday).profit
        sales = self.db.get('select sum(amount) total, count(em.id) count from external_money em, supplier s '
                            'where s.id=em.uid and s.agent_id=%s and em.type=1 and source=3', aid)
        sales_yesterday = self.db.get('select sum(amount) total, count(em.id) count from external_money em, supplier s '
                                      'where s.id=em.uid and s.agent_id=%s and em.type=1 and source=3 and '
                                      'CAST(em.created_at as DATE)=%s', aid, yesterday)
        self.render('welcome/index.html', profit=profit, sales=sales, profit_yesterday=profit_yesterday,
                    sales_yesterday=sales_yesterday)

