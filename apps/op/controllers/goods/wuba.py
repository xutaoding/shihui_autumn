# -*- coding: utf-8 -*-
from .. import BaseHandler
from .. import require
from datetime import datetime
import logging
from tornado.options import options
from autumn.api.wuba import Wuba
from autumn.utils import json_dumps
import tornado.gen
from autumn.goods import alloc_distributor_goods, img_url
from autumn.utils.dt import ceiling
import json


class Show(BaseHandler):
    @require('operator')
    def get(self, goods_id):
        """展示推送页面 """
        goods = self.db.get("select * from goods where id =%s", goods_id)
        goods_shops = get_goods_shops(self, goods_id)
        area_list = get_area_list(self, goods_shops)

        img_paths = json.loads(goods.img_paths) if goods.img_paths else dict()
        img_path = img_url(img_paths['680x425']) if '680x425' in img_paths else img_url(goods.img_path)

        self.render('goods/distributor/wuba/push.html', goods=goods, goods_shops=goods_shops,
                    area_list=area_list, img_path=img_path)


class Push(BaseHandler):
    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        """推送商品"""
        arg = lambda k: self.get_argument(k).encode('utf-8')
        goods_id = self.get_argument('goods_id')

        dg = alloc_distributor_goods(self.db, goods_id, options.shop_id_wuba)
        params = dict([(name, self.get_argument(name).encode('utf-8')) for name in self.request.arguments])

        params.pop("goods_id")
        params.pop("_xsrf")
        params['groupbuyId'] = dg.goods_link_id
        prod_model_json = dict(prodmodcatename=arg('prodName'), prodprice=arg('prodPrice'),
                               groupprice=arg('groupPrice'), prodcode='', count=arg('saleMaxNum'))

        cityIds = self.request.arguments['cityIds']
        ids = []
        for cityId in cityIds:
            ids.append(int(cityId))

        params['cityIds'] = str(ids)

        if options.app_mode == 'dev':
            params['prodImg'] = 'http://www.itlearner.com/google_commonweal_ad/images/sun/300px.jpg'
        params['prodModelJson'] = '{%s}' % json_dumps(prod_model_json)
        #商家信息参数
        shop_ids = list(arg('shop_ids').split(","))
        # 将团购信息参数中的特定key值转移出来，构建商家信息参数
        partner_keys = {"partnerId", "title", "shortTitle", "telephone", "webUrl", "busline", "mapImg",
                        "mapServiceId", "mapUrl", "latitude", "longitude", "address", "circleId"}
        partners = []
        for shop_id in shop_ids:
            partner = {}
            for key in partner_keys:
                partner[key] = params.pop(key + "_" + shop_id)
            partners.append(partner)

        request_params = {'groupbuyInfo': params, 'partners': partners}
        wb = Wuba('addgroupbuy')
        response = yield wb.fetch(**request_params)
        wb.parse_response(response.body)

        if wb.is_ok():
            off_sale_at = datetime.strptime(params['endTime'], '%Y-%m-%d %H:%M:%S')
            expire_at = ceiling(datetime.strptime(params['deadline'], '%Y-%m-%d %H:%M:%S'), today=True)
            self.db.execute('update goods_distributor_shop set status="PENDING", created_by=%s, created_at=NOW(), '
                            'offsale_at = %s, expire_at = %s, distributor_goods_id = %s '
                            'where goods_id=%s and distributor_shop_id=%s and goods_link_id=%s',
                            self.current_user.name, off_sale_at, expire_at,
                            wb.message.data.groupbuyId58, goods_id, options.shop_id_wuba, dg.goods_link_id)

            self.render('goods/distributor/wuba/result.html', ok=True, title='上传成功',
                        explain='<a href="http://t.58.com/sh/%s" target="_blank">去58查看商品</a><br/><a href="/goods/distributor?shop=wb">'
                                '继续上传58商品</a>' % wb.message.data.groupbuyId58)
        else:
            self.render('goods/distributor/wuba/result.html', ok=False, title='上传出错', explain=wb.message.msg)


class Edit(BaseHandler):
    """ 编辑58商品 """
    @require('operator')
    def get(self):
        product = self.db.get('select * from goods_distributor_shop where id = %s', self.get_argument('gds_id'))
        goods = self.db.get('select * from goods where id = %s', product.goods_id)
        goods_shops = get_goods_shops(self, goods.id)
        area_list = get_area_list(self, goods_shops)

        img_paths = json.loads(goods.img_paths) if goods.img_paths else dict()
        img_path = img_url(img_paths['680x425']) if '680x425' in img_paths else img_url(goods.img_path)
        self.render('goods/distributor/wuba/edit.html', goods=goods, product=product,
                    goods_shops=goods_shops, area_list=area_list, img_path=img_path)

    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        """编辑团购和商户信息"""
        product_id = self.get_argument('product_id')
        product = self.db.get('select * from goods_distributor_shop where id = %s', product_id)
        params = dict([(name, self.get_argument(name).encode('utf-8')) for name in self.request.arguments])

        params.pop("product_id")
        params.pop("method")
        params.pop("_xsrf")
        method = self.get_argument("method")

        if 'endTime' in self.request.arguments:
            end_time = params['endTime']
        request_params = getattr(self, method)(params, str(product.goods_link_id))
        wb = Wuba(method)
        response = yield wb.fetch(**request_params)
        wb.parse_response(response.body)

        if wb.is_ok():
            #券延期成功之后再延期团购结束日期
            if method == 'delay':
                params.pop("deadline")
                request_params = {'groupbuyId': product.goods_link_id, 'endTime': end_time}
                wb = Wuba('editgroupbuyinfo')
                response = yield wb.fetch(**request_params)
                wb.parse_response(response.body)
                if wb.is_ok():
                    logging.info("延长团购结束日期成功！商品ID=%s", product_id)

            self.render('goods/distributor/wuba/result.html', ok=True, title='编辑成功',
                        explain='<a href="/goods/distributor?shop_id=%s">继续上传58商品</a>' % options.shop_id_wuba)
        else:
            self.render('goods/distributor/wuba/result.html', ok=False, title='修改出错', explain=wb.message.msg)

    def editgroupbuyinfo(self, params, goods_link_id):
        params['groupbuyId'] = goods_link_id
        return params

    def editpartnerbygroupbuy(self, params, goods_link_id):
        arg = lambda k: self.get_argument(k).encode('utf-8')
        params.pop("shop_ids")
        params.pop("cityIds")
        params['groupbuyId'] = goods_link_id
        #商家信息参数
        shop_ids = list(arg('shop_ids').split(","))
        # 将团购信息参数中的特定key值转移出来，构建商家信息参数
        partner_keys = {"partnerId", "title", "shortTitle", "telephone", "webUrl", "busline", "mapImg",
                        "mapServiceId", "mapUrl", "latitude", "longitude", "address", "circleId"}
        partners = []
        for shop_id in shop_ids:
            params.pop("circleIdChain_" + shop_id)
            partner = {}
            for key in partner_keys:
                partner[key] = params.pop(key + "_" + shop_id)
            partners.append(partner)

        return {'groupbuyInfo': params, 'partners': partners}

    def delay(self, params, goods_link_id):
        params.pop("endTime")
        params['groupbuyId'] = goods_link_id
        return params

    def xiaxian(self, params, goods_link_id):
        params['groupbuyId'] = goods_link_id
        return params


class CategoryAjax(BaseHandler):
    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        wb = Wuba('find.allprotype')
        response = yield wb()
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        wb.parse_response(response.body)
        parent_id = int(self.get_argument('id', '0'))
        result = []
        if wb.is_ok():
            for node in wb.message.data:
                if node.parentId == parent_id:
                    result.append({
                        'id': node.prodTypeId,
                        'name': node.name,
                        'isParent': False
                    })
            self.write(json_dumps(result))
        else:
            self.write('[]')


def get_goods_shops(self, goods_id):
    """ 取得门店信息"""
    return self.db.query(
        'select ss.*,ss.name area_name '
        'from supplier_shop ss, goods g where ss.supplier_id=g.supplier_id and g.id=%s and ss.deleted=0 '
        'and (g.all_shop=1 or ss.id in (select supplier_shop_id from goods_supplier_shop where goods_id=%s))',
        goods_id, goods_id)


def get_area_list(self, goods_shops):
    """ 取得商圈信息"""
    area_ids = [item.area_id for item in goods_shops]
    return self.db.query('select area_area.name area, area_district.name district, area_city.name city from '
                         '(select * from area where type = "AREA") as area_area, '
                         '(select * from area where type="DISTRICT") as area_district, '
                         '(select * from area where type="CITY") as area_city '
                         'where area_district.parent_id = area_city.id '
                         'and area_area.parent_id = area_district.id and area_area.id in (%s)' %
                         ','.join(['%s'] * len(area_ids)), *area_ids)