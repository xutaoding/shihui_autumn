#-*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
import json
from tornado.options import options
import tornado.gen
from autumn.utils import json_dumps, json_hook
from autumn.api.taobao import Taobao
from autumn.goods import alloc_distributor_goods
import time
import datetime
import logging
from autumn.goods import img_url
from autumn.ktv import build_taobao_sku


class Show(BaseHandler):
    @require('clerk')
    def get(self):
        shops = self.db.query('select * from supplier_shop where supplier_id = %s', self.current_user.supplier_id)
        products = self.db.query('select * from ktv_product where supplier_id = %s', self.current_user.supplier_id)

        d = {}
        # shop_id 如果是银乐迪，指定为31， 否则默认是券生活8的id(13)
        shop_id = {629: 31}.get(self.current_user.supplier_id, options.shop_id_taobao)
        data = self.db.query('select kpg.*, gds.distributor_goods_id from ktv_product_goods kpg left join '
                             'goods_distributor_shop gds on kpg.goods_id = gds.goods_id where gds.deleted = 0 '
                             'and gds.distributor_shop_id = %s and gds.status = "PENDING"', shop_id)
        for item in data:
            d[str(item.shop_id) + str(item.product_id)] = [item.goods_id, item.distributor_goods_id]

        self.render('ktv/manage/show.html', shops=shops, products=products, d=d)


class Publish(BaseHandler):
    @require('clerk')
    @tornado.gen.coroutine
    def get(self):
        shop_id = self.get_argument('shop_id')
        product_id = self.get_argument('product_id')
        product_name = self.get_argument('product_name')

        shop = self.db.get('select name from supplier_shop where id = %s', shop_id)

        taobao_sku_list = build_taobao_sku(self.db, shop_id, product_id)
        title = shop.name + '－' + product_name.encode('utf-8')

        app_info = json.loads(self.db.get('select taobao_api_info from distributor_shop where id = %s',
                              options.shop_id_taobao).taobao_api_info, object_hook=json_hook)
        attribute_request = Taobao('taobao.itemprops.get')
        attribute_request.set_app_info(app_info.app_key, app_info.app_secret_key)
        attribute_request.set_session(app_info.session)
        response = yield attribute_request(cid=50644003, fields='pid,name,must,multi,prop_values,is_input_prop,features')
        attribute_request.parse_response(response.body)

        if attribute_request.is_ok() and 'item_props' in attribute_request.message:
            if 'item_prop' in attribute_request.message.item_props:
                attributes = attribute_request.message.item_props.item_prop
            else:
                attributes = []
        else:
            attributes = []

        self.render('ktv/manage/publish.html', taobao_sku_list=taobao_sku_list, title=title, shop_id=shop_id,
                    product_id=product_id, attributes=json_dumps(attributes))

    @require('finance')
    @tornado.gen.coroutine
    def post(self):
        params = dict([(name, self.get_argument(name).encode('utf-8')) for name in self.request.arguments])

        #判断是否存在对应的商品，如果没有则添加
        goods = self.db.get('select goods_id from ktv_product_goods where product_id = %s and shop_id = %s',
                            params['product_id'], params['shop_id'])
        shop = self.db.get('select * from supplier_shop where id = %s', params['shop_id'])
        product = self.db.get('select * from ktv_product where id = %s', params['product_id'])
        taobao_sku_list = build_taobao_sku(self.db, shop.id, product.id)

        props = ''
        if 'attr-name' in self.request.arguments:
            for pid in self.request.arguments['attr-name']:
                if pid in self.request.arguments:
                    for i in self.request.arguments[pid]:
                        props += pid + ':' + i + ';'

        if not goods:
            shop_name = self.db.get('select name from supplier_shop where id = %s', params['shop_id'])['name']
            sql = """insert into goods(supplier_id, sales_price, face_value, purchase_price, category_id, name,
                     short_name, sms_name, created_at, expire_at, type, detail, created_by, generate_type, all_shop)
                     values(%s, 1, 1, 1, 1021, %s, %s, %s, NOW(), NOW(), 'E', 'ktv产品', %s, 'GENERATE', 0)"""
            combo = shop_name + product['name']
            param = [self.current_user.supplier_id, combo, combo, combo, self.current_user.name]
            goods_id = self.db.execute(sql, *param)
            self.db.execute('insert into goods_property(goods_id, name, value) values(%s, "ktv", 1)', goods_id)
            self.db.execute('insert into goods_property(goods_id, name, value) values(%s, "hidden", 1)', goods_id)
            self.db.execute('insert into ktv_product_goods(shop_id, product_id, goods_id, created_at) '
                            'values(%s, %s, %s, NOW())', params['shop_id'], params['product_id'], goods_id)
            self.db.execute('insert into goods_supplier_shop(goods_id,supplier_shop_id) values(%s, %s)', goods, shop.id)
        else:
            goods_id = goods.goods_id

        # shop_id 如果是银乐迪，指定为31， 否则默认是券生活8的id(13)
        shop_id = {629: 31}.get(self.current_user.supplier_id, options.shop_id_taobao)
        dg = alloc_distributor_goods(self.db, goods_id, shop_id)
        outer_id = str(dg.goods_link_id)

        sku_properties = []
        sku_quantities = []
        sku_prices = []
        sku_outer_ids = []
        props_set = []

        goods_number = 0
        min_price = 100000
        max_price = 0
        room_type_taobao_info = {'MINI': '27426219:6312905', 'SMALL': '27426219:3442354', 'MIDDLE': '27426219:6769368',
                                 'LARGE': '27426219:3374388', 'DELUXE': '27426219:40867986'}

        for taobao_sku in taobao_sku_list:
            sku_properties.append(get_taobao_propertities(taobao_sku))
            sku_quantities.append(taobao_sku.quantity)
            sku_prices.append(taobao_sku.price)
            sku_outer_ids.append(get_taobao_outer_id(taobao_sku))
            for i in sku_quantities:
                goods_number += i
            props_set = remove_repeat(props_set, room_type_taobao_info[taobao_sku.room_type])
            if taobao_sku.price < min_price:
                min_price = taobao_sku.price
            if taobao_sku.price > max_price:
                max_price = taobao_sku.price

        props += ';'.join(props_set)
        sku_properties_str = ','.join(sku_properties)
        # sku_properties_str = sku_properties_str.encode('utf-8')
        sku_quantities_str = ','.join([str(i) for i in sku_quantities]).encode('utf-8')
        sku_prices_str = ','.join([str(i) for i in sku_prices]).encode('utf-8')
        sku_outer_ids_str = ','.join(sku_outer_ids).encode('utf-8')

        input_pid = []
        input_s = []
        # props += self.get_argument('face_value') + ':' + str(int(max_price) * 1.5) + ';'

        # 增加品牌、省份、城市属性
        props += ';' + params['ktv_brand'] + ':' + params['brand'] + ';'
        ktv_province = self.request.arguments['ktv_provinces']
        for province_item in ktv_province:
            props += params['ktv_province'] + ':' + province_item + ';'

        ktv_cities = self.request.arguments['ktv_cities']
        for city_item in ktv_cities:
            props += params['ktv_city'] + ':' + city_item + ';'

        merchant = params['merchant']

        input_pid.append(self.get_argument('face_value'))
        input_s.append(str(int(int(max_price) * 1.5)))
        input_pids = ','.join(input_pid).encode('utf-8')
        input_str = ','.join(input_s).encode('utf-8')

        app_info = json.loads(self.db.get('select taobao_api_info from distributor_shop where id = %s',
                              options.shop_id_taobao).taobao_api_info, object_hook=json_hook)
        goods_push = Taobao('taobao.item.add')
        goods_push.set_app_info(app_info.app_key, app_info.app_secret_key)
        goods_push.set_session(app_info.session)
        publish = self.get_argument('publish', 0)
        image = img_url(params['img_url'])
        # image = 'http://img0.bdstatic.com/img/image/9196a600c338744ebf8e350016bdbf9d72a6059a745.jpg'
        if publish:
            approve_status = 'onsale'
        else:
            approve_status = 'instock'

        args = {
            'num': goods_number,
            'price': min_price,
            'type': 'fixed',
            'image': image,
            'stuff_status': 'news',
            'title': params['title'],
            'location__state': params['location_state'],
            'location__city': params['location_city'],
            'cid': 50644003,
            'approve_status': approve_status,
            'desc': params['desc'],
            'props': props,
            'sku_properties': sku_properties_str,
            'sku_quantities': sku_quantities_str,
            'sku_prices': sku_prices_str,
            'sku_outer_ids': sku_outer_ids_str,
            'input_pids': input_pids,
            'input_str': input_str,
            'outer_id': outer_id,
            'locality_life__merchant': merchant,
            'locality_life__choose_logis': '0',
            'locality_life__expirydate': '30',
            'locality_life__onsale_auto_refund_ratio': 100
        }

        response = yield goods_push(**args)
        goods_push.parse_response(response.body)
        if goods_push.is_ok():
            message = '发布成功'
            self.db.execute('update goods_distributor_shop set status="PENDING", created_by=%s, created_at=NOW(), '
                            'distributor_goods_id = %s where goods_id=%s and distributor_shop_id=%s and '
                            'goods_link_id=%s', self.current_user.name, goods_push.message.item.num_iid, goods_id,
                            shop_id, dg.goods_link_id)
        else:
            err_msg = goods_push.error.sub_msg if 'sub_msg' in goods_push.error else goods_push.error.msg
            message = '发布失败：' + err_msg.encode('utf-8')

        self.render('ktv/manage/result.html', message=message)


class Delete(BaseHandler):
    @require('finance')
    @tornado.gen.coroutine
    def post(self):
        distributor_goods_id = self.get_argument('distributor_goods_id')
        #删除淘宝上的商品
        is_exist = self.db.get('select * from goods_distributor_shop g where g.distributor_goods_id = %s '
                               'and g.deleted = 0 and distributor_shop_id = %s limit 1', distributor_goods_id, 1)
        if not is_exist:
            self.render('ktv/manage/result.html', message='没有对应的商品可以删除')

        logging.info('delete distributer_goods_id: %s' % distributor_goods_id)

        app_info = json.loads(self.db.get('select taobao_api_info from distributor_shop where id = %s',
                              options.shop_id_taobao).taobao_api_info, object_hook=json_hook)
        goods_delete = Taobao('taobao.item.delete')
        goods_delete.set_app_info(app_info.app_key, app_info.app_secret_key)
        goods_delete.set_session(app_info.session)
        response = yield goods_delete(num_iid=distributor_goods_id)
        goods_delete.parse_response(response.body)

        if goods_delete.is_ok():
            self.db.execute('update goods_distributor_shop set deleted = 1 where distributor_goods_id = %s and '
                            'distributor_shop_id = 1 and deleted = 0', distributor_goods_id)
        else:
            self.render('ktv/manage/result.html', message='在淘宝上删除商品失败')

        self.redirect(self.reverse_url('ktv.show'))


def sort_start_time(str):
        temp_time = [int(i) for i in str.split(',')]
        temp_time.sort()
        return temp_time


def remove_repeat(list_type, data):
    temp = list_type
    temp.append(data)
    temp = set(temp)
    temp = list(temp)
    return temp


def time_add(dt, number):
    return string_to_datetime(dt) + datetime.timedelta(number)


def string_to_datetime(str):
    return datetime.datetime.fromtimestamp(time.mktime(time.strptime(str, '%Y-%m-%d')))


#要求day1和day2都是datetime格式。前者小返回0，否则返回为非0
def big_time(day1, day2):
    return day1 > day2


def get_taobao_propertities(taobao_sku):
    room_type_taobao_info = {'MINI': '27426219:6312905', 'SMALL': '27426219:3442354', 'MIDDLE': '27426219:6769368',
                             'LARGE': '27426219:3374388', 'DELUXE': '27426219:40867986'}

    info_str = room_type_taobao_info[taobao_sku.room_type] + ';$欢唱时间:' + taobao_sku.human_time_range + \
               ';$日期:' + taobao_sku.human_date

    return info_str


def date_to_china_date(start_time, end_time):
    end_time = end_time if end_time < 24 else end_time - 24
    start_str = u'凌晨' + str(start_time) + u'点' if start_time < 6 else str(start_time) + u'点'
    end_str = u'凌晨' + str(end_time) + u'点' if end_time < 6 else str(end_time) + u'点'

    return start_str + u'至' + end_str


def get_taobao_outer_id(taobao_sku):
    end = taobao_sku.start_time + taobao_sku.duration
    end = end - 24 if end >= 24 else end
    temp_str = taobao_sku.room_type + taobao_sku.date.strftime('%Y%m%d') + str(taobao_sku.start_time*100+end)

    return temp_str