# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from decimal import Decimal
import tornado.web
from xlrd import open_workbook
from xlwt import Workbook
from autumn.torn.paginator import Paginator
import json
import StringIO
from autumn import const
from tornado.options import options
import tornado.gen
from autumn.api.taobao import Taobao
from autumn.utils import json_dumps, PropDict, json_hook
import logging


class ShowShipping(BaseHandler):
    @require('manager')
    def get(self):
        sql = 'select * from stock_batch where supplier_id = %s order by id desc'
        params = [self.current_user.supplier_id]
        page = Paginator(self, sql, params)

        wait_orders = wait_send_orders(self)
        self.render('real/show.html', page=page, unload_number=len(wait_orders))


def wait_send_orders(self):
    """代发货清单"""
    return self.db.query('select distinct g.id id, oi.id item_id, oi.num from order_item oi left join goods g on '
                         'oi.goods_id = g.id left join item ri on oi.id = ri.order_item_id '
                         'where oi.stock_batch_id is NULL and ri.status = %s and '
                         'g.type = "R" and g.supplier_id = %s ', const.status.BUY, self.current_user.supplier_id)


class CreateShipping(BaseHandler):
    @require('manager')
    def post(self):
        wait_orders = wait_send_orders(self)

        order_item_ids = [str(i['item_id']) for i in wait_orders]
        order_items = []
        for item in wait_orders:
            order_items.append(dict(item_id=item.item_id, num=item.num))

        batch_id = self.db.execute('insert into stock_batch(order_info,type,status,created_at,created_by,supplier_id,'
                                   'order_count) '
                                   'values(%s, %s, %s, now(), %s,%s,%s)', json_dumps(order_items), 'OUT', 'DONE',
                                   self.current_user.login_name, self.current_user.supplier_id, len(wait_orders))

        self.db.execute(
            'update item i,goods g set i.status = %s where g.id=i.goods_id and g.type ="R" '
            'and i.status <> %s and i.status <> %s and '
            'i.order_item_id in (%s) ' % ('%s','%s','%s', ','.join(['%s'] * len(order_item_ids))),
            const.status.WAIT_TO_SEND, const.status.REFUND,const.status.RETURNING, *order_item_ids)

        self.db.execute('update order_item set stock_batch_id = %s where id in (%s) '
                        % ('%s', ','.join(['%s'] * len(order_item_ids))),
                        batch_id, *order_item_ids)

        self.redirect(self.reverse_url('real.show_shipping'))


class DownloadShipping(BaseHandler):
    @require('manager')
    def get(self):
        batch_id = self.get_argument('batch_id')
        filename = u'发货单_' + self.current_user.name.decode('utf-8') + u'_' + batch_id
        #指定返回的类型
        self.set_header('Content-type', 'application/excel')
        #设定用户浏览器显示的保存文件名
        self.set_header('Content-Disposition', 'attachment; filename=' + filename + '.xls')

        order_batch_excel_list = [u'商品ID', u'订单号', u'商品名称', u'单价', u'数量', u'支付时间', u'备注', u'收件人',
                                  u'手机号码', u'邮编号码', u'送货地址', u'外部订单号', u'快递公司', u'快递单号']

        order_batch_excel = Workbook(encoding='utf-8')
        write_order_batch_excel = order_batch_excel.add_sheet('0')

        for i in range(len(order_batch_excel_list)):
            write_order_batch_excel.write(0, i, order_batch_excel_list[i])

        range_list = ['goods_id', 'order_no', 'name', 'sales_price', 'num', 'paid_at', 'remarks', 'receiver', 'phone',
                      'zip_code', 'address', 'distr_order_no']

        order_batch = self.db.get('select * from stock_batch where id = %s', batch_id)
        sql = """select distinct oi.goods_id, o.order_no, oi.sales_price, osi.paid_at,oi.id order_item_id,
                                oi.num-(select count(r.id) from `item` r,goods g where r.order_id=o.id and
                                r.goods_id=g.id and r.status in (%s,%s) ) num,ri.goods_name name,
                                osi.remarks,osi.receiver, osi.phone, osi.zip_code, osi.address, osi.distr_order_no
                                from order_item oi, order_shipping_info osi,item ri,orders o
                                where oi.shipping_info_id = osi.id and ri.order_item_id = oi.id and
                                 o.id=oi.order_id and ri.order_id =o.id
                                and ri.status <> %s and ri.status <> %s and ri.sp_id =%s """

        params = [const.status.REFUND, const.status.RETURNING, const.status.REFUND, const.status.RETURNING,
                  self.current_user.supplier_id]
        row = 0
        if order_batch:
            sql += " and oi.stock_batch_id = %s"
            params.append(batch_id)

        orders = self.db.query(sql, *params)
        item_ids = []
        #转换快递信息
        if orders:
            for order in orders:
                row += 1
                item_ids.append(order.order_item_id)
                for j in range(len(range_list)):
                    v = order[range_list[j]]
                    write_order_batch_excel.write(row, j, str(v) if v is not None else '')

        stream = StringIO.StringIO()
        order_batch_excel.save(stream)

        #最后把相关订单更新待打包
        if item_ids:
            self.db.execute("update item set status = %%s where status= %%s and order_item_id in(%s) " %
                            ','.join(['%s'] * len(item_ids)),
                            const.status.WAIT_TO_SEND, const.status.BUY, *item_ids)

        self.write(stream.getvalue())


class ImportShipping(BaseHandler):
    @require('manager')
    def get(self):
        #取得快递信息
        express = self.db.query('select * from express_company ')
        self.render('real/import_shipping.html', error='', message='', success_list=[], failure_list=[],
                    taobao_failure=[], express=express)

    @require('manager')
    @tornado.gen.coroutine
    def post(self):
        express = self.db.query('select * from express_company ')
        if not self.request.files:
            self.render('real/import_shipping.html', error=1, message='', success_list=[], failure_list=[],
                        taobao_failure=[], express=express)

        #读取文件
        order_shipping_file = self.request.files['order_shipping_file'][0]
        try:
            book = open_workbook(file_contents=order_shipping_file['body'])
            sheet = book.sheet_by_index(0)
        except:
            message = u"打开%s发生错误，请重新选择上传文件" % (order_shipping_file['filename'])
            self.render('real/import_shipping.html', error=1, message=message, success_list=[], failure_list=[],
                        taobao_failure=[], express=express)

        #flag_import用于判定是否重复导入发货单
        flag_import = 0
        success_list = set([])
        failure_list = set([])
        taobao_list = set([])
        taobao_map = {}
        taobao_failure = []
        rows = [sheet.row_values(i) for i in range(1, sheet.nrows)]
        for row in rows:
            order_no = row[1]
            express_company = row[12]
            express_number = guess_express(str(row[13]))
            if not (express_company and express_number):
                failure_list.add(order_no)
                continue

            express_company_id = self.db.get('select id from express_company where code = %s', express_company)
            if not express_company_id:
                failure_list.add(order_no)
                continue

            #只有待打包的才可以上传
            real_items = self.db.query(""" select ri.id,oi.goods_id,oi.shipping_info_id,ri.distr_id,ri.goods_name,
                                    oi.order_id,(select g.name from goods g,sku s,sku_goods sg where g.id = sg.goods_id
                                    and s.id=sg.sku_id and g.id = oi.goods_id) name,ri.sp_id, osi.express_number,
                                    osi.express_company_id,ri.payment,ri.purchase_price,ri.distr_shop_id
                                    from order_item oi,item ri,orders o,order_shipping_info osi
                                    where ri.order_item_id = oi.id and o.id=oi.order_id and ri.order_id =o.id and
                                    oi.shipping_info_id = osi.id and ri.status = %s and
                                    o.order_no = %s and oi.goods_id=%s order by o.id """, const.status.WAIT_TO_SEND,
                                    order_no, row[0])

            if real_items:
                flag_import += 1
                # 查找商户及门店的账户
                supplier_shop_account_id = self.db.get('select ss.account_id from supplier s,supplier_shop ss '
                                                       'where s.id=ss.supplier_id and s.deleted =0 and s.id=%s limit 1',
                                                       real_items[0].sp_id).account_id
                #记录资金
                for item in real_items:
                    #把每个real_item状态更新为已发货
                    self.db.execute('update item set status =%s, used_at = NOW() where status = %s '
                                    'and id = %s', const.status.USED, const.status.WAIT_TO_SEND, item.id)
                    self.db.execute(
                        'insert into account_sequence(type, account_id, item_id,amount,created_at,remark,'
                        'trade_type,trade_id) values (%s, %s, %s, %s, NOW(),%s,1,%s)',
                        const.seq.USED, supplier_shop_account_id, item.id, item.purchase_price,
                        u'实物发货,备注:%s,订单号:%s' % (item.goods_name.decode('utf-8'), order_no),item.order_id)
                #更新运物流信息
                self.db.execute('update order_shipping_info set express_company_id = %s, express_number = %s '
                                'where id = %s', express_company_id.id, express_number, real_items[0].shipping_info_id)
                # 记录订单日志
                self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                                'values (NOW(), 1, %s, %s, %s)',
                                self.current_user.login_name, "实物发货成功, 本次发货数量%s个" % len(real_items),
                                real_items[0].order_id)

                #分销商为taobao时自动发货
                if real_items[0].distr_shop_id == options.shop_id_taobao \
                    or real_items[0].distr_shop_id == options.shop_id_tmall:
                    taobao_list.add(real_items[0].order_id)
                    taobao_map[str(real_items[0].order_id)] = [real_items[0].distr_shop_id, express_number, express_company]

                #更新运费todo
                success_list.add(order_no)

        #取得淘宝订单中的所有外部单号
        if taobao_list:
            outer_list = self.db.query('select o.id, d.order_no from orders o left join distributor_order d on '
                                       'o.distributor_order_id = d.id where o.id in (%s)'
                                       % ','.join(['%s'] * len(taobao_list)), *taobao_list)

            for i in outer_list:
                taobao_map[str(i.id)].append(i.order_no)

            #taobao自动发货的都加入进队列
            for taobao_item in taobao_list:
                params = {
                    'tid': int(taobao_map[str(taobao_item)][3]),
                    'out_sid': int(taobao_map[str(taobao_item)][1]),
                    'company_code': taobao_map[str(taobao_item)][2]
                }
                #此处循环取得队列中的信息，先进行取状态。若状态为WAIT_SELLER_SEND_GOODS，则加入队列
                app_info = json.loads(self.db.get('select taobao_api_info from distributor_shop where id = %s',
                                                  int(taobao_map[str(taobao_item)][0])).taobao_api_info,
                                                  object_hook=json_hook)
                status = yield order_status(params['tid'], app_info)

                if status.ok:
                    self.redis.lpush(options.queue_taobao_express, json_dumps(params))
                else:
                    taobao_failure.append(taobao_map[str(taobao_item)][3])
                    #如果订单多个item 只退了其中一个 则，我们这边不知道更新哪一个real_item
                    # if status.status == 'REFUND':
                    #     self.db.execute('update real_item set status = "RETURNED" where order_id = %s', taobao_item)
                    #     logging.info('order has returned. order %s', taobao_item)
                    # else:
                    logging.info('order need not send. order %s', taobao_item)

        if not flag_import:
            if not len(failure_list):
                message = u"%s已经导入，请勿重复导入" % (order_shipping_file['filename'])
                self.render('real/import_shipping.html', error=1, message=message, success_list=[], failure_list=[],
                            taobao_failure=[], express=express)
            else:
                message = u"%s已经导入成功" % (order_shipping_file['filename'])
                self.render('real/import_shipping.html', error='', message=message, success_list=success_list,
                            failure_list=failure_list, taobao_failure=taobao_failure, express=express)

        message = u"%s已经导入成功" % (order_shipping_file['filename'])
        self.render('real/import_shipping.html', error='', message=message, success_list=success_list,
                    failure_list=failure_list, taobao_failure=taobao_failure, express=express)


def guess_express(express_number):
    converted_express_number = express_number
    if express_number and (express_number.find('E') >= 0 or express_number.find('e') >= 0):
        converted_express_number = Decimal(express_number)
    elif express_number and isinstance(express_number, float):
        converted_express_number = str(int(express_number))
    elif express_number:
        converted_express_number = str(int(float(express_number)))
    return converted_express_number


@tornado.gen.coroutine
def order_status(tid, app_info):
    order_status_request = Taobao('taobao.trade.get')
    order_status_request.set_app_info(app_info.app_key, app_info.app_secret_key)
    order_status_request.set_session(app_info.session)

    response = yield order_status_request(tid=tid, fields='status')
    order_status_request.parse_response(response.body)

    if order_status_request.is_ok():
        if order_status_request.message.trade.status == 'WAIT_SELLER_SEND_GOODS':
            raise tornado.gen.Return(PropDict(ok=True, status='SEND'))
        elif order_status_request.message.trade.status == 'TRADE_CLOSED':
            raise tornado.gen.Return(PropDict(ok=False, status='REFUND'))
        else:
            raise tornado.gen.Return(PropDict(ok=False, status='OTHER'))
    else:
        raise tornado.gen.Return(PropDict(ok=False, status='OTHER'))
