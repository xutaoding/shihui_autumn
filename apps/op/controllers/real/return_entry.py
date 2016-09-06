# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from decimal import Decimal
import logging
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator
from voluptuous import Schema, Any
from autumn import const

find_list = Schema({
    'order_no': str,
    'goods_name': str,
    'return_status': Any('', 'RETURNING', 'RETURNED'),
    'apply_time_start': str,
    'apply_time_end': str,
    'return_time_start': str,
    'return_time_end': str,
}, extra=True)


class ReturnList(BaseHandler):
    @require()
    def get(self):
        form = Form(self.request.arguments, find_list)
        sql = """select i.* from item i,goods g where g.id=i.goods_id and g.type='R' and i.status in (%s,%s)
                 and refund_at is not NULL """
        params = [const.status.REFUND, const.status.RETURNING]

        if form.order_no.value:
            sql += 'and i.order_no = %s '
            params.append(form.order_no.value)
        if form.goods_name.value:
            sql += 'and i.goods_name like %s'
            params.append('%' + form.goods_name.value + '%')
        if form.return_status.value:
            sql += 'and i.status = %s '
            params.append(form.return_status.value)

        sql += 'order by i.id desc'
        page = Paginator(self, sql, params)
        self.render('real/return_entry.html', form=form, page=page)


class ReturnConfirm(BaseHandler):
    @require('operator', 'storage', 'service')
    def post(self):
        id = self.get_argument('id')
        reason = self.get_argument('reason')
        item = self.db.get('select ri.*,osi.express_number ,osi.express_company_id from item ri '
                           'left join order_item oi on ri.order_item_id=oi.id '
                           'left join order_shipping_info osi on osi.id = oi.shipping_info_id '
                           'where ri.id = %s', id)
        sku_goods = self.db.query('select sku_id, num from sku_goods where goods_id = %s', item.goods_id)
        for sku_item in sku_goods:
            sku = self.db.get('select stock, price from sku where id = %s', sku_item.sku_id)
            total = int(sku.stock) + sku_item.num
            self.db.execute('insert into stock_item(sku_id, num, price, remark, type,'
                            'created_at, created_by, deleted, remain_stock) '
                            'values (%s, %s, %s, %s, %s, now(), %s, 0 ,%s)',
                            sku_item.sku_id, sku_item.num, sku.price, '',
                            'IN', self.current_user.name, sku_item.num)
            self.db.execute('update sku set stock = %s where id = %s', total, sku_item.sku_id)

        # 查找商户及门店的账户
        supplier_shop_account_id = self.db.get('select ss.account_id from supplier s,supplier_shop ss '
                                               'where s.id=ss.supplier_id and s.deleted =0 and s.id=%s limit 1',
                                               item.sp_id).account_id
        #只有已发货过的才记录商户资金
        if item.express_number and item.express_company_id:
            self.db.execute(
                'insert into account_sequence(type, account_id, item_id,amount,created_at, remark,trade_type,trade_id) '
                'values (%s, %s, %s, %s, NOW(), %s, 1, %s)',
                const.seq.REFUND, supplier_shop_account_id, item.id, -item.purchase_price,
                '实物退款,备注:%s,订单号：%s' % (item.goods_name, item.order_no), item.order_id)
        self.db.execute('update item set status = %s where id = %s', const.status.REFUND, id)
        #记录日志
        recordJournal(self, item, '确认', reason)
        self.redirect(self.reverse_url('real.return_list'))


class UnReturn(BaseHandler):
    @require('operator', 'storage', 'service')
    def post(self):
        id = self.get_argument('id')
        item = self.db.get('select ri.*,osi.express_number,osi.express_company_id from item ri '
                           'left join order_item oi on ri.order_item_id=oi.id '
                           'left join order_shipping_info osi on osi.id = oi.shipping_info_id '
                           'where ri.id = %s', id)
        remark = self.get_argument('reason')
        # 查找商户及门店的账户
        supplier_shop_account_id = self.db.get('select ss.account_id from supplier s,supplier_shop ss '
                                               'where s.id=ss.supplier_id and s.deleted =0 and s.id=%s limit 1',
                                               item.sp_id).account_id

        #记录日志   #只有已发货过的才记录商户资金
        if item.express_number and item.express_company_id:
            # 记录account_sequence
            self.db.execute(
                'insert into account_sequence(type, account_id,item_id,amount,created_at, remark,trade_type,trade_id) '
                'values (%s, %s, %s, %s, NOW(), %s, 1, %s)',
                const.seq.REFUND, supplier_shop_account_id, item.id, -item.purchase_price,
                '实物退款,备注：%s,订单号：%s' % (item.goods_name, item.order_no), item.order_id)
            #更新订单状态
        self.db.execute('update item set status = %s where id =%s', const.status.REFUND, item.id)

        recordJournal(self, item, '确认', remark)
        self.redirect(self.reverse_url('real.return_list'))


class RealGoodsRefundHandler(BaseHandler):
    @require('service')
    def post(self):
        """ 处理退款、退货"""
        real_item_id = self.get_argument('real_item_id')
        if not real_item_id:
            return
        remark = self.get_argument('return_remark')
        #全额退款金额
        return_amount = Decimal(self.get_argument('return_amount'))
        #部分退款金额
        part_refund_price = self.get_argument('refund_part_price')
        if part_refund_price and Decimal(part_refund_price) > 0:
            return_amount = part_refund_price

        real_item = self.db.get('select * from item where id = %s', real_item_id)
        logging.info("real_item status:%s,real_id:%s,remark:%s", real_item.status, real_item.id, remark)

        if real_item.status == const.status.BUY:
            self.handleRefundOfNoSend(real_item, remark, return_amount)
        elif real_item.status == const.status.WAIT_TO_SEND:
            #未发货的
            shipping = self.db.get('select oi.*,osi.express_number from item r ,order_item oi, '
                                   'order_shipping_info osi where r.order_item_id = oi.id and '
                                   'osi.id=oi.shipping_info_id and r.id=%s', real_item_id)
            #第三方导入订单但未上传运单号的则进行退款操作
            if shipping and shipping.express_number is None:
                self.handleRefundOfNoSend(real_item, remark, return_amount)
            else:
                self.db.execute('update item set status = %s where id =%s', const.status.RETURNING, real_item_id)
                #记录日志
                recordJournal(self, real_item, '申请', remark)

        elif real_item.status == const.status.UPLOADED or real_item.status == const.status.USED:
            self.db.execute('update item set status = %s,refund_value=%s,refund_at = NOW() where id =%s',
                            const.status.RETURNING, return_amount, real_item.id)
            #记录日志
            recordJournal(self, real_item, '申请', remark)

        self.redirect(self.reverse_url('order.show_detail', real_item.order_id))

    def handleRefundOfNoSend(self, real_item, remark, return_amount):
        """ 处理退款"""
        #如果商户是视惠的并且为待打包，则变为退货中，让仓库人员进行确认是不是收回货物
        if real_item.sp_id == 5 and real_item.status == const.status.WAIT_TO_SEND:
            self.db.execute('update item set status = %s,refund_value=%s,refund_at= NOW() where id =%s',
                            const.status.RETURNING, return_amount, real_item.id)
        else:
            #第三方的则直接退款掉
            self.db.execute('update item set status = %s,refund_value=%s,refund_at= NOW() where id =%s',
                            const.status.REFUND, return_amount, real_item.id)
        recordJournal(self, real_item, '处理', remark)


def recordJournal(self, real_item, action, remark):
    """ 记录订单日志 同时插入信息表"""
    self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                    'values (NOW(), 1, %s, %s, %s)',
                    self.current_user.name, u"实物" + action.decode('utf-8') + u"退款/退货 ,原因:%s,item_id:%s" %
                    (remark, real_item.id), real_item.order_id)

    content = '实物' + action + '退货/退款 物品名：%s' % real_item.goods_name
    self.db.execute('insert into notification(created_at, content, uid, type, url, user_type, title) '
                    'values(NOW(), %s, %s, 1, "", 0, %s)', content, real_item.distr_id, u'退货通知')
