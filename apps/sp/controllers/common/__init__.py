# -*- coding: utf-8 -*-

__author__ = 'likang'

import os
import random
from datetime import datetime
from tornado.options import options
import xpinyin
import tornado.web
from ..import BaseHandler
from autumn.utils import json_dumps
from autumn.goods import img_url
from PIL import Image
import StringIO

pinyin = xpinyin.Pinyin()


class AutocompleteSupplier(BaseHandler):
    """ 提供给autocomplete的supplier列表 """
    @tornado.web.authenticated
    def post(self):
        sql = 'select id, short_name,name from supplier where deleted = 0'
        result = []
        for supplier in self.db.query(sql):
            result.append({
                'id': supplier.id,
                'value': pinyin.get_pinyin(supplier.short_name.decode('utf-8'), '').encode('utf-8'),
                'label': supplier.short_name,
                'full_name': supplier.name,
                'alias': [
                    ''.join([pinyin.get_initials(s).lower().encode('utf-8') for s in supplier.short_name.decode('utf-8')]),
                    supplier.short_name,
                ]
            })
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(result))


class AutocompleteSku(BaseHandler):
    """ 提供给autocomplete的sku列表 """
    @tornado.web.authenticated
    def post(self):
        sql = 'select s.id, s.name,sum(si.remain_stock) remain_stock ' \
              'from sku s left join stock_item si on si.sku_id = s.id and si.deleted =0 ' \
              'where s.deleted = 0 group by s.id'

        result = []
        for sku in self.db.query(sql):
            result.append({
                'id': sku.id,
                'value': pinyin.get_pinyin(sku.name.decode('utf-8'), '').encode('utf-8'),
                'label': sku.name,
                'remain_stock': sku.remain_stock,
                'alias': [
                    ''.join([pinyin.get_initials(s).lower().encode('utf-8') for s in sku.name.decode('utf-8')]),
                    sku.name,
                ]
            })
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(result))


class GoodsCategories(BaseHandler):
    """ json 格式的商品分类
        形如： [ "分类A":{"id": 1, "children": [{"id": 11, "name": "子分类"},...] },"分类B":{},... ]
    """
    @tornado.web.authenticated
    def post(self):
        categories = self.db.query('select id, name, parent_id from goods_category')
        parents = dict([(c.id, {'id': c.id, 'name': c.name, 'children': []}) for c in categories if not c.parent_id])
        for category in categories:
            if category.parent_id:
                parents[category.parent_id]['children'].append({'id': category.id, 'name': category.name})

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(parents.values()))


class SupplierShops(BaseHandler):
    """ json 格式的商户门店列表
        可传入 supplier_id 参数指定具体的商户，否则返回所有商户的门店信息
    """
    @tornado.web.authenticated
    def post(self):
        supplier_id = self.get_argument('supplier_id')
        params = []
        result = []
        sql = 'select id, name, supplier_id from supplier_shop where deleted=0 '
        if supplier_id:
            sql += 'and supplier_id=%s'
            params.append(supplier_id)

        data = self.db.query(sql, *params)
        for shop in data:
            result.append({
                'id': shop.id,
                'value': pinyin.get_pinyin(shop.name.decode('utf-8'), '').encode('utf-8'),
                'label': shop.name,
                'full_name': shop.name,
                'alias': [
                    ''.join([pinyin.get_initials(s).lower().encode('utf-8') for s in shop.name.decode('utf-8')]),
                    shop.name,
                ]
            })
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(result))


class KindEditorUploadImage(BaseHandler):
    """ KindEditor 上传图片的服务器端代码 """
    @tornado.web.authenticated
    def post(self):
        if (not self.request.files) or (not 'imgFile' in self.request.files):
            return self.write(json_dumps({'error': 1, 'message': u'请选择文件'}))

        img_file = self.request.files['imgFile'][0]
        o_filename = img_file['filename']
        size = self.get_argument('size', '')
        if size:
            img_info = Image.open(StringIO.StringIO(img_file['body']))
            if '%sx%s' % img_info.size != size:
                return self.write(json_dumps({'error': 1, 'message': u'图片尺寸错误，请上传尺寸为 %s 的图片' % size}))

        # 生成文件名
        random_id = int(datetime.now().strftime('%Y%m%d%H%M%S%f')[:19])
        random_id += random.randint(0, 99)
        extension = os.path.splitext(o_filename)[1]
        file_name = '%s%s' % (random_id, extension)

        # 算出目录
        first_dir = random_id >> 20
        second_dir = (~(first_dir << 10)) & (random_id >> 10)
        third_dir = (~((random_id >> 10) << 10)) & random_id
        first_dir %= 1000

        three_level_path = os.path.join(str(first_dir), str(second_dir), str(third_dir))
        file_dir = os.path.join(options.upload_img_path, three_level_path)

        # 如果目录不存在，创建之
        if not os.path.exists(file_dir):
            try:
                os.makedirs(file_dir)
            except OSError:
                return self.write(json_dumps({'error': 1, 'message': u'创建目录失败'}))

        # 保存文件
        try:
            with open(os.path.join(file_dir, file_name), 'w') as f:
                f.write(img_file['body'])
        except IOError:
            return self.write(json_dumps({'error': 1, 'message': u'保存文件失败'}))

        # 文件名上加认证信息、水印信息
        masks = ['nw']
        if self.get_argument('source', ''):
            masks.append(self.get_argument('source'))

        url = img_url(os.path.join('/', three_level_path, file_name), *masks)
        self.write(json_dumps({'error': 0, 'url': url}))


class Areas(BaseHandler):
    """ json 格式的区域
        形如： [ "城市A":{"id": 1, "区域": [{"id": 11, "name": "区域"，"商圈":[{"id":111,"name":"商圈"}]},...] },"城市B":{},... ]
    """

    @tornado.web.authenticated
    def post(self):
        areas = self.db.query('select id, name, type, parent_id from area where deleted = 0')
        all_areas = dict([(area.id, area) for area in areas])

        for area_id in all_areas:
            area = all_areas[area_id]
            if area['parent_id']:
                parent = all_areas[area['parent_id']]
                if not 'children' in parent:
                    parent['children'] = []
                parent['children'].append(area)
        result = [area for area in all_areas.values() if not area['parent_id']]
        for area in result:
            del area['parent_id']

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(result))

