# -*- coding: utf-8 -*-


from ..import BaseHandler
from ..import require
from decimal import Decimal
import itertools
from tornado.web import HTTPError
from voluptuous import Schema, All, Coerce, Length, Any, Range
from autumn.goods import img_url
from autumn.torn.form import Form, EmptyList, Decode, Datetime, EmptyNone, Strip, Unique, ListCoerce
from autumn.torn.paginator import Paginator
from autumn.utils import EmptyDict, json_dumps
from autumn.utils.dt import ceiling
import json
import logging


class List(BaseHandler):
    @require()
    def get(self):
        form = Form(self.request.arguments, list_schema)

        sql = """select g.id, g.short_name, g.face_value, g.sales_price, g.created_by,
        g.purchase_price, g.stock, g.status, gds.dsid, gp.name gpname
        from goods g left join
        (select goods_id, group_concat(concat(gds.distributor_shop_id, '-',
        case when gds.distributor_shop_id=7 then extra else gds.distributor_goods_id end)) dsid
        from goods_distributor_shop gds where status='ON_SALE' group by goods_id) gds
        on g.id=gds.goods_id
        left join goods_property gp on g.id = gp.goods_id and gp.name = "is_wx_goods" and gp.value = "1"
        where g.deleted=0 and gp.name is null and g.supplier_id = %s
         """

        params = [self.current_user.supplier_id]

        if form.goods.value:
            sql += 'and g.short_name like %s '
            params.append('%' + form.goods.value + '%')

        if form.status.value:
            sql += 'and g.status = %s '
            params.append(form.status.value)

        sql += 'order by g.id desc'

        page = Paginator(self, sql, params)
        self.render('goods/list.html', page=page, form=form)


class Add(BaseHandler):
    """ 商品添加 """
    @require('manager')
    def get(self):
        form = Form(self.request.arguments, add_schema)
        form.shops['value'] = []
        supplier_shops = self.db.query('select ss.* from supplier_shop ss where ss.supplier_id=%s',
                                       self.current_user.supplier_id)
        form.img_paths['value'] = dict()
        self.render('goods/add.html', form=form, supplier_shops=supplier_shops, error='', action='add', img_url=img_url)

    @require('manager')
    def post(self):
        form = Form(self.request.arguments, add_schema)
        img_paths = dict()
        for key in self.request.arguments:
            if key.startswith('var_img_path_'):
                v = self.request.arguments[key][0]
                if v:
                    img_paths[key[key.rindex('_')+1:]] = v

        if not form.validate():
            supplier_shops = self.db.query('select ss.* from supplier_shop ss where ss.supplier_id=%s and ss.deleted=0',
                                           self.current_user.supplier_id)
            form.img_paths['value'] = img_paths
            logging.error(json_dumps(form.errors))
            return self.render('goods/add.html', form=form, error='error', action='add', supplier_shops=supplier_shops,
                               img_url=img_url)

        fields = ('type', 'generate_type', 'expire_at', 'category_id', 'name', 'short_name', 'sms_name',
                  'face_value', 'sales_price', 'purchase_price', 'stock', 'virtual_sales_count', 'img_path', 'all_shop',
                  'detail', 'tips', 'supplier_intro', 'on_sale_at', 'off_sale_at', 'postage')

        goods_sql = """
            insert into goods(%s, supplier_id, created_by, img_paths, created_at, status)
            values (%s, %%s, %%s, %%s, NOW(), "PREPARE")""" % (','.join(fields), ','.join(['%s']*len(fields)))

        form.expire_at['value'] = ceiling(form.expire_at.value, today=True) if form.expire_at.value else None
        form.off_sale_at['value'] = ceiling(form.off_sale_at.value, today=True) if form.off_sale_at.value else None
        params = [form.arguments[field]['value'] for field in fields]

        params.extend([self.current_user.supplier_id, self.current_user.name, json_dumps(img_paths)])

        goods_id = self.db.execute_lastrowid(goods_sql, * params)

        self.db.execute('insert into journal(created_at, type, created_by, message, iid) '
                        'values(NOW(), 3, %s, %s, %s)', self.current_user.name, '商户新增了商品', goods_id)

        # 批量插入商品属性
        if form.properties.value:
            insert_properties(self.db, form.properties.value, goods_id)

        # 批量插入关联的门店
        if not form.all_shop.value:
            if form.shops.value:
                insert_shops(self.db, form.shops.value, goods_id)

        # 批量插入分销店铺佣金
        insert_ratios(self.db, goods_id)

        self.redirect(self.reverse_url('goods.list'))


class Edit(BaseHandler):
    """ 商品编辑 """
    @require('manager')
    def get(self):
        goods_id = self.get_argument('id')
        goods_info, shops, properties, img = get_goods_info(self.db, goods_id)

        if goods_info.supplier_id != self.current_user.supplier_id:
            raise HTTPError(403)

        if goods_info.status not in ['PREPARE', 'REJECT']:
            raise HTTPError(403)

        form = Form(goods_info, add_schema)
        form.properties.value = properties
        form.shops['value'] = shops
        form.img_paths['value'] = dict() if not form.img_paths.value else json.loads(form.img_paths.value)

        supplier_shops = self.db.query('select ss.* from supplier_shop ss where ss.supplier_id=%s and ss.deleted=0',
                                       self.current_user.supplier_id)
        self.render('goods/add.html', form=form, error='', action='edit', img_url=img_url,
                    supplier_shops=supplier_shops)

    @require('manager')
    def post(self):
        form = Form(self.request.arguments, add_schema)
        goods_info, shops, properties, img = get_goods_info(self.db, form.id.value)

        if goods_info.supplier_id != self.current_user.supplier_id:
            raise HTTPError(403)

        if goods_info.status not in ['PREPARE', 'REJECT']:
            raise HTTPError(403)

        # 为了下面的 validate 成功 这里必须填入数据
        form.arguments.update({'generate_type': EmptyDict({'value': goods_info.generate_type})})
        img_paths = dict()
        for key in self.request.arguments:
            if key.startswith('var_img_path_'):
                v = self.request.arguments[key][0]
                if v:
                    img_paths[key[key.rindex('_')+1:]] = v
        form.img_paths['value'] = json_dumps(img_paths)
        if not form.validate():
            form.properties.value = properties
            form.shops['value'] = shops
            form.img_paths['value'] = img_paths

            supplier_shops = self.db.query('select ss.* from supplier_shop ss where ss.supplier_id=%s and ss.deleted=0',
                                           self.current_user.supplier_id)
            logging.error(json_dumps(form.errors))
            self.render('goods/add.html', form=form, error='', action='edit', supplier_shops=supplier_shops,
                        img_url=img_url)

        fields = ('type', 'generate_type', 'expire_at', 'category_id', 'name', 'short_name', 'sms_name', 'face_value',
                  'sales_price', 'purchase_price', 'stock', 'virtual_sales_count', 'img_path', 'detail', 'tips',
                  'supplier_intro', 'all_shop', 'on_sale_at', 'off_sale_at', 'img_paths', 'postage')

        update_sql = 'update goods set %s where id=%%s' % ','.join([field + '=%s' for field in fields])

        form.expire_at['value'] = ceiling(form.expire_at.value, today=True) if form.expire_at.value else None
        form.off_sale_at['value'] = ceiling(form.off_sale_at.value, today=True) if form.off_sale_at.value else None
        params = [form.arguments[field]['value'] for field in fields]
        params.append(form.id.value)

        self.db.execute(update_sql, *params)

        self.db.execute('insert into journal(created_at, type, created_by, message, iid) '
                        'values(NOW(), 3, %s, %s, %s)', self.current_user.name, '商户修改了商品', form.id.value)

        # 批量更新商品属性
        self.db.execute('delete from goods_property where goods_id=%s and name in ("gift_card", "hidden", "ktv")',
                        form.id.value)
        if form.properties.value:
            insert_properties(self.db, form.properties.value, form.id.value)

        # 批量更新关联门店
        self.db.execute('delete from goods_supplier_shop where goods_id=%s', form.id.value)
        if not form.all_shop.value:
            if form.shops.value:
                insert_shops(self.db, form.shops.value, form.id.value)

        self.redirect(self.reverse_url('goods.list'))


class GoodsDetail(BaseHandler):
    """ 商品详情 """
    @require()
    def get(self, goods_id):
        goods = self.db.get('select g.*, gc.name category from goods g, goods_category gc '
                            'where g.category_id = gc.id and g.id =%s and g.supplier_id=%s',
                            goods_id, self.current_user.supplier_id)
        if not goods:
            raise HTTPError(404)

        shops = self.db.query(
            'select ss.* from supplier_shop ss,goods g where ss.supplier_id=g.supplier_id and g.id=%s and ss.deleted=0 '
            'and (g.all_shop=1 or ss.id in (select supplier_shop_id from goods_supplier_shop where goods_id=%s) ) ',
            goods_id, goods_id
        )
        if goods.img_path:
            imgurl = img_url(goods.img_path)
        else:
            imgurl = 'http://img.uhcdn.com/images/autumn/default.png'

        self.render('goods/detail.html', goods=goods, shops=shops, img_url=imgurl)


class Delete(BaseHandler):
    """商品删除"""
    @require('manager')
    def post(self):
        goods_id = self.get_argument('goods_id', 0)
        self.db.execute('update goods set deleted = 1 where status="PREPARE" and id = %s and supplier_id=%s',
                        goods_id, self.current_user.supplier_id)

        self.redirect(self.reverse_url('goods.list'))


class Apply(BaseHandler):
    """商品提交审核"""
    @require('manager')
    def post(self):
        status = {'apply': 'PENDING', 'undo': 'PREPARE'}.get(self.get_argument('action'), '')
        if status:
            goods_id = self.get_argument('goods_id', 0)
            self.db.execute('update goods set status = %s where id = %s and supplier_id=%s',
                            status, goods_id, self.current_user.supplier_id)
            if status == 'PENDING':
                message = '没有注明分销商' if not self.get_argument('distr') else '请发布在以下分销商: ' + self.get_argument('distr').encode('utf-8')
                message += '  备注：' + self.get_argument('remark').encode('utf-8') if not self.get_argument('remark') else ''
            elif status == 'PREPARE':
                message = self.current_user.name + '取消了该商品审核'

            self.db.execute('insert into journal(created_at, type, created_by, message, iid) '
                            'values(NOW(), 3, %s, %s, %s)', self.current_user.name, message, goods_id)

        self.redirect(self.reverse_url('goods.list'))


def insert_properties(db, properties, goods_id, value=1):
    prop_sql = 'insert into goods_property(goods_id, name, value) values %s' % ','.join(
        ['(%s,%s,%s)']*len(properties))
    prop_params = list(itertools.chain(*[[goods_id, prop, value] for prop in properties]))
    db.execute(prop_sql, *prop_params)


def insert_shops(db, shops, goods_id):
    shop_sql = 'insert into goods_supplier_shop(goods_id, supplier_shop_id) values %s' % ','.join(
        ['(%s,%s)']*len(shops))
    shop_params = list(itertools.chain(*[[goods_id, shop_id] for shop_id in shops]))
    db.execute(shop_sql, *shop_params)


def get_goods_info(db, goods_id):
    goods_info = db.get('select * from goods where id = %s', goods_id)

    shops = [item.id for item in db.query('select ss.id from supplier_shop ss, goods_supplier_shop gss '
                                          'where ss.id=gss.supplier_shop_id and gss.goods_id=%s', goods_id)]
    properties = [d.name for d in db.query('select name from goods_property where goods_id = %s', goods_id)]
    return goods_info, shops, properties, img_url(goods_info.img_path)


def insert_ratios(db, goods_id):
    distributor_commission = {
        '7':	        2.00,
        '9':	        2.00,
        '10':       	3.00,
        '14':	        3.00,
        '27':       	1.25,
        '28':	        2.50,
        '29':       	2.50,
        '30':       	2.50,
        '34':       	1.00,
        '38':       	2.50,
    }
    zip_params = [(key, value, goods_id) for key, value in distributor_commission.iteritems()]
    ratio_params = [i for item in zip_params for i in item]
    ratio_sql = 'insert into goods_distributor_commission(distr_shop_id, ratio, goods_id) values %s' % ','.join(
        ['(%s,%s,%s)']*len(distributor_commission))
    db.execute(ratio_sql, *ratio_params)

list_schema = Schema(
    {
        'supplier': str,
        'goods': str,
        'status': str,
    }, extra=True)

add_schema = Schema(
    {
        'type':             Any('E', 'R'),
        'generate_type':    Any('GENERATE', 'IMPORT'),
        'expire_at':        Any(Datetime(), EmptyNone()),
        'on_sale_at':       Datetime(),
        'off_sale_at':      Datetime(),
        'category_id':      Coerce(int),
        'properties':       All(EmptyList(), Unique()),
        'name':             All(Decode(), Strip(), Length(min=1, max=300)),
        'sms_name':         All(Decode(), Length(min=1, max=50)),
        'short_name':       All(Decode(), Length(min=1, max=12)),
        'face_value':       All(Coerce(Decimal), Range(min=Decimal('0.1'))),
        'sales_price':      All(Coerce(Decimal), Range(min=Decimal('0.1'))),
        'purchase_price':   All(Coerce(Decimal), Range(min=Decimal('0.1'))),
        'postage':          Any(All(Coerce(Decimal), Range(min=Decimal('0.0'))), EmptyNone()),
        'stock':            All(Coerce(int), Range(min=1)),
        'virtual_sales_count': Coerce(int),
        'all_shop':         Coerce(int),
        'shops':            All(EmptyList(), Unique(), ListCoerce(int)),
        'img_path':         str,
        'img_paths':        str,
        'detail':           str,
        'tips':             str,
        'supplier_intro':   str,
        'id':               str,
    }, extra=True)
