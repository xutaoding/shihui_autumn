# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from tornado.options import options
from autumn.utils import json_dumps
from autumn import const
import logging


class VerifiedRefund(BaseHandler):
    """已消费电子券退款处理"""
    @require()
    def get(self):
        self.render('coupon/verified_refund.html')

    @require('service_mgr', 'finance')
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        coupon_sn = self.get_argument('coupon', '').encode('utf-8')
        coupon = self.db.get("""select c.id cid, i.*, c.* from item i, item_coupon c where i.id=c.item_id and c.sn=%s""", coupon_sn)

        # 券不存在, 返回错误信息
        if not coupon:
            return self.write({'error': '券号不存在或者券号错误'})
        # 券状态：未消费， 不能在此操作退款
        if const.status.BUY == coupon.status:
            return self.write({'error': '券号未验证,不能在此操作退款'})
        # 券状态：已退款， 不能再退款
        if const.status.REFUND == coupon.status:
            return self.write({'error': '券号已经退过款'})

        # 获取商户账户id
        # supplier_account_id = self.db.get('select s.account_id sp_account_id from '
        #                                   'supplier s where s.id=%s', coupon.sp_id).sp_account_id
        # 验证门店id
        supplier_shop_account_id = self.db.get('select account_id from supplier_shop where id=%s', coupon.sp_shop_id).account_id

        # 商户门店减去相应金额，数值与验证时增加额度相同
        self.db.execute(
            'insert into account_sequence(type, account_id, item_id, trade_type, trade_id, amount, remark, created_at) '
            'values (%s, %s, %s, %s, %s, %s, %s, NOW())',
            const.seq.REFUND, supplier_shop_account_id, coupon.item_id, 1, coupon.order_id,
            -coupon.purchase_price, '%s 已消费退款' % coupon_sn,  # 商户门店账户减去成本价
        )
        # 更新coupon状态, refund_value 记录退给用户多少钱
        self.db.execute('update item set refund_value=%s, refund_at=NOW(), status=%s where id=%s',
                        coupon.payment, const.status.REFUND, coupon.item_id)

        # 记录日志
        self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                        'values (NOW(), 2, %s, %s, %s)',
                        self.get_current_user().name,
                        '券 %s 已消费退款' % coupon_sn,
                        coupon.cid)

        return self.write({'info': '券号:%s 退款成功!' % coupon_sn})


class RefundQuery(BaseHandler):
    """已消费电子券查询请求"""
    @require()
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        coupon_sn = self.get_argument('coupon', '')
        if not coupon_sn:
            return self.write(json_dumps({'error': '请输入券号'}))

        coupon = self.db.get("""select * from item i, item_coupon c where i.id=c.item_id and c.sn=%s""", coupon_sn)
        if not coupon:
            return self.write(json_dumps({'error': '券号不存在'}))

        return self.write(json_dumps({'coupon': coupon}))


class Unconsumed(BaseHandler):
    """未消费电子券退款，只能是一号店, 一百券, 京东的电子券"""
    @require('service')
    def get(self):
        self.render('coupon/unconsumed_refund.html')

    @require('service')
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        coupon_sn = self.get_argument('coupon', '').encode('utf-8')
        coupon = self.db.get("""select c.id cid, i.*, c.* from item i, item_coupon c where i.id=c.item_id and c.sn=%s""", coupon_sn)

        # 券不存在, 返回错误信息
        if not coupon:
            return self.write({'error': '券号不存在或者券号错误'})
        # 券状态：未消费， 不能在此操作退款
        if const.status.BUY != coupon.status:
            return self.write({'error': '券号状态错误，不能在此操作退款'})
        goods = self.db.get('select * from goods where id=%s', coupon.goods_id)
        # 导入券不能退款
        if 'IMPORT' == goods.generate_type:
            return self.write({'error': '导入券不能退款'})
        # 券状态：已退款， 不能再退款
        if const.status.REFUND == coupon.status:
            return self.write({'error': '券号已经退过款'})
        # 券的分销店铺不是一百券和一号店，不能退款
        if coupon.distr_id != options.distributor_id_jingdong and \
           coupon.distr_id != options.distributor_id_yihaodian and coupon.distr_shop_id != options.shop_id_yibaiquan:
            return self.write({'error': '只有 一百券 , 一号店, 京东 的未消费电子券可以在此退款'})

        # 更新coupon状态
        self.db.execute('update item set refund_value=%s, refund_at=NOW(), status=%s where id=%s',
                        coupon.payment, const.status.REFUND, coupon.item_id)

        # 更新库存
        self.db.execute('update goods set sales_count=sales_count-1, stock=stock+1 where id=%s', goods.id)
        # 记录日志
        self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                        'values (NOW(), 2, %s, %s, %s)',
                        self.get_current_user().name,
                        '未消费电子券 %s 运营后台人工退款' % coupon_sn,
                        coupon.cid)

        return self.write({'info': '券号:%s 退款成功! 请联系财务，执行线下打款操作' % coupon_sn})
