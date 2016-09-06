# -*- coding: utf-8 -*-

from . import BaseHandler, authenticated
from autumn.torn.paginator import Paginator


class List(BaseHandler):
    @authenticated
    def get(self):
        page = Paginator(self, 'select * from supplier where agent_id = %s', [self.current_user.id])
        self.render('supplier/list.html', page=page)


class Sequence(BaseHandler):
    @authenticated
    def get(self):
        supplier_name = self.get_argument('supplier_name', '')
        if supplier_name:
            supplier = self.db.query('select id from supplier where agent_id = %s and short_name like %s',
                                     self.current_user.id, '%' + supplier_name + '%')
        else:
            supplier = self.db.query('select id from supplier where agent_id = %s', self.current_user.id)

        if supplier:
            shop_accounts = self.db.query('select account_id from supplier_shop where supplier_id in (%s)' %
                                          ','.join(['%s'] * len(supplier)), *[item.id for item in supplier])
            sp_account = self.db.query('select id from account where type = 1 and uid in (%s)' %
                                       ','.join(['%s'] * len(supplier)), *[sp.id for sp in supplier])
            accounts = [sh.account_id for sh in shop_accounts]
            accounts.extend([sp.id for sp in sp_account])
        else:
            accounts = []

        start_at = self.get_argument('start_at', '')
        end_at = self.get_argument('end_at', '')

        params = []
        if accounts:
            sql = 'select * from account_sequence where account_id in (%s) ' % ','.join(['%s'] * len(accounts))
            params.extend(accounts)

            if start_at:
                sql += 'and created_at >= %s '
                params.append(start_at)
            if end_at:
                sql += 'and created_at <= %s '
                params.append(end_at)
            sql += 'order by created_at desc'

        else:
            sql = 'select * from account_sequence where id < 0'

        sequence = Paginator(self, sql, params)

        self.render('supplier/sequence.html', sequence=sequence, supplier_name=supplier_name, start_at=start_at,
                    end_at=end_at)


class Goods(BaseHandler):
    @authenticated
    def get(self):
        suppliers = self.db.query('select id from supplier where agent_id = %s', self.current_user.id)
        sql = """select g.id gid, g.short_name, g.sales_price, s.short_name sname, g.sales_count
                 from goods g join supplier s on g.supplier_id = s.id
                 where g.deleted = 0 """
        params = []
        supplier_name = ''
        if suppliers:
            sql += 'and s.id in (%s)' % ','.join(['%s'] * len(suppliers))
            params = [supplier.id for supplier in suppliers]

            if 'supplier_name' in self.request.arguments:
                supplier_name = self.get_argument('supplier_name')
                sql += 'and s.short_name like %s'
                params.append('%' + supplier_name + '%')

            goods = Paginator(self, sql, params)
        else:
            sql += 'and g.id < 0'
            goods = Paginator(self, sql, params)

        self.render('supplier/goods.html', goods=goods, supplier_name=supplier_name)


class Detail(BaseHandler):
    @authenticated
    def get(self, sid):
        supplier = self.db.get('select * from supplier where id = %s', sid)
        self.render('supplier/detail.html', supplier=supplier)
