# -*- coding: utf-8 -*-

import torndb
import logging
from conf import load_app_options
from tornado.options import options
import json
from autumn.utils import json_hook

from autumn.api.taobao import Taobao
from autumn.api.jingdong import Jingdong
from autumn.api.wuba import Wuba
from tornado.gen import coroutine
from tornado.ioloop import IOLoop

# 加载配置
load_app_options()

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')

# 配置连接
db = torndb.Connection(
    host=options.mysql_host, database=options.mysql_database,
    user=options.mysql_user, password=options.mysql_password)


@coroutine
def sync_stock():
    sql = """
        select g.id, gds.distributor_shop_id, gds.distributor_goods_id, gds.goods_link_id, g.stock, ds.taobao_api_info,
        ds.distributor_id
        from goods g, distributor_shop ds, goods_distributor_shop gds where g.id = gds.goods_id
        and gds.distributor_shop_id = ds.id
        and g.generate_type = 'IMPORT' and gds.deleted = '0'
            and gds.distributor_shop_id in (%s, %s, %s, %s) """

    params = [options.shop_id_taobao, options.shop_id_tmall, options.shop_id_jingdong,  options.shop_id_wuba]
    sync_list = db.query(sql, *params)

    for item in sync_list:
        if not item.distributor_goods_id or item.distributor_goods_id == '0':
            logging.error('商品找不到对应的外部id.商品id: %s', item.id)
            continue

        if item.distributor_shop_id in (options.shop_id_taobao, options.shop_id_tmall):
            if not item.taobao_api_info:
                logging.error('商品没有对应的taobao_api_info.商品id: %s', item.id)
                continue

            app_info = json.loads(item.taobao_api_info, object_hook=json_hook)
            # 获取店铺类型
            request = Taobao('taobao.item.quantity.update')
            request.set_app_info(app_info.app_key, app_info.app_secret_key)
            request.set_session(app_info.session)

            args = {
                'num_iid': item.distributor_goods_id,
                'quantity': item.stock,
                'type': 1
            }
            response = yield request(**args)
            request.parse_response(response.body)

            if request.is_ok():
                logging.info('商品id: %s在 %s上更新库存成功，更新为%s', item.id,
                             {options.shop_id_tmall: '天猫', options.shop_id_taobao: '淘宝'}.get(item.distributor_shop_id),
                             item.stock)
            else:
                logging.info('商品id: %s在 %s上更新库存失败', item.id,
                             {options.shop_id_tmall: '天猫', options.shop_id_taobao: '淘宝'}.get(item.distributor_shop_id))

        elif item.distributor_id == options.distributor_id_jingdong:
            args = {
                'vender_team_id': item.goods_link_id,
                'jd_team_id': item.distributor_goods_id,
                'max_number': item.stock
            }

            shop = db.get('select taobao_seller_id, taobao_api_info from distributor_shop where id=%s',
                          item.distributor_shop_id)
            api_info = json.loads(shop.taobao_api_info, object_hook=json_hook)

            jd_push = Jingdong('updateMaxNumber', str(shop.taobao_seller_id), api_info.vender_key, api_info.secret_key)

            response = yield jd_push.fetch(**args)
            jd_push.parse_response(response.body)

            if jd_push.is_ok():
                logging.info('商品id: %s在京东上更新库存成功，更新为%s', item.id, item.stock)
            else:
                logging.info('商品id: %s在京东上更新库存失败', item.id)

        elif item.distributor_shop_id == options.shop_id_wuba:
            args = {
                'groupbuyId': item.goods_link_id,
                'num': item.stock
            }

            wuba = Wuba('changeinventory')
            response = yield wuba.fetch(**args)
            wuba.parse_response(response.body)

            if wuba.is_ok():
                logging.info('商品id: %s在58上更新库存成功，更新为%s', item.id, item.stock)
            else:
                logging.info('商品id: %s在58上更新库存失败', item.id)

        else:
            pass

IOLoop.instance().run_sync(sync_stock)