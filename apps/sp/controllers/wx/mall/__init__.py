# -*- coding: utf-8 -*-

from ... import BaseHandler, require
import json
import logging
import itertools
from tornado.web import HTTPError
from autumn.torn.paginator import Paginator
from autumn.utils import json_hook, json_dumps, EmptyDict
from autumn.goods import img_url
from autumn.utils import PropDict
from voluptuous import Schema, All, Coerce, Length, Any, Range
from autumn.torn.form import Form, EmptyList, Decode, Datetime, EmptyNone, Unique, ListCoerce
from decimal import Decimal
from datetime import datetime
from autumn.utils.dt import ceiling
from tornado.options import options


class Cover(BaseHandler):
    @require()
    def get(self):
        cover = self.db.get('select * from supplier_property where name = "wx_mall_cover" and sp_id = %s',
                            self.current_user.supplier_id)
        if cover:
            cover = json.loads(cover.value, object_hook=json_hook)
        else:
            cover = PropDict()

        self.render('wx/mall/show.html', cover=cover, img_url=img_url)


class Edit(BaseHandler):
    @require()
    def get(self):
        cover = self.db.get('select * from supplier_property where name = "wx_mall_cover" and sp_id = %s',
                            self.current_user.supplier_id)
        if cover:
            cover = json.loads(cover.value, object_hook=json_hook)
        else:
            cover = PropDict()

        self.render('wx/mall/cover.html', cover=cover, img_url=img_url)

    @require()
    def post(self):
        sp_id = self.current_user.supplier_id
        self.db.execute('delete from supplier_property where sp_id=%s and name="wx_mall_cover"', sp_id)
        self.db.execute('insert into supplier_property(sp_id, name, value) values (%s, "wx_mall_cover", %s)',
                        sp_id, json_dumps({'pic': self.get_argument('pic'),
                                           'title': self.get_argument('title'),
                                           'desc': self.get_argument('desc')}))

        self.redirect(self.reverse_url('wx.mall.cover'))


class WxGoods(BaseHandler):
    """微信商品列表"""
    @require()
    def get(self):
        form = Form(self.request.arguments, list_schema)

        sql = """select g.id, g.short_name, g.face_value, g.sales_price, g.created_by, g.purchase_price, g.rank,
                 g.stock, g.status, g.expire_at, gp2.value as 'on_sale', g.on_sale_at, g.off_sale_at
                 from goods g, goods_property gp, goods_property gp2 where g.id = gp.goods_id and g.deleted = 0
                 and gp.name = "is_wx_goods" and gp.value = 1 and gp2.goods_id=g.id and gp2.name="is_wx_on_sale"
                 and g.supplier_id = %s """

        params = [self.current_user.supplier_id]
        if form.goods.value:
            sql += 'and g.short_name like %s '
            params.append('%' + form.goods.value + '%')

        if form.status.value:
            sql += 'and gp2.value = %s '
            params.append(form.status.value)

        sql += 'order by g.id desc'

        page = Paginator(self, sql, params)

        self.render('wx/mall/list.html', page=page, form=form, now=datetime.now())


class WxGoodsAdd(BaseHandler):
    """微商城商品添加"""
    @require()
    def get(self):
        form = Form(self.request.arguments, add_schema)
        form.shops['value'] = []
        supplier_shops = self.db.query('select ss.* from supplier_shop ss where ss.supplier_id=%s',
                                       self.current_user.supplier_id)
        form.img_paths['value'] = dict()
        self.render('wx/mall/goods_add.html', form=form, supplier_shops=supplier_shops,
                    error='', action='add', img_url=img_url)

    @require()
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
            return self.render('wx/mall/goods_add.html', form=form, error='error', action='add', supplier_shops=supplier_shops,
                               img_url=img_url)
        # 获取微信商品手续费
        commission = self.db.get('select value from supplier_property where sp_id=%s and name="wx_commission"',
                                 self.current_user.supplier_id)
        if not commission:
            rate = Decimal((100 - options.wx_min_commission)/100.0)
        else:
            rate = Decimal((100 - int(commission.value))/100.0)
        # 更新结算价
        form.arguments['purchase_price']['value'] = form.arguments['sales_price']['value'] * rate

        fields = ('type', 'generate_type', 'expire_at', 'category_id', 'short_name', 'sms_name',
                  'max_buy', 'on_sale_at', 'off_sale_at', 'face_value', 'sales_price', 'purchase_price',
                  'stock', 'img_path', 'all_shop', 'detail',  'postage')

        goods_sql = """
            insert into goods(%s, supplier_id, created_by, img_paths, created_at, status, name)
            values (%s, %%s, %%s, %%s, NOW(), "PREPARE", "")""" % (','.join(fields), ','.join(['%s']*len(fields)))

        form.expire_at['value'] = ceiling(form.expire_at.value, today=True) if form.expire_at.value else None
        form.on_sale_at['value'] = form.on_sale_at.value if form.off_sale_at.value else None
        form.off_sale_at['value'] = ceiling(form.off_sale_at.value, today=True) if form.off_sale_at.value else None
        params = [form.arguments[field]['value'] for field in fields]

        params.extend([self.current_user.supplier_id, self.current_user.name, json_dumps(img_paths)])

        goods_id = self.db.execute_lastrowid(goods_sql, * params)

        self.db.execute('insert into journal(created_at, type, created_by, message, iid) '
                        'values(NOW(), 3, %s, %s, %s)', self.current_user.name, '商户新增了微商城商品', goods_id)

        # 批量插入关联的门店
        if not form.all_shop.value:
            if form.shops.value:
                insert_shops(self.db, form.shops.value, goods_id)

        # 插入微信商品特有属性
        self.db.execute('insert into goods_property (goods_id, name, value) values '
                        '(%s, "is_wx_goods", %s)', goods_id, "1")
        self.db.execute('insert into goods_property (goods_id, name, value) values '
                        '(%s, "is_wx_on_sale", %s)', goods_id, "0")

        self.redirect(self.reverse_url('wx.goods.list'))


class WxGoodsEdit(BaseHandler):
    """微商城商品编辑"""
    @require()
    def get(self):
        goods_id = self.get_argument('goods_id')
        goods_info, shops, properties, img = get_goods_info(self.db, goods_id)

        if goods_info.supplier_id != self.current_user.supplier_id:
            raise HTTPError(403)

        form = Form(goods_info, add_schema)
        form.shops['value'] = shops
        form.img_paths['value'] = dict() if not form.img_paths.value else json.loads(form.img_paths.value)

        supplier_shops = self.db.query('select ss.* from supplier_shop ss where ss.supplier_id=%s and ss.deleted=0',
                                       self.current_user.supplier_id)
        self.render('wx/mall/goods_add.html', form=form, error='', action='edit', img_url=img_url,
                    supplier_shops=supplier_shops)

    @require()
    def post(self):
        form = Form(self.request.arguments, add_schema)
        goods_info, shops, properties, img = get_goods_info(self.db, form.id.value)

        if goods_info.supplier_id != self.current_user.supplier_id:
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
            self.render('wx/mall/goods_add.html', form=form, error='', action='edit', supplier_shops=supplier_shops,
                        img_url=img_url)

        # 获取微信商品手续费
        commission = self.db.get('select value from supplier_property where sp_id=%s and name="wx_commission"',
                                 self.current_user.supplier_id)
        if not commission:
            rate = Decimal((100 - options.wx_min_commission)/100.0)
        else:
            rate = Decimal((100 - int(commission.value))/100.0)
        # 更新结算价
        form.arguments['purchase_price']['value'] = form.arguments['sales_price']['value'] * rate

        fields = ('type', 'generate_type', 'expire_at', 'category_id', 'short_name', 'sms_name',
                  'max_buy', 'on_sale_at', 'off_sale_at', 'face_value', 'sales_price', 'purchase_price',
                  'stock', 'img_path', 'all_shop', 'detail',  'postage')

        update_sql = 'update goods set %s where id=%%s' % ','.join([field + '=%s' for field in fields])

        form.expire_at['value'] = ceiling(form.expire_at.value, today=True) if form.expire_at.value else None
        form.on_sale_at['value'] = form.on_sale_at.value if form.off_sale_at.value else None
        form.off_sale_at['value'] = ceiling(form.off_sale_at.value, today=True) if form.off_sale_at.value else None
        params = [form.arguments[field]['value'] for field in fields]
        params.append(form.id.value)

        self.db.execute(update_sql, *params)

        self.db.execute('insert into journal(created_at, type, created_by, message, iid) '
                        'values(NOW(), 3, %s, %s, %s)', self.current_user.name, '商户修改了微商城商品', form.id.value)

        # 批量更新关联门店
        self.db.execute('delete from goods_supplier_shop where goods_id=%s', form.id.value)
        if not form.all_shop.value:
            if form.shops.value:
                insert_shops(self.db, form.shops.value, form.id.value)

        self.redirect(self.reverse_url('wx.goods.list'))


class WxGoodsDetail(BaseHandler):
    """微信商品详情"""
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

        img = dict() if not goods.img_paths else json.loads(goods.img_paths)

        self.render('wx/mall/goods_detail.html', goods=goods, shops=shops, img_url=img_url,
                    img=img)


class WxGoodsDelete(BaseHandler):
    """删除微商城商品"""
    @require()
    def post(self):
        goods_id = self.get_argument('goods_id', 0)
        self.db.execute('update goods set deleted = 1 where status="PREPARE" and id = %s and supplier_id=%s',
                        goods_id, self.current_user.supplier_id)

        self.redirect(self.reverse_url('wx.goods.list'))


class WxGoodsRank(BaseHandler):
    """编辑微商城商品排名"""
    @require()
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        goods_id = self.get_argument('goods_id', 0)
        try:
            self.db.execute('update goods set rank=%s where id=%s and supplier_id=%s',
                            self.get_argument('rank', '0'), goods_id, self.current_user.supplier_id)
            self.write({'ok': True})
        except Exception:
            self.write({'ok': False})


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


class WxGoodsOnSale(BaseHandler):
    """微商城商品上下架"""
    @require()
    def post(self):
        operator = self.get_argument('operator', '-1')
        goods_id = self.get_argument('goods_id', '-1')

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        if operator not in ['0', '1']:
            self.write({'is_ok': False})
            return

        self.db.execute('update goods_property set value=%s where goods_id=%s and name="is_wx_on_sale"',
                        operator, goods_id)
        self.write({'is_ok': True})

list_schema = Schema({
    'supplier': str,
    'goods': str,
    'status': str,
}, extra=True)

add_schema = Schema({
    'type':             Any('E', 'R'),
    'generate_type':    Any('GENERATE', 'IMPORT'),
    'category_id':      Coerce(int),
    'on_sale_at':       Datetime(),
    'off_sale_at':      Datetime(),
    'expire_at':        Any(Datetime(), EmptyNone()),
    'properties':       All(EmptyList(), Unique()),
    'sms_name':         All(Decode(), Length(min=1, max=50)),
    'short_name':       All(Decode(), Length(min=1, max=50)),
    'face_value':       All(Coerce(Decimal), Range(min=Decimal('0.0'))),
    'sales_price':      All(Coerce(Decimal), Range(min=Decimal('0.0'))),
    'purchase_price':   All(Coerce(Decimal), Range(min=Decimal('0.0'))),
    'postage':          Any(All(Coerce(Decimal), Range(min=Decimal('0.0'))), EmptyNone()),
    'stock':            All(Coerce(int), Range(min=1)),
    'max_buy':          All(Coerce(int), Range(min=0)),
    'all_shop':         Coerce(int),
    'shops':            All(EmptyList(), Unique(), ListCoerce(int)),
    'img_path':         str,
    'img_paths':        str,
    'detail':           str,
    'tips':             str,
    'supplier_intro':   str,
    'id':               str,
}, extra=True)
