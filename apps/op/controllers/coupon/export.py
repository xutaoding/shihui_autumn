# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from autumn.order import new_distributor_item, new_distributor_order
from datetime import datetime
from xlwt import Workbook
import StringIO
import time


class SelectDistributor(BaseHandler):

    @require('developer')
    def get(self):
        distributor_shops = self.db.query('select id, name from distributor_shop where deleted =0 ')
        self.render('coupon/export.html', distributor_shops=distributor_shops)

    @require('developer')
    def post(self):
        distributor_shop_id = self.get_argument('distributor_id').encode('utf-8')
        goods_id = self.get_argument('goods_id').encode('utf-8')
        num = int(self.get_argument('num').encode('utf-8'))

        # 参数错误返回
        if not distributor_shop_id or not goods_id or not num:
            return self.render('coupon/export_result.html', result="出错了！！参数错误, 请重新操作", coupons=[],
                               goods_name='', order_id='')

        # 没有商品，返回
        goods_info = self.db.get('select * from goods where id=%s and deleted=0', goods_id)
        if not goods_info:
            return self.render('coupon/export_result.html', result="出错了！！找不到商品", coupons=[],
                               goods_name='', order_id='')

        # 检查库存，如果库存不足，返回
        if int(goods_info.stock) < num:
            return self.render('coupon/export_result.html', result="出错了！！库存不足", coupons=[],
                               goods_name='', order_id='')

        # 生成订单
        order_amount = goods_info.sales_price * num
        order_id, order_no = new_distributor_order(self.db, distributor_shop_id,
                                                   order_amount, order_amount, "")
        result = new_distributor_item(self.db, order_id, order_no, goods_info.sales_price, num, goods_info,
                                      "", distributor_shop_id, "", [], False)
        # 生成分销订单
        self.db.execute('insert into distributor_order (order_no, created_at, message, distributor_shop_id, order_id) '
                        'values (%s, NOW(), %s, %s, %s)',
                        'EXPORT%s' % int(time.time()), '批量导出电子券', distributor_shop_id, order_id)

        if not result.ok:
            return self.render('coupon/export_result.html', result=result.msg, goods_name=goods_info.short_name,
                               coupons=[], order_id='')
        else:
            # 写日志,订单记一个,商品记一个
            operator = self.get_current_user().name
            message = "批量导出电子券, 分销商店铺id:%s, 数量:%s, 商品:%s" % (distributor_shop_id, num, goods_info.short_name)
            self.db.execute(
                'insert into journal (created_at, type, created_by, message, iid) values '
                '(NOW(), 1, %s, %s, %s)', operator, message, order_id
            )
            self.db.execute(
                'insert into journal (created_at, type, created_by, message, iid) values '
                '(NOW(), 3, %s, %s, %s)', operator, message, goods_id
            )
            coupons = [c['coupon_sn'] for c in result.coupons]
            self.render('coupon/export_result.html', result=result.msg, coupons=coupons,
                        goods_name=goods_info.short_name, order_id=order_id)


class Download(BaseHandler):
    """下载批量导出的电子券"""
    @require('developer')
    def get(self):
        order_id = self.get_argument('order_id')
        #指定返回的类型
        self.set_header('Content-type', 'application/excel')
        filename = '导出电子券'+ datetime.now().strftime('%m%d%H%M')
        #设定用户浏览器显示的保存文件名
        self.set_header('Content-Disposition', 'attachment; filename=' + filename + '.xls')

        coupons = self.db.query('select sn from item i, item_coupon c where i.order_id=%s and i.id=c.item_id', order_id)

        excel = Workbook(encoding='utf-8')
        write_excel = excel.add_sheet('0', cell_overwrite_ok=True)
        write_excel.write(0, 0, '券号')

        row = 1
        for coupon in coupons:
            write_excel.write(row, 0, coupon.sn)
            row += 1

        stream = StringIO.StringIO()
        excel.save(stream)

        self.write(stream.getvalue())
