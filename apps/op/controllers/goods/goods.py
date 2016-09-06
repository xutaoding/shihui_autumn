# -*- coding: utf-8 -*-

from decimal import Decimal
from voluptuous import Schema, Any, All, Length, Coerce, Range
from tornado.options import options
from .. import BaseHandler
from .. import require
from autumn.torn.paginator import Paginator
from autumn.torn.form import Form, Datetime, Unique, Decode, ListCoerce, Strip, EmptyList, EmptyNone
from autumn.utils.dt import ceiling
from autumn.utils import EmptyDict, json_dumps
from autumn.goods import img_url
import logging
import itertools
import json


class GoodsList(BaseHandler):
    """ 商品列表 """
    @require()
    def get(self):
        # 银乐迪类的ktv产品不显示
        sql = """select g.id, g.short_name, g.face_value, g.sales_price, g.created_by,
                 g.purchase_price, g.created_at, g.status, s.short_name supplier_name
                 from goods g,supplier s
                 where g.supplier_id = s.id and g.deleted = 0  and g.status <> "PREPARE"
                 and g.id not in (select goods_id from ktv_product_goods) """

        form = Form(self.request.arguments, list_schema)
        params = []

        if form.supplier.value:
            sql += 'and g.supplier_id=%s '
            params.append(form.supplier.value)

        if form.goods.value:
            sql += 'and g.short_name like %s '
            params.append('%' + form.goods.value + '%')

        if form.status.value:
            sql += 'and g.status = %s'
            params.append(form.status.value)

        sql += 'order by g.created_at desc'

        page = Paginator(self, sql, params)
        self.render('goods/list.html', page=page, form=form)


class GoodsDetail(BaseHandler):
    """ 商品详情 """
    @require()
    def get(self, goods_id):
        goods = self.db.get('select g.*, gc.name category,s.short_name sp_name from goods g,goods_category gc, '
                            'supplier s where g.category_id = gc.id and s.id=g.supplier_id and g.id =%s', goods_id)
        shops = self.db.query(
            'select ss.* from supplier_shop ss,goods g where ss.supplier_id=g.supplier_id and g.id=%s and ss.deleted=0 '
            'and (g.all_shop=1 or ss.id in (select supplier_shop_id from goods_supplier_shop where goods_id=%s) ) ',
            goods_id, goods_id
        )
        journal = self.db.query('select * from journal where type = 3 and iid = %s order by created_at desc', goods_id)
        img_paths = dict() if not goods.img_paths else json.loads(goods.img_paths)

        distr_info = self.db.get(
            'select group_concat(concat(gds.distributor_shop_id, "-", '
            'case when gds.distributor_shop_id=7 then extra else gds.distributor_goods_id end)) dsid '
            'from goods_distributor_shop gds where gds.status="ON_SALE" '
            'group by gds.goods_id having gds.goods_id=%s', goods_id)
        distr_info = distr_info.dsid if distr_info else None

        self.render('goods/detail.html', goods=goods, shops=shops, img_url=img_url,
                    img_paths=img_paths, journal=journal, distr_info=distr_info)


class GoodsAdd(BaseHandler):
    """ 商品添加 """
    @require('operator')
    def get(self):
        form = Form(self.request.arguments, add_schema)
        form.shops.value = []
        supplier_shops = self.db.query('select ss.* from supplier_shop ss where ss.supplier_id=%s',
                                       form.supplier_id.value)
        form.skus.value = []
        all_sku = self.db.query('select * from sku where deleted=0 and supplier_id=%s', form.supplier_id.value)
        distributors = self.db.query('select * from distributor_shop where deleted = 0')

        distributor_commission = {
            options.shop_id_yihaodian:	    2.00,
            options.shop_id_dangdang:	    2.00,
            options.shop_id_jingdong:       3.00,
            options.shop_id_jdb:            1.00,
            options.shop_id_wuba:	        3.00,
            options.shop_id_gaopeng:       	1.25,
            options.shop_id_tuangouwang:	2.50,
            options.shop_id_liketuan:       2.50,
            options.shop_id_uuwang:       	2.50,
            options.shop_id_tmall:       	1.00,
            options.shop_id_jibin:       	2.50,
        }
        form.ratios.value = ['%s-%s' % (k, v) for (k, v) in distributor_commission.iteritems()]
        form.img_paths['value'] = dict()
        self.render('goods/add.html', form=form, supplier_shops=supplier_shops, all_sku=all_sku,
                    error='', action='add', distributors=distributors, img_url=img_url)

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, add_schema)

        img_paths = dict()
        for key in self.request.arguments:
            if key.startswith('var_img_path_'):
                v = self.request.arguments[key][0]
                if v:
                    img_paths[key[key.rindex('_')+1:]] = v
        form.img_paths['value'] = json_dumps(img_paths)

        if not form.validate():
            supplier_shops = self.db.query('select ss.* from supplier_shop ss where ss.supplier_id=%s and ss.deleted=0',
                                           form.supplier_id.value)
            distributors = self.db.query('select * from distributor_shop where deleted = 0')
            all_sku = self.db.query('select * from sku where deleted=0 and supplier_id=%s', form.supplier_id.value)
            form.img_paths['value'] = img_paths
            logging.error(json_dumps(form.errors))

            return self.render('goods/add.html', form=form, error='error', action='add', img_url=img_url,
                               supplier_shops=supplier_shops, all_sku=all_sku, distributors=distributors)

        fields = ('type', 'generate_type', 'expire_at', 'category_id', 'name', 'short_name', 'sms_name', 'img_paths',
                  'face_value', 'sales_price', 'purchase_price', 'stock', 'virtual_sales_count', 'img_path', 'all_shop',
                  'detail', 'tips', 'supplier_intro', 'created_by', 'supplier_id', 'on_sale_at', 'off_sale_at')

        goods_sql = 'insert into goods(%s, created_at, status) values (%s ,NOW(), "ON_SALE")' % (
            ','.join(fields), ','.join(['%s']*len(fields)))

        form.expire_at['value'] = ceiling(form.expire_at.value, today=True) if form.expire_at.value else None
        form.off_sale_at['value'] = ceiling(form.off_sale_at.value, today=True) if form.off_sale_at.value else None
        form.arguments['created_by'] = EmptyDict({'value': self.current_user.name})

        params = [form.arguments[field]['value'] for field in fields]

        goods_id = self.db.execute_lastrowid(goods_sql, * params)
        self.db.execute('insert into journal(created_at, type, created_by, message, iid) '
                        'values(NOW(), 3, %s, %s, %s)', self.current_user.name, '新增了商品', goods_id)

        # 批量插入商品属性
        if form.properties.value:
            insert_properties(self.db, form.properties.value, goods_id)

        # 批量插入关联的门店
        if not form.all_shop.value:
            if form.shops.value:
                insert_shops(self.db, form.shops.value, goods_id)

        # 批量插入SKU信息
        if form.skus.value:
            insert_skus(self.db, form.skus.value, goods_id)
        # 批量插入分销店铺佣金
        if form.ratios.value:
            insert_ratios(self.db, form.ratios.value, goods_id)
        self.redirect(self.reverse_url('goods.show_list'))


class GoodsEdit(BaseHandler):
    """ 商品编辑 """
    @require('operator')
    def get(self):
        goods_id = self.get_argument('id')
        goods_info, shops, properties = get_goods_info(self.db, goods_id)
        form = Form(goods_info, add_schema)
        form.shops['value'] = shops
        form.supplier_name.value = self.db.get('select short_name from supplier where id=%s',
                                               goods_info.supplier_id).short_name
        form.img_paths['value'] = dict() if not form.img_paths.value else json.loads(form.img_paths.value)

        supplier_shops = self.db.query('select ss.* from supplier_shop ss where ss.supplier_id=%s and ss.deleted=0',
                                       form.supplier_id.value)
        all_sku = self.db.query('select * from sku where deleted=0 and supplier_id=%s', form.supplier_id.value)
        form.skus.value = ['%s-%s' % (item.sku_id, item.num) for item in
                           self.db.query('select sku_id, num from sku_goods where goods_id=%s', goods_id)]

        distributors = self.db.query('select * from distributor_shop where deleted = 0')
        form.properties.value = ['%s-%s' % (item.name, item.value) for item in properties]
        form.ratios.value = ['%s-%s' % (item.distr_shop_id, item.ratio) for item in
                             self.db.query('select distr_shop_id, ratio from goods_distributor_commission '
                                           'where goods_id=%s', goods_id)]
        self.render('goods/add.html', form=form, error='', action='edit', img_url=img_url,
                    supplier_shops=supplier_shops, all_sku=all_sku, distributors=distributors)

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, add_schema)
        goods_info, shops, properties = get_goods_info(self.db, form.id.value)
        # 为了下面的 validate 成功 这里必须填入数据
        form.arguments.update({'type': EmptyDict({'value': goods_info.type}),
                               'generate_type': EmptyDict({'value': goods_info.generate_type})})
        img_paths = dict()
        for key in self.request.arguments:
            if key.startswith('var_img_path_'):
                v = self.request.arguments[key][0]
                if v:
                    img_paths[key[key.rindex('_')+1:]] = v
        form.img_paths['value'] = json_dumps(img_paths)
        if not form.validate():
            form.properties.value = ['%s-%s' % (item.name, item.value) for item in properties]
            form.shops['value'] = shops

            supplier_shops = self.db.query('select ss.* from supplier_shop ss where ss.supplier_id=%s and ss.deleted=0',
                                           form.supplier_id.value)
            all_sku = self.db.query('select * from sku where deleted=0 and supplier_id=%s', form.supplier_id.value)
            distributors = self.db.query('select * from distributor_shop where deleted = 0')
            form.img_paths['value'] = img_paths
            logging.error(json_dumps(form.errors))
            self.render('goods/add.html', form=form, error='', action='edit', img_url=img_url,
                        supplier_shops=supplier_shops, all_sku=all_sku, distributors=distributors)
            return

        fields = ('expire_at', 'category_id', 'name', 'short_name', 'sms_name', 'face_value', 'sales_price',
                  'stock', 'virtual_sales_count', 'img_path', 'detail', 'tips', 'supplier_intro', 'all_shop',
                  'on_sale_at', 'off_sale_at', 'purchase_price', 'img_paths')

        update_sql = 'update goods set %s, created_at = NOW(), created_by = %%s where id=%%s' % \
                     ','.join([field + '=%s' for field in fields])

        form.expire_at['value'] = ceiling(form.expire_at.value, today=True) if form.expire_at.value else None
        form.off_sale_at['value'] = ceiling(form.off_sale_at.value, today=True) if form.off_sale_at.value else None
        params = [form.arguments[field]['value'] for field in fields]
        params.append(self.current_user.name)
        params.append(form.id.value)

        #将更新前的旧数据插入goods_copy商品
        insert_fields = ('supplier_id', 'face_value', 'purchase_price', 'sales_price', 'sales_count', 'stock',
                         'virtual_sales_count', 'code', 'all_shop', 'name', 'short_name', 'sms_name', 'category_id',
                         'img_path', 'created_at', 'expire_at', 'detail', 'tips', 'supplier_intro', 'status',
                         'created_by', 'deleted', 'type', 'generate_type', 'supplier_goods_id', 'on_sale_at',
                         'off_sale_at', 'img_paths')
        change_fields = ','.join([field for field in insert_fields])
        insert_id = self.db.execute('insert into goods_copy({0}) select {0} from goods '
                                    'where id = %s'.format(change_fields), form.id.value)
        self.db.execute('update goods_copy set goods_id = %s where id = %s', form.id.value, insert_id)

        #更新goods表
        self.db.execute(update_sql, *params)

        self.db.execute('insert into journal(created_at, type, created_by, message, iid) '
                        'values(NOW(), 3, %s, %s, %s)', self.current_user.name, '修改了商品', form.id.value)

        # 批量更新商品属性
        self.db.execute('delete from goods_property where goods_id=%s and name in '
                        '("gift_card", "hidden", "ktv", "jd_team_id")', form.id.value)
        if form.properties.value:
            insert_properties(self.db, form.properties.value, form.id.value)

        # 批量更新关联门店
        self.db.execute('delete from goods_supplier_shop where goods_id=%s', form.id.value)
        if not form.all_shop.value:
            if form.shops.value:
                insert_shops(self.db, form.shops.value, form.id.value)
        # 批量更新SKU
        self.db.execute('delete from sku_goods where goods_id=%s', form.id.value)
        if form.skus.value:
            insert_skus(self.db, form.skus.value, form.id.value)
        # 批量更新分销店铺佣金
        self.db.execute('delete from goods_distributor_commission where goods_id=%s', form.id.value)
        if form.ratios.value:
            insert_ratios(self.db, form.ratios.value, form.id.value)

        self.redirect(self.reverse_url('goods.show_list'))


class GoodsCopy(BaseHandler):
    """复制商品"""
    @require('operator')
    def post(self):
        goods_id = self.get_argument('goods_id', '')
        if not goods_id:
            self.redirect(self.reverse_url('goods.show_list'))
            return

        supplier_id = self.get_argument('supplier_id', '')
        if not supplier_id:
            self.redirect(self.reverse_url('goods.show_detail', goods_id))
            return

        copy_fields = ('face_value', 'purchase_price', 'sales_price', 'stock', 'virtual_sales_count',
                       'code', 'all_shop', 'name', 'short_name', 'sms_name', 'category_id', 'img_path', 'created_at',
                       'expire_at', 'detail', 'tips', 'supplier_intro', 'status', 'created_by', 'deleted', 'type',
                       'generate_type', 'supplier_goods_id', 'on_sale_at', 'off_sale_at', 'img_paths')
        sql = 'insert into goods (supplier_id, {0}) select %s, {0} from goods where goods.id=%s'.format(', '.join(copy_fields))

        goods_copy_id = self.db.execute(sql, supplier_id, goods_id)
        self.db.execute('insert into goods_property(goods_id, name, value) '
                        'select %s, name, value from goods_property where goods_id=%s', goods_copy_id, goods_id)
        self.db.execute('insert into goods_distributor_commission(goods_id, distr_shop_id, ratio) '
                        'select %s, distr_shop_id, ratio from goods_distributor_commission where goods_id=%s',
                        goods_copy_id, goods_id)

        if goods_copy_id:
            self.redirect('edit?id=%s' % goods_copy_id)
            return
        else:
            self.redirect(self.reverse_url('goods.show_list'))
            return


class GoodsDelete(BaseHandler):
    """商品删除"""
    @require('operator')
    def post(self):
        goods_id = self.get_argument('goods_id', 0)
        self.db.execute('update goods set deleted = 1 where id = %s', goods_id)

        self.redirect(self.reverse_url('goods.show_list'))


class GoodsHistory(BaseHandler):
    """商品修改历史"""
    @require('operator')
    def get(self, goods_id):
        sql = """select gc.*, s.short_name supplier_name from goods_copy gc, supplier s
                 where gc.supplier_id = s.id and gc.goods_id = %s order by gc.id desc"""
        page = Paginator(self, sql, [goods_id])

        self.render('goods/history_list.html', page=page)


class HistoryDetail(BaseHandler):
    """商品历史详情"""
    @require('operator')
    def get(self, goods_id):
        gid = self.get_argument('id', 0)
        goods = self.db.get('select g.*, gc.name category,s.short_name sp_name from goods_copy g,goods_category gc,'
                            'supplier s where g.category_id= gc.id and s.id=g.supplier_id and g.id =%s', gid)
        shops = self.db.query(
            'select ss.* from supplier_shop ss,goods_copy g where ss.supplier_id=g.supplier_id and g.goods_id=%s and '
            'ss.deleted=0 '
            'and (g.all_shop=1 or ss.id in (select supplier_shop_id from goods_supplier_shop where goods_id=%s) ) ',
            goods_id, goods_id
        )
        if goods.img_path:
            imgurl = img_url(goods.img_path)
        else:
            imgurl = 'http://img.uhcdn.com/images/autumn/default.png'

        self.render('goods/history_detail.html', goods=goods, shops=shops, img_url=imgurl)


class Approve(BaseHandler):
    """商品通过审核与否"""
    @require('operator')
    def post(self):
        gid = self.get_argument('id', 0)
        goods = self.db.get('select short_name, supplier_id from goods where id = %s', gid)
        reason = self.get_argument('reason', '').encode('utf-8')

        status = {'pass': 'ON_SALE', 'reject': 'REJECT'}.get(self.get_argument('op'), '')
        if status:
            self.db.execute('update goods set status = %s, created_at = NOW() where id = %s', status, gid)
            url = ''
            if status == 'ON_SALE':
                title = '审核通过'
                content = '商品 %s 已经通过审核' % goods.short_name
            else:
                title = '审核未通过'
                content = '商品 %s 未通过审核。未通过原因: %s' % (goods.short_name, reason)
                url = '/goods/%s' % gid

            self.db.execute('insert into journal(created_at, type, created_by, message, iid) '
                            'values(NOW(), 3, %s, %s, %s)', self.current_user.name, content, gid)
            self.db.execute('insert into notification(title, content, created_at, type, uid, user_type, url) '
                            'values(%s, %s, NOW(), %s, %s, %s, %s)', title, content, 0, goods.supplier_id, 0, url)

        self.redirect(self.reverse_url('goods.show_list'))


def insert_properties(db, properties, goods_id):
    prop_sql = 'insert into goods_property(goods_id, name, value) values %s' % ','.join(
        ['(%s,%s,%s)']*len(properties))
    prop_params = list(itertools.chain(*[[goods_id, item.split('-')[0], item.split('-')[1]] for item in properties]))
    db.execute(prop_sql, *prop_params)


def insert_shops(db, shops, goods_id):
    shop_sql = 'insert into goods_supplier_shop(goods_id, supplier_shop_id) values %s' % ','.join(
        ['(%s,%s)']*len(shops))
    shop_params = list(itertools.chain(*[[goods_id, shop_id] for shop_id in shops]))
    db.execute(shop_sql, *shop_params)


def insert_skus(db, skus, goods_id):
    sku_sql = 'insert into sku_goods(sku_id, num, goods_id) values %s' % ','.join(
        ['(%s,%s,%s)']*len(skus))
    sku_params = list(itertools.chain(*[[item.split('-')[0], item.split('-')[1], goods_id] for item in skus]))
    db.execute(sku_sql, *sku_params)


def insert_ratios(db, ratios, goods_id):
    ratio_sql = 'insert into goods_distributor_commission(distr_shop_id, ratio, goods_id) values %s' % ','.join(
        ['(%s,%s,%s)']*len(ratios))
    ratio_params = list(itertools.chain(*[[item.split('-')[0], item.split('-')[1], goods_id] for item in ratios]))
    db.execute(ratio_sql, *ratio_params)


def get_goods_info(db, goods_id):
    goods_info = db.get('select * from goods where id = %s', goods_id)

    shops = [item.id for item in db.query('select ss.id from supplier_shop ss, goods_supplier_shop gss '
                                          'where ss.id=gss.supplier_shop_id and gss.goods_id=%s', goods_id)]
    properties = db.query('select name, value from goods_property where goods_id = %s', goods_id)
    return goods_info, shops, properties

list_schema = Schema({
    'supplier': str,
    'goods': str,
    'status': str,
}, extra=True)

add_schema = Schema({
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
    'face_value':       All(Coerce(Decimal), Range(min=Decimal('0.0'))),
    'sales_price':      All(Coerce(Decimal), Range(min=Decimal('0.0'))),
    'purchase_price':   All(Coerce(Decimal), Range(min=Decimal('0.0'))),
    'stock':            All(Coerce(int), Range(min=0)),
    'virtual_sales_count': Coerce(int),
    'supplier_id':      Coerce(int),
    'supplier_name':    str,
    'all_shop':         Coerce(int),
    'shops':            All(EmptyList(), Unique(), ListCoerce(int)),
    'skus':             All(EmptyList(), Unique()),
    'ratios':           All(EmptyList(), Unique()),
    'img_path':         str,
    'img_paths':        str,
    'detail':           str,
    'tips':             str,
    'supplier_intro':   str,
    'id':               str,
}, extra=True)

