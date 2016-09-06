# -*- coding: utf-8 -*-
import json
import string

from .. import require
from .. import BaseHandler
from autumn import const


class StockBatchList(BaseHandler):
    @require()
    def get(self):
        # 查询是否有等待审批的出库货品
        stock_batches = self.db.query('select * from stock_batch where type = %s and status = %s', 'OUT', 'APPLIED_OUT')

        self.render('real/stock_batch_list.html', stock_batches=stock_batches)


class StockBatchDetail(BaseHandler):
    @require()
    def get(self, batch_id):
        stock_batch = self.db.get('select * from stock_batch where id = %s', batch_id)
        sku_object = json.loads(stock_batch.sku_info)
        out_skus = []

        for s in sku_object:
            sku = self.db.get('select name,price,stock from sku where id = %s', s['sku_id'])
            sku.out_num = s['out_num']
            out_skus.append(sku)

        self.render('real/stock_batch_detail.html', out_skus=out_skus, batch_id=batch_id)


class StockBatchConfirm(BaseHandler):
    @require('storage')
    def post(self):
        action = self.get_argument('action')
        #处理 审批出库 或 拒绝出库
        getattr(self, action + '_stock_out')()

        self.redirect(self.reverse_url('real.order_sku_list'))

    def reject_stock_out(self):
        remark = self.get_argument('stock_remark')
        batch_id = self.get_argument('batch_id')

        stock_batch = self.db.get('select * from stock_batch where id = %s', batch_id)
        order_items_obj = json.loads(stock_batch.order_info)
        order_item_ids = [str(i['order_item_id']) for i in order_items_obj]

        # 恢复订单子项状态为已付款
        self.db.execute('update item set status = %s where order_item_id in (%s) '
                        % ('%s', ','.join(['%s']*len(order_item_ids))),
                        const.status.BUY, *order_item_ids)

        # 增加备注信息
        self.db.execute('update stock_batch set status = %s , remark = %s where id = %s', 'REJECT_OUT',
                        remark, batch_id)

    def approve_stock_out(self):
        batch_id = self.get_argument('batch_id')
        stock_batch = self.db.get('select * from stock_batch where id = %s', batch_id)
        order_items_obj = json.loads(stock_batch.order_info)
        order_item_ids = [str(i['order_item_id']) for i in order_items_obj]
        order_ids = set([str(i['order_id']) for i in order_items_obj])

        # 更新订单子项的批次号
        self.db.execute(
            'update item i,goods g set i.status = %s where g.id=i.goods_id and g.type ="R" '
            'and i.status <> %s and i.status <> %s and '
            'i.order_item_id in (%s) ' % ('%s', '%s', '%s', ','.join(['%s'] * len(order_item_ids))),
            const.status.WAIT_TO_SEND, const.status.REFUND, const.status.RETURNING, *order_item_ids)

        self.db.execute('update order_item set stock_batch_id = %s where id in (%s) '
                        % ('%s', ','.join(['%s']*len(order_item_ids))),
                        batch_id, *order_item_ids)

        # 出库
        sku_object = json.loads(stock_batch.sku_info)
        for s in sku_object:
            sku = self.db.get('select id,name,price,stock from sku where id = %s', s['sku_id'])
            sku.out_num = s['out_num']

            # 生成货品出库记录并绑定相应的批次号
            self.db.execute('insert into stock_item (sku_id,num,price,remark,type,'
                            'created_at,created_by,deleted,stock_batch_id) '
                            'values (%s,%s,%s,%s,%s,now(),%s,0,%s)',
                            sku.id, 0 - string.atoi(sku.out_num), sku.price, '审批订单货品出库',
                            'OUT', self.current_user.name, batch_id)

            stocks = self.db.query('select * from stock_item where sku_id = %s and remain_stock>0 and type ="IN" '
                                   'order by created_at', sku.id)

            out_num = string.atoi(sku.out_num)
            for stock in stocks:
                stock.remain_stock = stock.remain_stock - out_num
                if stock.remain_stock < 0:
                    out_num = out_num - stock.remain_stock
                    self.db.execute('update stock_item set remain_stock = 0 where id = %s', stock.id)
                else:
                    self.db.execute('update stock_item set remain_stock = %s where id = %s',
                                    stock.remain_stock, stock.id)
                    break

            # 更新货品库存
            self.db.execute('update sku set stock = stock - %s where id = %s', out_num, sku.id)

        # 审批通过该批次
        self.db.execute('update stock_batch set status = %s where id = %s', 'APPROVE_OUT', batch_id)
        for order_id in order_ids:
            #审批通过出库日志
            self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                            'values (NOW(), 1, %s, %s, %s)',
                            self.current_user.name, "订单出库成功,订单ID:%s" % order_id, order_id)
