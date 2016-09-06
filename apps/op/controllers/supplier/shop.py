# -*- coding: utf-8 -*-

from voluptuous import Schema, Length, Any

from autumn.torn.form import Form
from .. import BaseHandler
from .. import require
from autumn.torn.paginator import Paginator


shop_schema = Schema({
    'supplier':         str,
    'name':             Length(min=1),
    'address':          Length(min=1),
    'latitude':         str,
    'longitude':        str,
    'manager_name':     str,
    'manager_mobile':   str,
    'phone':            str,
    'traffic_info':     str,
    'action':           Any('edit', 'add'),
    'id':               str,
    'supplier_id':      str,
    'area_id':          str,
    'city_id':          str,
    'district_id':      str,
    'verify_phones':    str,
}, extra=True)


class Add(BaseHandler):
    @require('operator')
    def get(self):
        form = Form(self.request.arguments, shop_schema)
        form.action.value = 'add'
        supplier = self.db.get('select * from supplier where id=%s', form.supplier_id.value)

        self.render('supplier/shop/shop.html', supplier=supplier, form=form, error='')

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, shop_schema)
        supplier_id = form.supplier_id.value

        if not form.validate():
            return self.render('supplier/shop/shop.html', form=form, error='error')

        supplier = self.db.get('select short_name from supplier where id = %s', supplier_id)

        # 新建账户
        shop_account_id = self.db.execute('insert into account set uid=0, type=2, '
                                          'created_at=NOW(), amount=0')

        fields = dict([(key, getattr(form, key).value.strip()) for key in
                       ['name', 'area_id', 'address', 'verify_phones', 'latitude', 'longitude', 'manager_name',
                        'manager_mobile', 'phone', 'traffic_info']])
        fields.update({
            'supplier_id': supplier_id,
            'account_id': shop_account_id,
            'supplier_name': supplier.short_name,
        })
        sql = 'insert into supplier_shop set %s' % ','.join([key + '=%s' for key in fields.keys()]) + ',created_at = NOW()'
        # 新建商户门店
        shop_id = self.db.execute(sql, *fields.values())

        #更新店铺账户uid
        self.db.execute('update account set uid=%s where id= %s', shop_id, shop_account_id)

        self.redirect(self.reverse_url('supplier.shop', supplier_id))


class Edit(BaseHandler):
    @require('operator')
    def get(self):
        shop_id = self.get_argument('id')
        shop = self.db.get('select * from supplier_shop where id = %s', shop_id)
        supplier = self.db.get('select * from supplier where id = %s', shop.supplier_id)
        form = Form(shop, shop_schema)
        form.action.value = 'edit'
        form.area_id.value = shop.area_id

        self.render('supplier/shop/shop.html', supplier=supplier, form=form, error='')

    @require('operator')
    def post(self):
        shop_id = self.get_argument('id')
        form = Form(self.request.arguments, shop_schema)
        supplier_shop = self.db.get('select * from supplier_shop where id = %s', shop_id)
        supplier_id = supplier_shop.supplier_id

        if not form.validate():
            return self.render('supplier/shop/shop.html', form=form, error='error')

        fields = dict([(key, getattr(form, key).value.strip()) for key in
                       ['name', 'area_id', 'address', 'verify_phones', 'latitude', 'longitude', 'manager_name',
                        'manager_mobile', 'phone', 'traffic_info']])
        sql = 'update supplier_shop set ' + ','.join([key + '=%s' for key in fields.keys()]) + 'where id=%s'
        self.db.execute(sql, *(fields.values()+[shop_id]))
        self.redirect(self.reverse_url('supplier.shop', supplier_id))


class List(BaseHandler):
    @require()
    def get(self, supplier_id):
        sql = 'select ss.* from supplier_shop ss where ss.supplier_id = %s and ss.deleted =0 order by id desc'
        page = Paginator(self, sql, [supplier_id])
        supplier = self.db.get('select * from supplier where id=%s', supplier_id)

        self.render('supplier/shop/list.html', page=page, supplier=supplier)


class Detail(BaseHandler):
    @require()
    def get(self, shop_id):
        """ 显示商户门店详情 """

        # 门店信息
        shop = self.db.get('select ss.*,a.name area from supplier_shop ss,area a '
                           'where ss.area_id = a.id and ss.id = %s', shop_id)
        city_id = shop.area_id[0:len(shop.area_id) - 5]

        district_id = shop.area_id[0:len(shop.area_id)-3]
        city = self.db.get('select name from area where id = %s', city_id)
        district = self.db.get('select name from area where id = %s', district_id)
        shop['city'] = city.name
        shop['district'] = district.name
        supplier = self.db.get('select * from supplier where id=%s', shop.supplier_id)

        users = self.db.query('select su.* from supplier_user su where deleted=0 and supplier_id=%s '
                              'and shop_id in (0, %s)', shop.supplier_id, shop_id)
        accounts = self.db.query('select * from withdraw_account where deleted=0 '
                                 'and ((type="SUPPLIER" and uid=%s) or (type="SUPPLIER_SHOP" and uid=%s))',
                                 shop.supplier_id, shop_id)

        self.render('supplier/shop/detail.html', shop=shop, supplier=supplier, users=users, accounts=accounts)


class Delete(BaseHandler):
    @require('operator')
    def post(self):
        """删除商户门店"""
        sp_id = self.get_argument('sp_id', '')
        shop_id = self.get_argument('shop_id', '')
        if not sp_id or not shop_id:
            self.write({'error': '参数不正确'})
            return

        shop = self.db.get('select id from supplier_shop where deleted=0 and supplier_id=%s and id=%s',
                           sp_id, shop_id)
        if not shop:
            self.write({'error': '没有找到对应门店'})
            return

        try:
            self.db.execute('update supplier_shop set deleted=1 where supplier_id=%s and id=%s', sp_id, shop_id)
            self.write({'ok': 'ok'})
            return
        except:
            self.write({'error': '删除失败， 请重试'})
            return

