# -*- coding: utf-8 -*-

import re
import torndb
import logging
import json
from autumn.api.taobao import Taobao

from decimal import Decimal
from conf import load_app_options
from autumn.utils import json_hook
from tornado.options import define, options
from autumn.ktv import TaobaoSku, diff_local_and_remote, build_taobao_sku

sku_split_re = re.compile(r'[:;]')


def taobao_products(db, iids):
    sql = """ select gds.id gds_id, kpg.product_id, kpg.shop_id, gds.distributor_goods_id,
            ds.taobao_seller_id, ds.taobao_api_info
        from ktv_product_goods kpg, goods_distributor_shop gds, distributor_shop ds
        where kpg.goods_id=gds.goods_id and gds.deleted=0 and gds.distributor_shop_id=ds.id
        and ds.distributor_id=%s """
    params = [options.distributor_id_taobao]
    if iids:
        sql += 'and gds.distributor_goods_id in (%s)' % ','.join(['%s']*len(iids))
        params.extend(iids)
    return db.query(sql, *params)


def sync(db, products):
    for product in products:
        if not product.taobao_api_info:
            logging.error('sync_ktv_sku: invalid taobao_api_info. product_id: %s', product.product_id)
            continue
        taobao_api_info = json.loads(product.taobao_api_info, object_hook=json_hook)

        iid = product.distributor_goods_id
        taobao = Taobao('taobao.item.get')
        taobao.set_app_info(taobao_api_info.app_key, taobao_api_info.app_secret_key)
        response = taobao.sync_fetch(fields='sku', num_iid=iid)
        taobao.parse_response(response)
        if not taobao.is_ok():
            logging.error('sync_ktv_sku: get taobao item info failed. goods_distributor_shop_id: %s', product.gds_id)
            if taobao.error.sub_code == 'isv.item-get-service-error:ITEM_NOT_FOUND':
                #  商品在淘宝不存在，于是在我们系统中设置为逻辑删除
                logging.error('sync_ktv_sku: product not exist. goods_distributor_shop_id: %s', product.gds_id)
                db.execute('update goods_distributor_shop set deleted=1 where id=%s', product.gds_id)
            continue

        local_sku_list = build_taobao_sku(db, product.shop_id, product.product_id)
        remote_sku_list = []
        invalid_skus = []
        if 'skus' in taobao.message.item and 'sku' in taobao.message.item.skus:
            for sku in taobao.message.item.skus.sku:
                tmp = sku_split_re.split(sku.properties_name)
                # 例： 27426219:3442354:包厢房型:小包;-1:-1:欢唱时间:17点至20点;-2:-45:日期:12月11日(周三)
                tb_sku = TaobaoSku(
                    room_type='',
                    dt=None,
                    price=Decimal(sku.price),
                    quantity=sku.quantity,
                    start_time=0,
                    duration=0,
                    sku_id=sku.sku_id
                )
                if len(tmp) != 12:
                    invalid_skus.append(tb_sku)
                    continue
                tb_sku.parse_taobao_property(tmp[3].encode('utf-8'), tmp[7].encode('utf-8'), tmp[11].encode('utf-8'))
                remote_sku_list.append(tb_sku)

        add_sku_list, delete_sku_list, update_price_sku_list, update_quantity_sku_list = diff_local_and_remote(
            local_sku_list, remote_sku_list
        )
        delete_sku_list.extend(invalid_skus)

        remote_price_set = set([sku.price for sku in remote_sku_list])

        for sku in delete_sku_list:
            if sku.price in remote_price_set:
                remote_price_set.remove(sku.price)
            taobao = Taobao('taobao.item.sku.delete')
            taobao.set_app_info(taobao_api_info.app_key, taobao_api_info.app_secret_key)
            taobao.set_session(taobao_api_info.session)
            response = taobao.sync_fetch(
                num_iid=iid,
                properties='%s;$欢唱时间:%s;$日期:%s' % (sku.room_key, sku.human_time_range, sku.human_date),
                item_price=str(min(remote_price_set) if remote_price_set else sku.price)
            )
            taobao.parse_response(response)
            logging.info('sync_ktv_sku: %s DELETE[%s] %s %s', product.gds_id, 'OK' if taobao.is_ok() else 'FAIL',
                         sku, '' if taobao.is_ok() else taobao.error.sub_code.encode('utf-8'))

        for sku in add_sku_list:
            remote_price_set.add(sku.price)
            taobao = Taobao('taobao.item.sku.add')
            taobao.set_app_info(taobao_api_info.app_key, taobao_api_info.app_secret_key)
            taobao.set_session(taobao_api_info.session)

            end = sku.start_time + sku.duration
            end = end - 24 if end >= 24 else end
            response = taobao.sync_fetch(
                num_iid=iid,
                properties='%s;$欢唱时间:%s;$日期:%s' % (sku.room_key, sku.human_time_range, sku.human_date),
                quantity=sku.quantity,
                price=sku.price,
                outer_id=sku.room_type+sku.date.strftime('%Y%m%d')+str(sku.start_time*100+end),
                item_price=str(min(remote_price_set))
            )
            taobao.parse_response(response)
            logging.info('sync_ktv_sku: %s ADD[%s] %s %s', product.gds_id, 'OK' if taobao.is_ok() else 'FAIL',
                         sku, '' if taobao.is_ok() else taobao.error.sub_code.encode('utf-8'))

        if update_quantity_sku_list:
            taobao = Taobao('taobao.skus.quantity.update')
            taobao.set_app_info(taobao_api_info.app_key, taobao_api_info.app_secret_key)
            taobao.set_session(taobao_api_info.session)
            response = taobao.sync_fetch(
                num_iid=iid,
                skuid_quantities=';'.join(['%s:%s' % (sku.sku_id, sku.quantity) for sku in update_quantity_sku_list])
            )
            taobao.parse_response(response)
            logging.info('sync_ktv_sku: UPDATE_QUANTITY[%s] %s', 'OK' if taobao.is_ok() else 'FAIL',
                         taobao.get_field('skuid_quantities'))

        for sku in update_price_sku_list:
            taobao = Taobao('taobao.item.sku.price.update')
            taobao.set_app_info(taobao_api_info.app_key, taobao_api_info.app_secret_key)
            taobao.set_session(taobao_api_info.session)
            response = taobao.sync_fetch(
                num_iid=iid,
                properties='%s;$欢唱时间:%s;$日期:%s' % (sku.room_key, sku.human_time_range, sku.human_date),
                quantity=sku.quantity,
                price=sku.price,
                item_price=sku.price,  # 此处不好确定此时的该商品所有SKU的最低价格，所以就填了当前价格
            )
            taobao.parse_response(response)
            logging.info('sync_ktv_sku: %s UPDATE_PRICE[%s] %s', product.gds_id, 'OK' if taobao.is_ok() else 'FAIL',
                         sku, '' if taobao.is_ok() else taobao.error.sub_code.encode('utf-8'))


def usage():
    print('usage: sku.py --iids=taobaoId,taobaoId2,...')
    print('usage: sku.py')

if __name__ == '__main__':
    define('iids', 'all')
    load_app_options()  # 加载配置
    logging.basicConfig(level=logging.INFO,
                        format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')

    db = torndb.Connection(
        host=options.mysql_host, database=options.mysql_database,
        user=options.mysql_user, password=options.mysql_password)

    if options.iids == 'all':
        products = taobao_products(db, [])
    else:
        products = taobao_products(db, options.iids.split(','))

    logging.info('sync_ktv_sku: start sync %s', ','.join([p.distributor_goods_id for p in products]))
    sync(db, products)
    db.close()
