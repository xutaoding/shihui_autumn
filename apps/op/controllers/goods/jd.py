# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
import tornado.gen
from autumn.api.jingdong import Jingdong, jd_error
from autumn.utils import json_dumps, json_hook
import string
from autumn.goods import alloc_distributor_goods, img_url, jd_logo_url_replace, html_font_size_replace
from decimal import Decimal
from datetime import datetime
from autumn.utils.dt import ceiling
import logging
import json


class Push(BaseHandler):
    @require('operator')
    @tornado.gen.coroutine
    def get(self, goods_id):
        goods = self.db.get('select * from goods where id = %s', goods_id)

        goods_area_ids = [item.area_id for item in self.db.query(
            'select ss.* from supplier_shop ss,goods g where ss.supplier_id=g.supplier_id and g.id=%s and ss.deleted=0 '
            'and (g.all_shop=1 or ss.id in (select supplier_shop_id from goods_supplier_shop where goods_id=%s))',
            goods_id, goods_id)]

        area_list = self.db.query('select area_area.name area, area_district.name district, area_city.name city from '
                                  '(select * from area where type = "AREA") as area_area, '
                                  '(select * from area where type="DISTRICT") as area_district, '
                                  '(select * from area where type="CITY") as area_city '
                                  'where area_district.parent_id = area_city.id '
                                  'and area_area.parent_id = area_district.id and area_area.id in (%s)' %
                                  ','.join(['%s']*len(goods_area_ids)), *goods_area_ids) if goods_area_ids else []

        shop_id = self.get_argument('shop_id')
        shop = self.db.get('select taobao_seller_id, taobao_api_info from distributor_shop where id=%s', shop_id)
        api_info = json.loads(shop.taobao_api_info, object_hook=json_hook)

        jd = Jingdong('queryCategoryList', str(shop.taobao_seller_id), api_info.vender_key, api_info.secret_key)
        parent_id = self.get_argument('id', '0')
        response = yield jd(category_id=parent_id)
        jd.parse_response(response.body)
        result = []
        if jd.is_ok():
            for category in jd.message.findall('Categories/Category'):
                result.append({
                    'id': category.findtext('Id'),
                    'name': category.findtext('Name'),
                })

        jd_map_city = Jingdong('queryCityList', str(shop.taobao_seller_id), api_info.vender_key, api_info.secret_key)
        map_response = yield jd_map_city()
        jd_map_city.parse_response(map_response.body)
        map_result = []
        if jd_map_city.is_ok():
            for area in jd_map_city.message.findall('Cities/City'):
                map_result.append({
                    'id': area.findtext('Id'),
                    'name': area.findtext('Name'),
                })
        # 主图
        img_paths = json.loads(goods.img_paths) if goods.img_paths else dict()
        img = img_url(img_paths['440x293']) if '440x293' in img_paths else img_url(goods.img_path)

        self.render('goods/distributor/jd/push.html', goods=goods, result=result, map_result=map_result,
                    area_list=area_list, img=img, jd_logo_url_replace=jd_logo_url_replace,
                    html_font_size_replace=html_font_size_replace, now=datetime.now(), shop_id=shop_id)

    @require('operator')
    @tornado.gen.coroutine
    def post(self, goods_id):
        params = dict([(name, self.get_argument(name).encode('utf-8')) for name in self.request.arguments])
        shops = self.db.query(
            'select ss.* from supplier_shop ss,goods g where ss.supplier_id=g.supplier_id and g.id=%s and ss.deleted=0 '
            'and (g.all_shop=1 or ss.id in (select supplier_shop_id from goods_supplier_shop where goods_id=%s))',
            goods_id, goods_id)
        params.pop('_xsrf')
        shop_id = params.pop('shop_id')
        params['shops'] = shops
        params['market_price'] = Decimal(params['market_price'])
        params['team_price'] = Decimal(params['team_price'])
        #params['groupon_bimg'] = 'http://www.itlearner.com/google_commonweal_ad/images/sun/300px.jpg'
        params['min_number'] = 1
        if params['max_number'] == '0':
            params['max_number'] = '9999'
        #分割区域和商圈信息
        district_info = params.pop('district_info')
        sp = (',', '-')
        for s in sp:
            district_info = district_info.replace(s, ' ')
        dd = string.split(district_info, ' ')
        districts = {}
        for i in range(len(dd) / 2):
            if dd[2 * i] not in districts:
                districts[dd[2 * i]] = []
            districts[dd[2 * i]].append(dd[2 * i + 1])
        params['districts'] = districts
        params['group2'] = string.split(params['group2'], ',')
        vender_team = alloc_distributor_goods(self.db, goods_id, shop_id)
        params['vender_team_id'] = vender_team.goods_link_id

        shop = self.db.get('select taobao_seller_id, taobao_api_info from distributor_shop where id=%s', shop_id)
        api_info = json.loads(shop.taobao_api_info, object_hook=json_hook)

        jd_push = Jingdong('uploadTeam', str(shop.taobao_seller_id), api_info.vender_key, api_info.secret_key)
        response = yield jd_push.fetch(**params)
        jd_push.parse_response(response.body)

        if jd_push.is_ok():
            message = '发布成功'
            offsale_at = datetime.strptime(params['end_time'], '%Y-%m-%d %H:%M:%S')
            expire_at = ceiling(datetime.strptime(params['expire_time'], '%Y-%m-%d %H:%M:%S'), today=True)
            self.db.execute('update goods_distributor_shop set status="PENDING", created_by=%s, created_at=NOW(), '
                            'offsale_at = %s, expire_at = %s, distributor_goods_id = %s '
                            'where goods_id=%s and distributor_shop_id=%s and goods_link_id=%s',
                            self.current_user.name, offsale_at, expire_at,
                            jd_push.message.findtext('JdTeamId'), goods_id, shop_id, vender_team.goods_link_id)

            logging.info('jingdong push success. goods_id = %s, distributor_goods_id = %s',
                         goods_id, jd_push.message.findtext('JdTeamId'))

        else:
            message = '上传失败：' + str(jd_error['error_message'].get(int(jd_push.result_code)))

        self.render('goods/distributor/jd/result.html', message=message)


class Edit(BaseHandler):
    @require('operator')
    @tornado.gen.coroutine
    def get(self):
        product = self.db.get('select * from goods_distributor_shop where id = %s', self.get_argument('gds_id'))
        goods = self.db.get('select * from goods where id = %s', product.goods_id)
        shops = self.db.query(
            'select ss.* from supplier_shop ss,goods g where ss.supplier_id=g.supplier_id and g.id=%s and ss.deleted=0 '
            'and (g.all_shop=1 or ss.id in (select supplier_shop_id from goods_supplier_shop where goods_id=%s))',
            goods.id, goods.id)

        img_paths = json.loads(goods.img_paths) if goods.img_paths else dict()
        img = img_url(img_paths['440x293']) if '440x293' in img_paths else img_url(goods.img_path)
        self.render('goods/distributor/jd/edit.html', product=product, goods=goods, shops=shops, now=datetime.now(),
                    img=img, jd_logo_url_replace=jd_logo_url_replace, html_font_size_replace=html_font_size_replace)

    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        params = dict([(name, self.get_argument(name).encode('utf-8')) for name in self.request.arguments])
        params.pop('_xsrf')

        shop_id = params.pop('shop_id')
        shop = self.db.get('select taobao_seller_id, taobao_api_info from distributor_shop where id=%s', shop_id)
        api_info = json.loads(shop.taobao_api_info, object_hook=json_hook)

        jingdong = Jingdong(self.get_argument('method'), str(shop.taobao_seller_id),
                            api_info.vender_key, api_info.secret_key)
        response = yield jingdong.fetch(**params)
        jingdong.parse_response(response.body)
        if jingdong.is_ok():
            if params['method'] == 'teamExtension':
                params['sale_end_date'] = ceiling(datetime.strptime(params['sale_end_date'], '%Y-%m-%d %H:%M:%S'), today=True)
                self.db.execute('update goods_distributor_shop set offsale_at = %s where id = %s',
                                params['sale_end_date'], params['product_id'])
            message = '修改成功'
        else:
            message = '修改失败, 失败原因: ' + jd_error.get(self.get_argument('method'), {}).get(int(jingdong.result_code), '')

        self.render('goods/distributor/jd/result.html', message=message)


class CityAjax(BaseHandler):
    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        parent_id = self.get_argument('id', '0')
        parent_type = self.get_argument('type', 'province')

        shop_id = self.get_argument('shop_id')
        shop = self.db.get('select taobao_seller_id, taobao_api_info from distributor_shop where id=%s', shop_id)
        api_info = json.loads(shop.taobao_api_info, object_hook=json_hook)

        if parent_type == 'province':
            jingdong = Jingdong('queryCityList', str(shop.taobao_seller_id), api_info.vender_key, api_info.secret_key)
            params = {}
            path = 'Cities/City'
        elif parent_type == 'city':
            jingdong = Jingdong('queryDistrictList', str(shop.taobao_seller_id),
                                api_info.vender_key, api_info.secret_key)
            params = {'city_id': parent_id}
            path = 'Districts/District'
        else:
            jingdong = Jingdong('queryAreaList', str(shop.taobao_seller_id), api_info.vender_key, api_info.secret_key)
            params = {'district_id': parent_id}
            path = 'Areas/Area'

        response = yield jingdong(**params)
        jingdong.parse_response(response.body)

        self.set_header('Content-Type', 'application/json; charset=UTF-8')

        if jingdong.is_ok():
            result = []
            for node in jingdong.message.findall(path):
                result.append({
                    'id': node.findtext('Id'),
                    'name': node.findtext('Name'),
                    'type': {'province': 'city', 'city': 'district', 'district': 'area'}[parent_type],
                    'nocheck': parent_type in ('province', 'city'),
                    'isParent': parent_type != 'district'
                })
            self.write(json_dumps(result))
        else:
            self.write('[]')


class CategoryAjax(BaseHandler):
    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        parent_id = self.get_argument('id', '0')
        category_type = self.get_argument('type', 'grand')

        shop_id = self.get_argument('shop_id')
        shop = self.db.get('select taobao_seller_id, taobao_api_info from distributor_shop where id=%s', shop_id)
        api_info = json.loads(shop.taobao_api_info, object_hook=json_hook)

        jingdong = Jingdong('queryCategoryList', str(shop.taobao_seller_id), api_info.vender_key, api_info.secret_key)
        response = yield jingdong(category_id=parent_id)
        jingdong.parse_response(response.body)

        self.set_header('Content-Type', 'application/json; charset=UTF-8')

        if jingdong.is_ok():
            result = []
            for node in jingdong.message.findall('Categories/Category'):
                result.append({
                    'id': node.findtext('Id'),
                    'name': node.findtext('Name'),
                    'type': {'grand': 'parent', 'parent': 'son'}[category_type],
                    'nocheck': category_type == 'grand',
                    'isParent': category_type not in ('parent', 'son')
                })
            self.write(json_dumps(result))
        else:
            self.write('[]')
