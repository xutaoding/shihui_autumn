# -*- coding: utf-8 -*-
import json
import logging
import torndb

from conf import load_app_options
from datetime import datetime
from autumn.api import Yihaodian
from autumn.api import Taobao
from autumn.api import Wuba
from autumn.api import Jingdong
from autumn.utils import json_hook
from tornado.options import options


def sync_tb(db, step):
    goods = db.query('select gds.id,gds.status,gds.distributor_goods_id '
                     'from goods_distributor_shop gds, distributor_shop ds '
                     'where gds.distributor_shop_id=ds.id and gds.status <> "PREPARE" and gds.deleted=0 '
                     'and gds.distributor_goods_id <> "" and ds.distributor_id=%s', options.distributor_id_taobao)
    goods_dict = dict([(int(g.distributor_goods_id), g) for g in goods])
    api_info = db.get('select taobao_api_info from distributor_shop where id=%s', options.shop_id_tmall)
    api_info = json.loads(api_info.taobao_api_info, object_hook=json_hook)

    goods_slice = [goods[i:i+step] for i in range(0, len(goods), step)]
    for slc in goods_slice:
        taobao = Taobao('taobao.items.list.get')
        taobao.set_app_info(api_info.app_key, api_info.app_secret_key)
        response = taobao.sync_fetch(fields='num_iid,approve_status',
                                     num_iids=','.join(map(str, [s.distributor_goods_id for s in slc])))
        taobao.parse_response(response)
        if not taobao.is_ok():
            logging.error('sync goods status. taobao request error %s', taobao.error)
            continue

        if len(taobao.message['items'].item) < len(slc):
            # 有商品已被删除
            slc_id_set = set([s.distributor_goods_id for s in slc])
            num_iid_set = set([str(i.num_iid) for i in taobao.message['items'].item])
            deleted_ids = slc_id_set-num_iid_set
            db.execute('update goods_distributor_shop gds, distributor_shop ds '
                       'set gds.deleted="1", gds.deleted_at=NOW() '
                       'where gds.distributor_shop_id=ds.id and ds.distributor_id=%%s '
                       'and gds.distributor_goods_id in (%s)' % ','.join(['%s']*len(deleted_ids)),
                       options.distributor_id_taobao, *list(deleted_ids))
            logging.info('sync goods status. delete taobao item %s', ','.join(deleted_ids))

        for item in taobao.message['items'].item:
            g = goods_dict[item.num_iid]
            if item.approve_status == 'instock' and g.status != 'OFF_SALE':
                # 下架
                db.execute('update goods_distributor_shop gds, distributor_shop ds '
                           'set gds.status="OFF_SALE", gds.offsale_at=NOW(), gds.onsale_at=NULL '
                           'where gds.distributor_shop_id=ds.id and ds.distributor_id=%s '
                           'and gds.distributor_goods_id=%s',
                           options.distributor_id_taobao, g.distributor_goods_id)
                logging.info('sync goods status. offsale taobao item %s', g.distributor_goods_id)

            elif item.approve_status == 'onsale' and g.status != 'ON_SALE':
                # 上架
                db.execute('update goods_distributor_shop gds, distributor_shop ds '
                           'set gds.status="ON_SALE", gds.onsale_at=NOW(), gds.offsale_at=NULL '
                           'where gds.distributor_shop_id=ds.id and ds.distributor_id=%s '
                           'and gds.distributor_goods_id=%s',
                           options.distributor_id_taobao, g.distributor_goods_id)
                logging.info('sync goods status. onsale taobao item %s', g.distributor_goods_id)


def sync_yhd(db, step):
    goods = db.query('select gds.id,gds.status,gds.goods_link_id from goods_distributor_shop gds, distributor_shop ds '
                     'where gds.distributor_shop_id=ds.id and gds.status <> "PREPARE" and gds.deleted=0 '
                     'and gds.distributor_goods_id <> "" and ds.distributor_id=%s', options.distributor_id_yihaodian)
    goods_dict = dict([(g.goods_link_id, g) for g in goods])

    goods_slice = [goods[i:i+step] for i in range(0, len(goods), step)]
    for slc in goods_slice:
        yhd = Yihaodian('yhd.general.products.search')
        response = yhd.sync_fetch(outerIdList=','.join(map(str, [s.goods_link_id for s in slc])))
        yhd.parse_response(response)
        if not yhd.is_ok():
            logging.error('sync goods status. yihaodian request error %s', response)
            continue
        for product in yhd.message.findall('productList/product'):
            g = goods_dict[int(product.findtext('outerId'))]
            can_sale = product.findtext('canSale')
            if can_sale == '0' and g.status != 'OFF_SALE':
                db.execute('update goods_distributor_shop set status="OFF_SALE", offsale_at=NOW(), onsale_at=NULL '
                           'where distributor_shop_id=%s and goods_link_id=%s',
                           options.shop_id_yihaodian, g.goods_link_id)
                logging.info('sync goods status. offsale yihaodian item %s', g.goods_link_id)
            elif can_sale == '1' and g.status != 'ON_SALE':
                db.execute('update goods_distributor_shop set status="ON_SALE", onsale_at=NOW(), offsale_at=NULL '
                           'where distributor_shop_id=%s and goods_link_id=%s',
                           options.shop_id_yihaodian, g.goods_link_id)
                logging.info('sync goods status. onsale yihaodian item %s', g.goods_link_id)


def sync_58(db, step):
    goods = db.query('select gds.id,gds.status,gds.goods_link_id from goods_distributor_shop gds, distributor_shop ds '
                     'where gds.distributor_shop_id=ds.id and gds.status <> "PREPARE" and gds.deleted=0 '
                     'and gds.distributor_goods_id <> "" and ds.distributor_id=%s', options.distributor_id_wuba)
    goods_dict = dict([(g.goods_link_id, g) for g in goods])

    goods_slice = [goods[i:i+step] for i in range(0, len(goods), step)]
    for slc in goods_slice:
        wuba = Wuba('getstatus')
        response = wuba.sync_fetch(groupbuyIds=','.join(map(str, [s.goods_link_id for s in slc])))
        # response = wuba.sync_fetch(groupbuyIds='34841', status='-1')
        wuba.parse_response(response)
        if not wuba.is_ok():
            logging.error('sync goods status. wuba request error %s', response)
            continue
        for product in wuba.message.findall('productList/product'):
            g = goods_dict[product.groupbuyIdThirdpart]
            if product.status != 0 and g.status != 'OFF_SALE':
                db.execute('update goods_distributor_shop set status="OFF_SALE", offsale_at=NOW(), onsale_at=NULL '
                           'where distributor_shop_id=%s and goods_link_id=%s',
                           options.shop_id_wuba, g.goods_link_id)
                logging.info('sync goods status. offsale wuba item %s', g.goods_link_id)
            elif product.status == 0 and g.status != 'ON_SALE':
                db.execute('update goods_distributor_shop set status="ON_SALE", onsale_at=NOW(), offsale_at=NULL '
                           'where distributor_shop_id=%s and goods_link_id=%s',
                           options.shop_id_wuba, g.goods_link_id)
                logging.info('sync goods status. onsale wuba item %s', g.goods_link_id)


def sync_jd(db):
    goods = db.query('select gds.id,gds.status,gds.distributor_goods_id,'
                     'gds.goods_link_id,ds.taobao_api_info,ds.taobao_seller_id '
                     'from goods_distributor_shop gds, distributor_shop ds '
                     'where gds.distributor_shop_id=ds.id and gds.status <> "PREPARE" and gds.deleted=0 '
                     'and gds.distributor_goods_id <> "" and ds.distributor_id=%s', options.distributor_id_jingdong)
    now = datetime.now()
    for g in goods:
        api_info = json.loads(g.taobao_api_info, object_hook=json_hook)
        jingdong = Jingdong('queryTeamInfo', str(g.taobao_seller_id), api_info.vender_key, api_info.secret_key)
        response = jingdong.sync_fetch(vender_team_id=g.goods_link_id, jd_team_id=g.distributor_goods_id)
        jingdong.parse_response(response)
        if not jingdong.is_ok():
            if jingdong.result_code == '-538':
                db.execute('update goods_distributor_shop set deleted="1", deleted_at=NOW() '
                           'where id=%s', g.id)
                logging.info('sync goods status. delete jingdong item %s', g.distributor_goods_id)
            else:
                logging.error('sync goods status. jingdong request error %s', response)
            continue
        end_time = datetime.fromtimestamp(int(jingdong.message.findtext('EndTime')))
        if end_time < now and g.status != 'OFF_SALE':
            db.execute('update goods_distributor_shop set status="OFF_SALE", offsale_at=NOW(), onsale_at=NULL '
                       'where id=%s', g.id)
            logging.info('sync goods status. offsale jingdong item %s', g.distributor_goods_id)
        elif end_time > now and g.status != 'ON_SALE':
            db.execute('update goods_distributor_shop set status="ON_SALE", onsale_at=NOW(), offsale_at=NULL '
                       'where id=%s', g.id)
            logging.info('sync goods status. onsale jingdong item %s', g.distributor_goods_id)

if __name__ == '__main__':
    load_app_options()
    logging.basicConfig(level=logging.INFO,
                        format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')
    mysql_db = torndb.Connection(
        host=options.mysql_host, database=options.mysql_database,
        user=options.mysql_user, password=options.mysql_password)

    logging.info('start sync goods status')
    sync_tb(mysql_db, 20)
    sync_yhd(mysql_db, 20)
    # sync_58(mysql_db, 50)
    sync_jd(mysql_db)

    mysql_db.close()
