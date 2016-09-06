#-*- coding:utf-8 -*-

from . import BaseHandler, authenticated
from tornado.httputil import url_concat
from autumn.torn.paginator import Paginator
from autumn.torn.form import Form
from voluptuous import Schema


list_schema = Schema({
    'brand': str,
    'city': str,
    'district': str,
    'status': str,
}, extra=True)


class List(BaseHandler):
    @authenticated
    def get(self):
        form = Form(self.request.arguments, list_schema)
        params = []
        sql = '''select p.*, a1.name as "city", a2.name as "district"
        from pool_supplier p, area1 a1, area1 a2
        where p.city_id = a1.id and p.district_id = a2.id and p.state = 1'''
        if form.brand.value:
            sql += ' and p.brand_name like %s'
            params.append('%' + form.brand.value + '%')
        if form.city.value:
            sql += ' and a1.type = %s and a1.name like %s '
            params.append('city')
            params.append('%'+form.city.value+'%')
        if form.district.value:
            sql += ' and a2.type = %s and a2.name like %s'
            params.append('district')
            params.append('%'+form.district.value+'%')
        if form.status.value:
            sql += ' and p.category = %s'
            params.append(form.status.value)
        page = Paginator(self, sql, params)
        supplier_count = self.db.get('select count(*) as count from pool_supplier where agent_id = %s',
                                     self.current_user.id).count
        max_select = self.current_user.supplier_limit - supplier_count
        self.render('supplier/pool/list.html', page=page, form=form, max=max_select)

    @authenticated
    def post(self):
        form = Form(self.request.arguments, list_schema)
        supplier_count = self.db.get('select count(*) as count from pool_supplier where agent_id = %s',
                                     self.current_user.id).count
        brand_list = self.get_argument('brand_list').split(',')
        if supplier_count + len(brand_list) <= self.current_user.supplier_limit:  # 检查代理商挑选商户数量是否超过限制
            sql = """ update pool_supplier set agent_id = %s, pre_distribute_datetime = NOW(), state = 2
            where id in (%s) """ % (self.current_user.id, ','.join(['%s']*len(brand_list)))
            self.db.execute(sql, *brand_list)
        self.redirect(url_concat(self.reverse_url('supplier.pool.list'), {'status': form.status.value,
                      'city': form.city.value, 'district': form.district.value, 'brand': form.brand.value}))