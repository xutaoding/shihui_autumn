# -*- coding: utf-8 -*-

__author__ = 'likang'

import os
import random
from datetime import datetime
from tornado.options import options
import xpinyin
from ..import BaseHandler
from ..import require
from autumn.utils import json_dumps
from autumn.goods import img_url, contract_url

pinyin = xpinyin.Pinyin()


class AutocompleteSupplier(BaseHandler):
    """ 提供给autocomplete的supplier列表 """
    @require()
    def post(self):
        sql = 'select id, short_name,name from supplier where deleted = 0'
        result = []
        for supplier in self.db.query(sql):
            result.append({
                'id': supplier.id,
                'value': pinyin.get_pinyin(supplier.short_name.decode('utf-8'), '').encode('utf-8'),
                'label': '%s (%s)' % (supplier.short_name, supplier.name),
                'full_name': supplier.name,
                'alias': [
                    pinyin.get_initials(supplier.short_name.decode('utf-8'), splitter=u'').lower().encode('utf-8'),
                    supplier.short_name,
                ]
            })
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(result))


class AutocompleteAgent(BaseHandler):
    """提供给autocomplete的agent 表"""
    @require()
    def post(self):
        sql = 'select id, short_name, name, type from agent where deleted=0'
        result = []
        for a in self.db.query(sql):
            result.append({
                'id': a.id,
                'type': a.type,
                'value': pinyin.get_pinyin(a.short_name.decode('utf-8'), '').encode('utf-8'),
                'label': '%s (%s)' % (a.short_name, a.name),
                'full_name': a.name,
                'alias': [
                    pinyin.get_initials(a.short_name.decode('utf-8'), splitter=u'').lower().encode('utf-8'),
                    a.short_name,
                ]
            })
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(result))


class AutocompleteSku(BaseHandler):
    """ 提供给autocomplete的sku列表 """
    @require()
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
                    pinyin.get_initials(sku.name.decode('utf-8'), splitter=u'').lower().encode('utf-8'),
                    sku.name,
                ]
            })
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(result))


class AutocompleteOperator(BaseHandler):
    """所有运营人员名字的自动补全（包括已删除的）"""
    @require()
    def post(self):
        sql = 'select * from operator'
        result = []
        for op in self.db.query(sql):
            result.append({
                'id': op.id,
                'value': pinyin.get_pinyin(op.name.decode('utf-8'), '').encode('utf-8'),
                'label': op.name,
                'alias': [
                    pinyin.get_initials(op.name.decode('utf-8'), splitter=u'').lower().encode('utf-8'),
                    op.name,
                ]
            })
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(result))


class GoodsCategories(BaseHandler):
    """ json 格式的商品分类
        形如： [ "分类A":{"id": 1, "children": [{"id": 11, "name": "子分类"},...] },"分类B":{},... ]
    """
    @require()
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
    @require()
    def post(self):
        supplier_id = self.get_argument('supplier_id')
        params = []
        sql = '''select s.id sid, s.short_name sname, ss.id, ss.name from supplier s, supplier_shop ss
                 where s.id=ss.supplier_id and ss.deleted=0 '''
        if supplier_id:
            sql += 'and s.id=%s'
            params.append(supplier_id)

        data = self.db.query(sql, *params)
        suppliers = dict([(d.sid, {'id': d.sid, 'name': d.sname, 'children': []}) for d in data])
        for d in data:
            suppliers[d.sid]['children'].append({'id': d.id, 'name': d.name})
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(suppliers.values()))


class SupplierGoods(BaseHandler):
    """
    根据supplier id, 获得商户所有商品名字及id
    """
    @require()
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        supplier_id = self.get_argument('supplier_id')
        if not supplier_id:
            self.write(json_dumps({'error': '请输入正确商户'}))
            return
        goods = self.db.query('select id, short_name, type from goods where supplier_id=%s and deleted=0', supplier_id)

        if not goods:
            self.write(json_dumps({'error': '该商户下未查询到关联商品'}))
            return

        data = [{'id': g.id, 'name': g.short_name, 'type': g.type} for g in goods]
        self.write(json_dumps({'goods': data}))


class KindEditorUploadImage(BaseHandler):
    """ KindEditor 上传图片的服务器端代码 """
    @require()
    def post(self):
        if (not self.request.files) or (not 'imgFile' in self.request.files):
            return self.write(json_dumps({'error': 1, 'message': u'请选择文件'}))

        img_file = self.request.files['imgFile'][0]
        o_filename = img_file['filename']

        # 选择上传根目录
        root = self.get_argument('root', '')
        if root:
            upload_root = options['upload_img_path_%s' % root]
        else:
            upload_root = options.upload_img_path

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
        file_dir = os.path.join(upload_root, three_level_path)

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

        if root == 'contract':
            url = contract_url(os.path.join('/', three_level_path, file_name))
        else:
            url = img_url(os.path.join('/', three_level_path, file_name), *masks)
        self.write(json_dumps({'error': 0, 'url': url}))


class Areas(BaseHandler):
    """ json 格式的区域
        形如： [ "城市A":{"id": 1, "区域": [{"id": 11, "name": "区域"，"商圈":[{"id":111,"name":"商圈"}]},...] },"城市B":{},... ]
    """

    @require()
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
