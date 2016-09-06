#-*- coding:utf-8 -*-
from . import BaseHandler, authenticated
from autumn.torn.paginator import Paginator
from autumn.torn.form import Form
from voluptuous import Schema
from tornado.httputil import url_concat
from autumn.goods import contract_url

list_schema = Schema({
    'pre_id': str,
    's_name': str,
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
        where p.city_id = a1.id and p.district_id = a2.id and p.agent_id = %s and state = 2'''
        params.append(self.current_user.id)
        if form.s_name.value:
            sql += ' and p.shop_name like %s'
            params.append('%'+form.s_name.value+'%')
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
        sql += ' order by pre_distribute_datetime desc'
        page = Paginator(self, sql, params)
        self.render('supplier/marked/list.html', page=page, form=form)


class Add(BaseHandler):
    @authenticated
    def get(self):
        sql = '''select p.*, a1.name as "city", a2.name as "district"
        from pool_supplier p, area1 a1, area1 a2
        where p.city_id = a1.id and p.district_id = a2.id and p.agent_id = %s and p.id = %s'''
        supplier = self.db.get(sql, self.current_user.id, self.get_argument('id'))
        params = {}
        if supplier.contract:
            contract_urls = generate_img_url(supplier.contract)
            params['contract_urls'] = contract_urls
        if supplier.certificate:
            certificate_urls = generate_img_url(supplier.certificate)
            params['certificate_urls'] = certificate_urls
        params['supplier'] = supplier
        self.render('supplier/submitted/add.html', **params)


class Edit(BaseHandler):
    @authenticated
    def post(self):
        form = Form(self.request.arguments, list_schema)
        remark = self.get_argument('remark').strip()
        if 100 >= len(remark) >= 5:   # 日志信息至少5个字符至多100个字符
            self.db.execute('''update pool_supplier set remark = concat(ifnull(remark,''), now(), ':  ', %s, ',')
            where agent_id = %s and id = %s''', self.get_argument('remark'), self.current_user.id,
            self.get_argument('id'))
        self.redirect(url_concat(self.reverse_url('supplier.marked.list'), {'status': form.status.value,
                      'city': form.city.value, 'district': form.district.value, 's_name': form.s_name.value,
                      'pre_id': self.get_argument('id')}))


class Delete(BaseHandler):
    @authenticated
    def post(self):
        form = Form(self.request.arguments, list_schema)
        self.db.execute('''update pool_supplier set agent_id=NULL, state=1, pre_distribute_datetime=NULL, remark=NULL
        where agent_id=%s and id=%s''', self.current_user.id, self.get_argument("id"))
        self.redirect(url_concat(self.reverse_url('supplier.marked.list'), {'status': form.status.value,
                      'city': form.city.value, 'district': form.district.value, 's_name': form.s_name.value}))

def generate_img_url(images):
    """把数据库的图片名如：/27/610/148/231323.jpg
    转化成URL如：http://.../contract/o/27/610/148/231323.jpg"""
    image_urls = []
    image_list = images.split(',')
    for image in image_list:
        image_urls.append(contract_url(image))
    return image_urls
