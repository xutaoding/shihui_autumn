# -*- coding: utf-8 -*-
from datetime import datetime
import json
from collections import OrderedDict

from .. import BaseHandler
from .. import require
from autumn import const


class OrderSkuList(BaseHandler):
    @require()
    def get(self):
        # 查询实物待发货要出库的货品的订单明细
        # order_item_skus = self.db.query(
        #     """select distinct ri.order_id,oi.id item_id,oi.id order_item_id, ri.order_no,g.short_name goods_name,
        #     sk.name sku_name, sk.price sku_price,sk.id sku_id,
        #     sg.num*(oi.num-( select count(r.id) from `item` r where r.order_item_id=oi.id
        #     and r.goods_id=g.id and r.status in (%s,%s) )) sku_out_num, do.order_no wb_order_no
        #     from order_item oi,item ri,distributor_order do,goods g,sku_goods sg,sku sk,goods_property gp
        #     where oi.id=ri.order_item_id and ri.distr_id=do.id and oi.goods_id = g.id and ri.goods_id=g.id
        #     and sg.goods_id = g.id and sg.sku_id = sk.id and gp.goods_id = g.id
        #     and g.type = 'R'  and gp.name = 'sku' and gp.value = 1 and ri.status = %s
        #     and ri.created_at <= now()""", const.status.REFUND, const.status.RETURNING, const.status.BUY)
        sql = """select distinct ri.order_id, oi.id item_id, oi.id order_item_id, ri.order_no, g.short_name goods_name,
                   sku.name sku_name, sku.price sku_price, sku.id sku_id, do.order_no wb_order_no,
                   sg.num * (oi.num - ( select count(r.id) from item r where r.order_item_id = oi.id and
                   r.status in (%s, %s))) sku_out_num
                 from order_item oi, item ri, distributor_order do, goods g, sku_goods sg, sku, goods_property gp
                 where oi.id = ri.order_item_id and ri.order_id = do.order_id and oi.goods_id = g.id and
                   ri.goods_id = g.id and sg.goods_id = g.id and sg.sku_id = sku.id and gp.goods_id = g.id and
                   g.type = 'R' and gp.name = 'sku' and gp.value = 1 and ri.status = %s and ri.created_at <= NOW()"""
        order_item_skus = self.db.query(sql, const.status.REFUND, const.status.RETURNING, const.status.BUY)
        sku_ids = set()
        order_items = OrderedDict()
        for item in order_item_skus:
            if item.order_id not in order_items:
                order_items[item.order_id] = []
            order_items[item.order_id].append(item)
            sku_ids.add(item.sku_id)

        # 查询实物需发货的货品明细
        out_skus = []
        if sku_ids:
            out_skus = self.db.query(
                'select id, name, price, stock from sku where id in (%s)' % ','.join(['%s']*len(sku_ids)), *list(sku_ids))

        # 查询是否有等待审批的出库货品
        stock_batches = self.db.query('select * from stock_batch where type = %s and status = %s', 'OUT', 'APPLIED_OUT')

        self.render('real/order_sku_list.html', order_items=order_items, out_skus=out_skus, stock_batches=stock_batches)

    @require('storage')
    def post(self):
        order_items = self.get_argument('item_result')
        order_items_obj = json.loads(order_items)
        order_item_ids = [str(i['order_item_id']) for i in order_items_obj]
        order_ids = set([str(i['order_id']) for i in order_items_obj])
        if order_item_ids:
            #更新对应real_item的状态
            self.db.execute(
                'update item i,goods g set i.status = %s where g.id=i.goods_id and g.type ="R" '
                'and i.status <> %s and i.status <> %s and '
                'i.order_item_id in (%s) ' % ('%s', '%s', '%s', ','.join(['%s'] * len(order_item_ids))),
                const.status.WAIT_TO_SEND, const.status.REFUND, const.status.RETURNING, *order_item_ids)

            skus = self.get_argument('sku_result')
            # 统计要出库的订单数
            order_item = self.db.get('select count(distinct order_id) count from order_item where id in (%s) '
                                     % ','.join(['%s'] * len(order_item_ids)), *order_item_ids)
            self.db.execute(
                'insert into stock_batch (order_info,sku_info,type,status,created_at,created_by,order_count)'
                'values (%s,%s,%s,%s,now(),%s,%s)',
                order_items, skus, 'OUT', 'APPLIED_OUT', self.current_user.name, order_item.count)

            for order_id in order_ids:
                #申请出库日志
                self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                                'values (NOW(), 1, %s, %s, %s)',
                                self.current_user.name, "订单申请出库,订单ID:%s" % order_id, order_id)

        self.redirect(self.reverse_url('real.order_sku_list'))
