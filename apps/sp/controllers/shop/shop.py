# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from voluptuous import Schema
from autumn.torn.form import Form
from autumn.utils import json_dumps

add_edit_list = Schema({
    'area_id': str,
    'name': str,
    'address': str,
    'telephone': str,
    'verify': str,
    'manager_name': str,
    'manager_mobile': str,
    'traffic': str,
    'longitude': str,
    'latitude': str,
    'action': str,
}, extra=True)


class Add(BaseHandler):
    @require('manager')
    def get(self):
        form = Form(self.request.arguments, add_edit_list)
        form.action.value = 'add'
        city_list = self.db.query('select * from area where type = "CITY"')
        self.render('shop/add_edit.html', form=form, city_list=city_list)

    @require('manager')
    def post(self):
        form = Form(self.request.arguments, add_edit_list)
        form.action.value = 'add'
        if not form.validate():
            return self.render('shop/add_edit.html', form=form)

        # 新建账户
        shop_account_id = self.db.execute('insert into account(uid, type, created_at, amount) '
                                          'values(0, 2, NOW(), 0)')

        shop_id = self.db.execute(
            'insert into supplier_shop(supplier_id, name, area_id, address, account_id, manager_mobile, manager_name, '
            'phone, verify_phones, traffic_info, created_at, created_by, supplier_name, longitude, latitude) '
            'values(%s, %s, %s,  %s, %s,%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s)',
            self.current_user.supplier_id, form.name.value, form.area_id.value, form.address.value, shop_account_id,
            form.manager_mobile.value, form.manager_name.value, form.telephone.value, form.verify.value,
            form.traffic.value, self.current_user.name, self.current_user.supplier_short_name,
            form.longitude.value, form.latitude.value)
        self.db.execute('update account set uid = %s where id = %s', shop_id, shop_account_id)

        self.redirect(self.reverse_url('shop.show'))


class Edit(BaseHandler):
    @require('manager')
    def get(self, shop_id):
        shop = self.db.get('select * from supplier_shop where id = %s', shop_id)
        form = Form(shop, add_edit_list)
        form.telephone.value = shop.phone
        form.verify.value = shop.verify_phones
        form.traffic.value = shop.traffic_info
        form.action.value = 'edit'
        #查找出城市，区域，商圈的ID
        area_id = self.db.get('select area_id from supplier_shop where id = %s', shop_id)['area_id']
        district_id = self.db.get('select parent_id from area where id = %s', area_id)['parent_id']
        city_id = self.db.get('select parent_id from area where id = %s', district_id)['parent_id']

        city_list = self.db.query('select * from area where type = "CITY"')
        district_list = self.db.query('select * from area where type = "DISTRICT" and parent_id = %s', city_id)
        area_list = self.db.query('select * from area where type = "AREA" and parent_id = %s', district_id)

        self.render('shop/add_edit.html', form=form, area_id=area_id, district_id=district_id, city_id=city_id,
                    city_list=city_list, district_list=district_list, area_list=area_list, shop_id=shop_id)

    @require('manager')
    def post(self, shop_id):
        form = Form(self.request.arguments, add_edit_list)
        form.action.value = 'edit'
        if not form.validate():
            return self.redirect(self.reverse_url('shop.edit', shop_id))

        self.db.execute('update supplier_shop set area_id = %s, name = %s, address = %s, manager_mobile = %s, '
                        'manager_name = %s, phone = %s, verify_phones = %s, traffic_info = %s, longitude = %s, '
                        'latitude = %s where id = %s', form.area_id.value, form.name.value, form.address.value,
                        form.manager_mobile.value, form.manager_name.value, form.telephone.value, form.verify.value,
                        form.traffic.value, form.longitude.value, form.latitude.value, shop_id)

        self.redirect(self.reverse_url('shop.show'))


class Delete(BaseHandler):
    @require('manager')
    def post(self):
        shop_id = self.get_argument('shop_id')
        self.db.execute('update supplier_shop set deleted = 1 where id = %s', shop_id)

        self.redirect(self.reverse_url('shop.show'))


class DistrictAjax(BaseHandler):
    @require('manager')
    def post(self):
        city_id = self.get_argument('city_id')
        district_list = self.db.query('select * from area where type="DISTRICT" and parent_id = %s', city_id)

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(district_list))


class AreaAjax(BaseHandler):
    @require('manager')
    def post(self):
        district_id = self.get_argument('district_id')
        area_list = self.db.query('select * from area where type="AREA" and parent_id = %s', district_id)

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(area_list))