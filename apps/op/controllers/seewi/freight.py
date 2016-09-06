#-*- coding: utf-8 -*-

from .. import BaseHandler, require
import json


class Show(BaseHandler):
    @require()
    def get(self, eid):
        freight = self.db.query('select * from freight where deleted = 0 and supplier_id = 5 and express_id = %s', eid)
        name = self.db.get('select name from express_company where id = %s', eid).name

        self.render('seewi/freight_list.html', freight=freight, name=name, company_id=eid)


class Add(BaseHandler):
    @require('operator')
    def get(self, eid):
        express = self.db.get('select * from express_company where id = %s', eid)
        params = {
            'name': express.name,
            'company_id': eid,
            'action': u'新增'
        }

        self.render('seewi/freight.html', **params)

    @require('operator')
    def post(self, eid):
        self.db.execute('insert into freight(supplier_id, price, created_at, province, express_id) '
                        'values(5, %s, NOW(),%s, %s)', self.get_argument('price', 0), self.get_argument('province', ''),
                        eid)

        self.redirect(self.reverse_url('freight.list', eid))


class Edit(BaseHandler):
    @require('operator')
    def get(self, eid, fid):
        freight = self.db.get('select * from freight where id = %s', fid)
        express = self.db.get('select * from express_company where id = %s', eid)
        info = {
            'company_id': eid,
            'freight_id': fid,
            'name': express.name,
            'price': freight.price,
            'province': freight.province,
            'action': u'修改'
        }

        self.render('seewi/freight.html', **info)

    @require('operator')
    def post(self, eid, fid):
        self.db.execute('update freight set province = %s, price = %s where id = %s', self.get_argument('province', ''),
                        self.get_argument('price', 0), fid)

        self.redirect(self.reverse_url('freight.list', eid))


class Delete(BaseHandler):
    @require('operator')
    def post(self, eid):
        freight_id = self.get_argument('id')
        self.db.execute('update freight set deleted = 1 where id = %s', freight_id)

        self.redirect(self.reverse_url('freight.list', eid))
