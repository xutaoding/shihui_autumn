# -*- coding: utf-8 -*-
import logging
from tornado.options import options

from conf import load_app_options
import torndb
from autumn.api import Yihaodian


def fetch(db, step):
    link_id_list = db.query('select goods_link_id from goods_distributor_shop where distributor_shop_id=%s '
                            'and distributor_goods_id="" and status <> "PREPARE" and deleted=0',
                            options.shop_id_yihaodian)

    link_id_slice = [[link.goods_link_id for link in link_id_list[i:i+step]] for i in range(0, len(link_id_list), step)]
    for links in link_id_slice:
        yhd = Yihaodian('yhd.general.products.search')
        response = yhd.sync_fetch(outerIdList=','.join(map(str, links)))
        yhd.parse_response(response)
        if yhd.is_ok():
            yhd_products = yhd.message.findall('productList/product')
            for yhd_product in yhd_products:
                outer_id = yhd_product.findtext('outerId')
                url = yhd_product.findtext('prodDetailUrl')
                goods_code = yhd_product.findtext('productCode')
                db.execute('update goods_distributor_shop set distributor_goods_id=%s, extra=%s '
                           'where distributor_shop_id=%s and goods_link_id=%s',
                           goods_code, url, options.shop_id_yihaodian, outer_id)
        else:
            logging.error('fetch yihaodian goods_id failed. %s %s', yhd.get_field('outerIdList'), response)


if __name__ == '__main__':
    load_app_options()
    logging.basicConfig(level=logging.INFO,
                        format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')
    mysql_db = torndb.Connection(
        host=options.mysql_host, database=options.mysql_database,
        user=options.mysql_user, password=options.mysql_password)

    logging.info('start fetch yihaodian goods_id')
    fetch(mysql_db, 1)  # 每次请求一个

    mysql_db.close()
