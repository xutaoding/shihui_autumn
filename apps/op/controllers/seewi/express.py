#-*- coding: utf-8 -*-

from .. import BaseHandler, require
from autumn.torn.form import Form
from voluptuous import Schema

express = Schema({
    'id': str,
    'code': str,
    'name': str,
    'mapping': str,
    'action': str
}, extra=True)


class ExpressShow(BaseHandler):
    @require()
    def get(self):
        express = self.db.query('select * from express_company ')

        self.render('seewi/express_list.html', express=express)


class ExpressAdd(BaseHandler):
    @require('operator')
    def get(self):
        form = Form(self.request.arguments, express)
        form.action.value = 'add'

        self.render('seewi/express.html', form=form)

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, express)
        form.action.value = 'add'

        self.db.execute('insert into express_company(code, name, distributor_mapping) values(%s, %s, %s)',
                        form.code.value, form.name.value, form.mapping.value)

        self.redirect(self.reverse_url('express.list'))


class ExpressEdit(BaseHandler):
    @require('operator')
    def get(self, eid):
        express_info = self.db.get('select code, name, distributor_mapping mapping from express_company where id = %s',
                                   eid)
        form = Form(express_info, express)
        form.action.value = 'edit'
        form.id.value = eid

        self.render('seewi/express.html', form=form)

    @require('operator')
    def post(self, eid):
        form = Form(self.request.arguments, express)
        form.action.value = 'edit'
        form.id.value = eid

        self.db.execute('update express_company set code = %s, name = %s, distributor_mapping = %s where id = %s',
                        form.code.value, form.name.value, form.mapping.value)

        self.redirect(self.reverse_url('express.list'))


class ExpressDelete(BaseHandler):
    @require('operator')
    def post(self):
        pass