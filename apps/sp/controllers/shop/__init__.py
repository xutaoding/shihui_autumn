# -*- coding: utf-8 -*-

from .. import BaseHandler, require
from autumn.torn.paginator import Paginator


class Show(BaseHandler):
    @require()
    def get(self):
        user = self.db.get('select shop_id, supplier_id from supplier_user where id = %s and deleted = 0 '
                           , self.current_user.id)
        if not user.shop_id:
            sql = 'select * from supplier_shop where supplier_id = %s and deleted = 0'
            params = [user.supplier_id]
        else:
            sql = 'select * from supplier_shop where id = %s and deleted = 0'
            params = [user.shop_id]
        page = Paginator(self, sql, params)

        self.render('shop/show.html', page=page)