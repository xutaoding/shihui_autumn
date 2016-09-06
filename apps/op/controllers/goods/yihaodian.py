# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from autumn.api.yihaodian import Yihaodian
from autumn.utils import json_dumps, PropDict
from autumn.goods import alloc_distributor_goods
import tornado.gen
from tornado.options import options


class ShowCategory(BaseHandler):
    """ 显示商品分类选择 """
    @require('operator')
    def get(self, goods_id):
        self.render('goods/distributor/yihaodian/category.html', goods_id=goods_id)


class Push(BaseHandler):
    """ 推送商品 """
    @require('operator')
    @tornado.gen.coroutine
    def get(self):
        goods_id = self.get_argument('goods_id')
        category_id = self.get_argument('category_id')

        # 首先查询品牌和该分类下的所有额外属性
        brands_request = Yihaodian('yhd.category.brands.get')
        attribute_request = Yihaodian('yhd.category.attribute.get')
        brands_response, attribute_response = yield [brands_request(), attribute_request(categoryId=category_id)]
        brands_request.parse_response(brands_response.body)
        attribute_request.parse_response(attribute_response.body)

        brands = [PropDict({'brandId': brand.findtext('./brandId'), 'brandName': brand.findtext('./brandName')})
                  for brand in brands_request.message.findall('./brandInfoList/brandInfo')]

        if attribute_request.is_ok():
            attributes = attribute_request.message.findall('./categoryAttributeInfoList/categoryAttributeInfo')
        else:
            attributes = []

        goods = self.db.get('select * from goods where id=%s', goods_id)

        goods_shops = self.db.query(
            'select ss.* from supplier_shop ss,goods g where ss.supplier_id=g.supplier_id and g.id=%s and ss.deleted=0 '
            'and (g.all_shop=1 or ss.id in (select supplier_shop_id from goods_supplier_shop where goods_id=%s))',
            goods_id, goods_id)

        self.render('goods/distributor/yihaodian/push.html',
                    category_id=category_id,
                    category_name=self.get_argument('category_name'),
                    brands=brands,
                    attributes=attributes,
                    goods=goods,
                    goods_shops=goods_shops)

    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        arg = lambda k: self.get_argument(k).encode('utf-8')

        attr_items = []  # 带选项的属性
        attr_texts = []  # 需要输入的属性
        for name in self.request.arguments:
            if name.startswith('attr_item_'):
                attr_items.append('%s:%s' % (name[10:], '|'.join(self.get_arguments(name)).encode('utf-8')))
            elif name.startswith('attr_text_'):
                attr_texts.append('%s:%s' % (name[10:], arg(name)))

        goods_id = self.get_argument('goods_id')
        dg = alloc_distributor_goods(self.db, goods_id, options.shop_id_yihaodian)

        yihaodian = Yihaodian('yhd.product.add')
        response = yield yihaodian(
            outerId=dg.goods_link_id,
            prodAttributeInfoList=','.join(attr_texts), prodAttributeItemInfoList=','.join(attr_items),
            productType=arg('productType'), categoryId=arg('categoryId'),
            merchantCategoryId=arg('merchantCategoryId'), productCname=arg('productCname'),
            productSubTitle=arg('productSubTitle'), virtualStockNum=arg('virtualStockNum'),
            productNamePrefix=arg('productNamePrefix'), brandId=arg('brandId'),
            productMarketPrice=arg('productMarketPrice'), weight=arg('weight'),
            productSalePrice=arg('productSalePrice'), canSale=arg('canSale'),
            productDescription=arg('productDescription'), electronicCerticate=arg('electronicCerticate')
        )
        yihaodian.parse_response(response.body)
        if not yihaodian.is_ok():
            self.render('goods/distributor/yihaodian/result.html', ok=False, title="上传出错",
                        explain='<br/>'.join([error.findtext('errorCode')+':'+error.findtext('errorDes')
                                              for error in yihaodian.message.findall('./errInfoList/errDetailInfo')]))
        else:
            self.db.execute('update goods_distributor_shop set status="PENDING", created_by=%s, created_at=NOW() '
                            'where goods_id=%s and distributor_shop_id=%s and goods_link_id=%s',
                            self.current_user.name, goods_id, options.shop_id_yihaodian, dg.goods_link_id)
            self.render('goods/distributor/yihaodian/upload_img.html', error=None, goods_link_id=dg.goods_link_id)


class UploadImg(BaseHandler):
    """ 上传主图 """
    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        goods_link_id = self.get_argument('goods_link_id').encode('utf-8')
        if (not self.request.files) or (not 'img_file' in self.request.files):
            self.render('goods/distributor/yihaodian/upload_img.html',
                        error='请选择文件', goods_link_id=goods_link_id)
        else:
            img_file = self.request.files['img_file'][0]
            yihaodian = Yihaodian('yhd.product.img.upload')
            yihaodian.add_file('img_file', img_file['filename'], img_file['body'])
            response = yield yihaodian(outerId=goods_link_id)
            yihaodian.parse_response(response.body)
            if yihaodian.is_ok():
                self.render('goods/distributor/yihaodian/result.html', ok=True, title="上传成功",
                            explain='<a href="/goods/distributor?shop=yhd">继续推送其他一号店商品</a>')
            else:
                self.render('goods/distributor/yihaodian/upload_img.html',
                            goods_link_id=goods_link_id,
                            error='<br/>'.join([error.findtext('errorCode')+':'+error.findtext('errorDes')
                                                for error in yihaodian.message.findall('./errInfoList/errDetailInfo')]))


class Edit(BaseHandler):
    """ 编辑一号店商品 """
    @require('operator')
    def get(self):
        goods = self.db.get('select g.*, gds.goods_link_id from goods g, goods_distributor_shop gds '
                            'where gds.goods_id = g.id and gds.id=%s', self.get_argument('gds_id'))
        goods_shops = self.db.query(
            'select ss.* from supplier_shop ss, goods_supplier_shop gss '
            'where ss.id = gss.supplier_shop_id and gss.goods_id=%s order by ss.supplier_id', goods.id)
        self.render('goods/distributor/yihaodian/edit.html', goods=goods, goods_shops=goods_shops)

    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        arg = lambda k: self.get_argument(k).encode('utf-8')
        yihaodian = Yihaodian('yhd.product.update')
        response = yield yihaodian(outerId=arg('goods_link_id'),
                                   productCname=arg('productCname'),
                                   productSubTitle=arg('productSubTitle'),
                                   productNamePrefix=arg('productNamePrefix'),
                                   productDescription=arg('productDescription'))
        yihaodian.parse_response(response.body)
        if yihaodian.is_ok():
            self.render('goods/distributor/yihaodian/result.html', ok=True, title="编辑成功",
                        explain='<a href="/goods/distributor?shop=yhd">继续编辑其他一号店商品</a>')
        else:
            self.render('goods/distributor/yihaodian/result.html', ok=False, title="编辑出错",
                        explain='<br/>'.join([error.findtext('errorCode')+':'+error.findtext('errorDes')
                                              for error in yihaodian.message.findall('./errInfoList/errDetailInfo')]))


class CategoryAjax(BaseHandler):
    """ 一号店分类 用于响应 zTree 发起的 ajax 请求 """
    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        yihaodian = Yihaodian('yhd.category.products.get')
        parent_id = self.get_argument('id', 0)
        response = yield yihaodian(categoryParentId=parent_id)
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        yihaodian.parse_response(response.body)

        if yihaodian.is_ok():
            result = []
            for node in yihaodian.message.findall('./categoryInfoList/categoryInfo'):
                result.append({
                    'id': node.findtext('categoryId'),
                    'name': node.findtext('categoryName'),
                    'isParent': node.findtext('categoryIsLeaf') == '0'
                })
            self.write(json_dumps(result))
        else:
            self.write('[]')


class MerchantCategory(BaseHandler):
    """ 一号店商家分类 用于响应 zTree 发起的 ajax 请求 """
    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        yihaodian = Yihaodian('yhd.category.merchant.products.get')
        parent_id = self.get_argument('id', '0')
        response = yield yihaodian(categoryParentId=parent_id)
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        yihaodian.parse_response(response.body)

        if yihaodian.is_ok():
            result = []
            for node in yihaodian.message.findall('./merchantCategoryInfoList/merchantCategoryInfo'):
                result.append({
                    'id': node.findtext('merchantCategoryId'),
                    'name': node.findtext('categoryName'),
                    'isParent': node.findtext('categoryIsLeaf') == '0'
                })
            self.write(json_dumps(result))
        else:
            self.write('[]')