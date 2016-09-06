# -*- coding: utf-8 -*-

from ... import BaseHandler, require
from datetime import date


class Pull(BaseHandler):
    @require()
    def get(self):
        last_update = self.db.get('select * from supplier_property where sp_id = %s and name = "wx_mem_update"',
                                  self.current_user.supplier_id)
        if not last_update:
            self.db.execute('insert into supplier_property(sp_id, name, value) values(%s, "wx_mem_update", %s)',
                            self.current_user.supplier_id, date.today())
            self.redis.lpush('q:wx:mem:update', self.current_user.supplier_id)
            self.write('ok')
        else:
            if last_update.value >= date.today().strftime('%Y-%m-%d'):
                self.write('error')
            else:
                self.db.execute('update supplier_property set value = %s where sp_id = %s and name = "wx_mem_update"',
                                date.today(), self.current_user.supplier_id)
                self.redis.lpush('q:wx:mem:update', self.current_user.supplier_id)
                self.write('ok')