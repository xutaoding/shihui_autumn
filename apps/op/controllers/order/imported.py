# -*- coding: utf-8 -*-
from .. import BaseHandler, require
from tornado.options import options
import xlrd
from autumn.order import new_distributor_order, new_distributor_item
from autumn.utils import json_dumps
from datetime import datetime, timedelta


class OuterOrder(BaseHandler):
    @require()
    def get(self):
        """ 导入外部订单展示页面 """
        self.render('order/import_outer_order.html', message='')

    @require('finance')
    def post(self):
        """ 开始导入"""
        if not self.request.files:
            self.render('real/import_outer_order.html', message=u'请选择文件')

         #读取文件
        order_file = self.request.files['order_file'][0]
        book = xlrd.open_workbook(file_contents=order_file['body'])
        try:
            sheet = book.sheet_by_index(0)
        except:
            self.render('real/import_outer_order.html', message=u'文件格式错误，请检查')
            return
        partner = self.get_argument('partner').lower()
        distributor_shop_id = {'dp': 40, 'mt': 44, 'ls': '45', 'nm': 42, 'ww': 37}.get(partner)
        #读取工作表的所有行数据内容
        rows = [sheet.row_values(i) for i in range(1, sheet.nrows)]
        #转换数据
        col_names = ('coupon_sn', 'goods_id')
        coupon_list = [dict([(col_names[i], row[i]) for i in range(len(col_names))]) for row in rows]
        existed_orders = []
        need_convert_orders = []
        goods_id = -1
        for order in coupon_list:
            current_goods_id = order['goods_id']
            if goods_id != current_goods_id:
                goods_id = current_goods_id
                goods_info = self.db.get('select g.* ,ss.id shop_id from goods g,supplier_shop ss ,supplier s '
                                         'where ss.deleted=0 and s.id=ss.supplier_id and s.id=g.supplier_id '
                                         'and g.id=%s limit 1', goods_id)
            verify_infos = {'goods_id': goods_id, 'shop_id': goods_info.shop_id}
            if isinstance(order['coupon_sn'], int) or isinstance(order['coupon_sn'], float):
                need_convert_orders.append(str(order['coupon_sn']))
                continue

            #判断是不是已经导入过的外部订单
            distributor_order = self.db.get('select * from distributor_order where distributor_shop_id=%s and '
                                            'order_no=%s', distributor_shop_id, order['coupon_sn'])
            if distributor_order:
                existed_orders.append(str(order['coupon_sn']))
                continue

            created_at = datetime.now() - timedelta(days=1)
            #创建分销订单
            distributor_order_id = self.db.execute(
                'insert into distributor_order(order_no, message, distributor_shop_id, created_at) '
                'values (%s, %s, %s, %s)', order['coupon_sn'], json_dumps(verify_infos), distributor_shop_id, created_at)
            order_id, order_no = new_distributor_order(self.db, distributor_shop_id,
                                                       goods_info.sales_price, goods_info.sales_price, "")
            # 改时间
            self.db.execute('update orders set created_at=%s, paid_at=%s where id=%s', created_at, created_at, order_id)
            self.db.execute('update journal set created_at=%s where type=1 and iid=%s', created_at, order_id)

            #记录订单信息
            new_order = new_distributor_item(
                db=self.db,
                order_id=order_id,
                order_no=order_no,
                sales_price=None,
                count=1,
                goods_info=goods_info,
                mobile='',
                distributor_shop_id=distributor_shop_id,
                distributor_goods_id='',
                distributor_coupons=[{'coupon_sn': order['coupon_sn'], 'coupon_pwd': ''}],
                use_distributor_coupon=True
            )
            if new_order.ok:
                #更新分销订单id
                self.db.execute('update orders set distributor_order_id=%s where id = %s',
                                distributor_order_id, order_id)
                #更新订单id
                self.db.execute('update distributor_order set order_id=%s where id=%s',
                                order_id, distributor_order_id)
                #更新该券验证的门店
                self.db.execute('update item set sp_shop_id = %s where order_id=%s', goods_info.shop_id, order_id)
                #设定时间为前一天
                self.db.execute('update item set created_at=%s where order_id=%s', created_at, order_id)
                #自动验证
                self.redis.lpush(options.queue_coupon_local_verify, json_dumps({'coupon': order['coupon_sn'],
                                 'shop_id': goods_info.shop_id, 'retry': 0, 'used_at': created_at}))

        self.render('order/import_outer_order.html', message='success', existed_orders=existed_orders,
                    need_convert_orders=need_convert_orders)
