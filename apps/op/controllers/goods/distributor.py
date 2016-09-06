# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from autumn.torn.paginator import Paginator
from tornado.httputil import url_concat
from voluptuous import Schema
from autumn.torn.form import Form
from tornado.options import options
from autumn.goods import alloc_distributor_goods


list_schema = Schema({
    'supplier': str,
    'goods': str,
    'status': str,
}, extra=True)


class ShowList(BaseHandler):
    @require()
    def get(self):
        sql = """select g.id gid, g.short_name, g.sales_price, g.purchase_price, gds.*
                 from goods g left join goods_distributor_shop gds on g.id = gds.goods_id
                 and gds.distributor_shop_id = %s and gds.deleted=0 and gds.status <> 'PREPARE'
                 where g.deleted = 0 and g.status in ('PENDING', 'ON_SALE', 'OFF_SALE') and g.id not in
                  (select goods_id from ktv_product_goods) """

        abbrs = {
            'tb':   options.shop_id_taobao,
            'tm':   options.shop_id_tmall,
            'jd':   options.shop_id_jingdong,
            'jdb':  options.shop_id_jdb,
            'yhd':  options.shop_id_yihaodian,
            'wb':   options.shop_id_wuba,
            'bd':   options.shop_id_baidu,
        }

        shop_abbr = self.get_argument('shop', 'tm')
        shop_id = abbrs[shop_abbr]
        params = [shop_id]

        form = Form(self.request.arguments, list_schema)
        if form.supplier.value:
            sql += 'and g.supplier_id =%s'
            params.append(form.supplier.value)

        if form.goods.value:
            sql += 'and g.short_name like %s '
            params.append('%' + form.goods.value + '%')

        sql += ' order by g.id desc, gds.id desc'

        page = Paginator(self, sql, params)
        self.render('goods/distributor/list.html', page=page, form=form, shop_id=shop_id, shop_abbr=shop_abbr)


class Hide(BaseHandler):
    @require('operator')
    def post(self):
        self.db.execute('update goods_distributor_shop set deleted=1 where id=%s', self.get_argument('id'))
        self.redirect(url_concat(self.reverse_url('goods.distributor.show_list'),
                                 {'shop_id': self.get_argument('shop_id')}))


class ShowProducts(BaseHandler):
    @require()
    def get(self):
        """ 显示已推送的分销商品信息"""
        goods_id = self.get_argument('gds_id')
        distr_shop_id = int(self.get_argument('shop_id').encode('utf-8'))

        products = self.db.query('select * from goods_distributor_shop where deleted =0 and goods_id = %s '
                                 'and distributor_shop_id=%s and status = %s', goods_id, distr_shop_id, 'PENDING')
        url = ''
        if distr_shop_id == options.shop_id_taobao or distr_shop_id == options.shop_id_tmall:
            url = "http://item.taobao.com/item.htm?id="
        elif distr_shop_id == options.shop_id_wuba:
            url = 'http://t.58.com/sh/'
        elif distr_shop_id == options.shop_id_yihaodian:
            url = 'http://www.1mall.com/item/'
        elif distr_shop_id == options.shop_id_jingdong:
            url = 'http://tuan.jd.com/team-'
        self.render('goods/distributor/show_products.html', products=products, url=url)


class RelationProduct(BaseHandler):
    @require('operator')
    def get(self):
        shops = self.db.query('select id, name from distributor_shop where deleted =0')
        self.render('goods/distributor/relation_products.html', shops=shops, error='')

    @require('operator')
    def post(self):
        shop_id = int(self.get_argument('shop_id', 0).encode('utf-8'))
        goods_id = self.get_argument('goods_id', 0)

        if not self.db.get('select id from goods where deleted = 0 and id = %s', goods_id):
            shops_id = [options.shop_id_taobao, options.shop_id_tmall, options.shop_id_jingdong, options.shop_id_jdb,
                        options.shop_id_yihaodian, options.shop_id_wuba, options.shop_id_meituan, options.shop_id_dianping]

            shops = self.db.query('select id, name from distributor_shop where id in (%s)' % ','.join(['%s'] * len(shops_id)), *shops_id)
            self.render('goods/distributor/relation_products.html', shops=shops, error='不存在该商品')
            return

        distributor_goods_id = self.get_argument('distributor_goods_id', 0)
        status = self.get_argument('status', 'ON_SALE')

        if self.db.get('select id from goods_distributor_shop where distributor_shop_id = %s and '
                       'distributor_goods_id = %s limit 1', shop_id, distributor_goods_id):
            shops_id = [options.shop_id_taobao, options.shop_id_tmall, options.shop_id_jingdong, options.shop_id_jdb,
                        options.shop_id_yihaodian, options.shop_id_wuba, options.shop_id_meituan, options.shop_id_dianping]

            shops = self.db.query('select id, name from distributor_shop where id in (%s)' % ','.join(['%s'] * len(shops_id)), *shops_id)

            self.render('goods/distributor/relation_products.html', shops=shops, error='在该分销店铺上已存在该商品的分销id')

        distr_id = alloc_distributor_goods(self.db, goods_id, shop_id)
        self.db.execute('update goods_distributor_shop set distributor_goods_id = %s, status = %s,'
                        'created_by = %s where id = %s',
                        distributor_goods_id.strip(' '), status, self.current_user.name, distr_id.id)

        self.redirect(self.reverse_url('goods.distributor.show_list'))
