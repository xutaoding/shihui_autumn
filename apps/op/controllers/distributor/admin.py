# -*- coding: utf-8 -*-

from tornado.httputil import url_concat
from voluptuous import Schema, Length, Any

from autumn.torn.form import Form
from .. import BaseHandler
from .. import require
from autumn.torn.paginator import Paginator

distributor_schema = Schema({
    'name': Length(min=1),
    'remark': str,
    'id': str,
    'action': Any('edit', 'add'),
}, extra=True)


class Add(BaseHandler):
    @require('operator')
    def get(self):
        form = Form(self.request.arguments, distributor_schema)
        form.action.value = 'add'

        self.render('distributor/distributor.html', form=form, error='')

    @require('developer', 'operator')
    def post(self):
        form = Form(self.request.arguments, distributor_schema)

        if not form.validate():
            return self.render('distributor/distributor.html', form=form, error='error')

        self.db.execute('insert into distributor (name,remark,created_at,created_by) values (%s,%s,now(),%s)',
                        form.name.value.strip(), form.remark.value.strip(),
                        self.current_user.name)

        self.redirect(url_concat(self.reverse_url('distributor.show_list'), {'id': form.id.value.strip()}))


class Edit(BaseHandler):
    @require('operator')
    def get(self):
        distributor = self.db.get('select id, name,remark from distributor where id = %s', self.get_argument('id'))
        form = Form(distributor, distributor_schema)
        form.action.value = 'edit'

        self.render('distributor/distributor.html', form=form, error='')

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, distributor_schema)

        if not form.validate():
            return self.render('distributor/distributor.html', form=form, error='error')

        self.db.execute('update distributor set name = %s,remark = %s where id = %s',
                        form.name.value.strip(), form.remark.value.strip(), form.id.value.strip())

        self.redirect(url_concat(self.reverse_url('distributor.show_list'), {'id': form.id.value.strip()}))


class List(BaseHandler):
    @require()
    def get(self):
        sql = """select d.*,(select count(1) from distributor_shop ds where ds.deleted=0 and ds.distributor_id=d.id) shop_count
                 from distributor d where 1=1 """

        form = Form(self.request.arguments, distributor_schema)
        params = []
        distributor_id = self.get_argument('id', '')

        if distributor_id:
            sql += 'and d.id = %s '
            params.append(distributor_id)
        if form.name.value:
            sql += 'and d.name like %s '
            params.append('%' + form.name.value + '%')

        sql += 'order by d.id desc'
        page = Paginator(self, sql, params)
        self.render('distributor/list.html', page=page, form=form)



