# -*- coding: utf-8 -*-

from .. import BaseHandler
from autumn.utils import json_dumps
from tornado.options import options
import time
from autumn.goods import img_url


class List(BaseHandler):
    def get(self):
        sql = """select g.id, g.short_name, g.created_at, g.purchase_price, g.sales_price, g.img_path, g.face_value
                 from goods g join goods_category gc on g.category_id = gc.id
                 where g.off_sale_at > NOW() and g.deleted = 0
                 and g.id not in (select goods_id from ktv_product_goods
                                  union select gpp.goods_id from goods_property gpp where gpp.name = 'hidden' and gpp.value = 1
                                  union select gq.goods_id from goods_property gq where gq.name = 'recommend' and gq.value = 1)
                 and g.id in (select goods_id from goods_distributor_shop where distributor_shop_id in (%s, %s, %s, %s)
                              and deleted = 0 and distributor_goods_id <> '')
              """

        recommend_sql = """select distinct(g.id), g.short_name, g.created_at, g.purchase_price, g.sales_price, g.img_path, g.face_value
                           from goods g
                           join (select gpp.goods_id from goods_property gpp where gpp.name = 'recommend' and gpp.value = 1 and gpp.goods_id not in
                                (select gq.goods_id from goods_property gq where gq.name='hidden' and gq.value = 1)) gp on gp.goods_id = g.id
                           join goods_category gc on g.category_id = gc.id
                           where g.off_sale_at > NOW() and g.deleted = 0 and g.id not in (select goods_id from ktv_product_goods)
                           and g.id in (select goods_id from goods_distributor_shop where distributor_goods_id <> ''
                           and deleted = 0 and distributor_shop_id in (%s, %s, %s, %s))
                        """
        params = [options.shop_id_tmall, options.shop_id_taobao, options.shop_id_jingdong, options.shop_id_yihaodian]

        category = self.get_argument('category', '')

        if category != '':
            sql += 'and gc.parent_id = %s '
            recommend_sql += 'and gc.parent_id = %s '
            params.append(category)

        sql1 = sql
        sql1 += 'order by g.id desc limit 5 '

        sql += 'order by g.sales_count desc limit 10 '

        recommend_sql += 'limit 4'
        recommend_list = self.db.query(recommend_sql, *params)

        goods_list = self.db.query(sql, *params)
        new_goods_list = self.db.query(sql1, *params)

        max_id = self.db.get('select g.id from goods g where g.off_sale_at > NOW() and g.deleted = 0 '
                             'order by id desc limit 1')['id']

        #转化图片地址为图片服务器上的地址
        for goods in goods_list:
            goods.img_path = img_url(goods.img_path)
        for recommend_goods in recommend_list:
            recommend_goods.img_path = img_url(recommend_goods.img_path)
        for new_goods in new_goods_list:
            new_goods.img_path = img_url(new_goods.img_path)

        self.render('index.html', goods_list=goods_list, new_goods_list=new_goods_list, max_id=max_id,
                    category=category, recommend_list=recommend_list)


class Detail(BaseHandler):
    def get(self, goods_id):
        goods = self.db.get('select * from goods where id = %s', goods_id)
        goods.img_path = img_url(goods.img_path)

        distributor_shop_list = self.db.query('select * from goods_distributor_shop where goods_id=%s and deleted=0 '
                                              'order by goods_link_id desc', goods_id)

        shop_order = ((options.shop_id_tmall,       '天猫', 'http://detail.tmall.com/item.htm?id=%s&r=%s'),
                      (options.shop_id_taobao,      '淘宝', 'http://item.taobao.com/item.html?id=%s&r=%s'),
                      (options.shop_id_jingdong,    '京东', 'http://tuan.jd.com/team-%s.html?r=%s'),
                      (options.shop_id_yihaodian,   '一号店', 'http://item.1mall.com/item/%s?r=%s'))

        shop_info = None
        for shop_id, name, url in shop_order:
            found = False
            for shop in distributor_shop_list:
                if shop.distributor_shop_id == shop_id and shop.distributor_goods_id:
                    shop_info = {'name': name, 'url': url % (shop.distributor_goods_id, time.time())}
                    found = True
                    break
            if found:
                break

        supplier_shop_list = self.db.query(
            'select ss.* from supplier_shop ss,goods g where ss.supplier_id=g.supplier_id and g.id=%s and ss.deleted=0 '
            'and (g.all_shop=1 or ss.id in (select supplier_shop_id from goods_supplier_shop where goods_id=%s))',
            goods_id, goods_id)

        category = self.get_argument('category', '')
        self.render('detail.html', goods=goods, shop_info=shop_info, supplier_shop_list=supplier_shop_list,
                    category=category)


class New(BaseHandler):
    def get(self):
        sql = """select g.id, g.img_path, g.face_value, g.sales_price, g.short_name
                 from goods g join goods_category gc on g.category_id = gc.id
                 left join (select gpp.goods_id from goods_property gpp where gpp.name = 'hidden' and gpp.value = 1) gp on g.id <> gp.goods_id
                 where g.off_sale_at > NOW() and g.deleted = 0
                 and g.id in (select goods_id from goods_distributor_shop where distributor_goods_id <> ''
                              and deleted = 0 and distributor_shop_id in (%s, %s, %s, %s))
              """
        params = [options.shop_id_tmall, options.shop_id_taobao, options.shop_id_jingdong, options.shop_id_yihaodian]

        category = self.get_argument('category', '')

        if category != '':
            sql += 'and gc.parent_id = %s '
            params.append(category)

        sql += 'order by g.id desc limit 9 '
        goods_list = self.db.query(sql, *params)

        for goods in goods_list:
            goods.img_path = img_url(goods.img_path)

        self.render('new.html', goods_list=goods_list, category=category)


class Search(BaseHandler):
    def get(self):
        query = self.get_argument('query', '')

        sql = """select id, face_value, sales_price, img_path, short_name from goods
                 where short_name like %s and id not in (select gpp.goods_id from goods_property gpp where gpp.name = "hidden" and gpp.value = 1)
                 order by id desc """

        goods_list = self.db.query(sql, '%' + query + '%')

        for goods in goods_list:
            goods.img_path = img_url(goods.img_path)

        category = self.get_argument('category', '')

        self.render('search.html', goods_list=goods_list, category=category, query=query)


class GoodsAjax(BaseHandler):
    def post(self):
        page_number = self.get_argument('page_number')
        max_id = self.get_argument('max_id')
        category = self.get_argument('category', '')

        begin = int(page_number) * 10 + 1

        sql = """select g.id, g.face_value, g.sales_price, g.img_path, g.short_name
                 from goods g left join goods_category gc on g.category_id = gc.id
                 where g.off_sale_at > NOW() and g.deleted = 0 and g.id <= %s and g.id not in
                 (select goods_id from goods_property where name = 'hidden' and value = 1)
                 and g.id in (select goods_id from goods_distributor_shop where distributor_goods_id <> ''
                              and deleted = 0 and distributor_shop_id in (%s, %s, %s, %s))
              """
        params = [max_id, options.shop_id_tmall, options.shop_id_taobao, options.shop_id_jingdong, options.shop_id_yihaodian]

        if category != '':
            sql += 'and gc.parent_id = %s '
            params.append(category)

        sql += 'order by g.sales_count desc limit %s, 10 '
        params.append(begin)
        goods_list = self.db.query(sql, *params)

        for goods in goods_list:
            goods['img_path'] = img_url(goods.img_path)

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(goods_list))
