# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from decimal import Decimal
from autumn.torn.paginator import Paginator
from xlwt import Workbook
import StringIO
from xlrd import open_workbook
import json
from autumn import const
from tornado.options import options
from autumn.api.taobao import Taobao
from autumn.utils import json_dumps, PropDict, json_hook
import tornado.gen
import logging


class Show(BaseHandler):
    @require()
    def get(self):
        sql = 'select * from stock_batch where status = "APPROVE_OUT" order by id desc'
        page = Paginator(self, sql, [])
        self.render('real/order_shipping_show.html', page=page)


class Download(BaseHandler):
    @require('operator', 'service')
    def get(self):
        batch_id = self.get_argument('batch_id')
        filename = u'发货单_视惠_' + batch_id
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

        order_batch_list = json.loads(self.db.get('select * from stock_batch where id = %s', batch_id)['order_info'])
        row = 0
        for order_batch in order_batch_list:
            order = self.db.get("""select distinct oi.goods_id, o.order_no, oi.sales_price, osi.paid_at,
                                oi.num-(select count(r.id) from `item` r,goods g where r.order_id=o.id and
                                r.goods_id=g.id and r.status in (%s,%s) ) num,
                                osi.remarks,osi.receiver, osi.phone, osi.zip_code, osi.address, osi.distr_order_no,
                                (select g.name from goods g,sku s,sku_goods sg where g.id = sg.goods_id
                                and s.id=sg.sku_id and g.id = oi.goods_id) name
                                from order_item oi, order_shipping_info osi,item ri,orders o
                                where oi.shipping_info_id = osi.id and ri.order_item_id = oi.id and
                                 o.id=oi.order_id and ri.order_id =o.id
                                and ri.status <> %s and ri.status <> %s and oi.id = %s """,
                                const.status.REFUND, const.status.RETURNING,const.status.REFUND, const.status.RETURNING,
                                order_batch['order_item_id'])
            row += 1
            if order:
                for j in range(len(range_list)):
                    v = order[range_list[j]]
                    write_order_batch_excel.write(row, j, str(v) if v is not None else '')

        stream = StringIO.StringIO()
        order_batch_excel.save(stream)
        self.write(stream.getvalue())


def guess_express(express_number):
    converted_express_number = express_number
    if express_number and (express_number.find('E') >= 0 or express_number.find('e') >= 0):
        converted_express_number = Decimal(express_number)
    elif express_number and isinstance(express_number, float):
        converted_express_number = str(int(express_number))
    elif express_number:
        converted_express_number = str(int(float(express_number)))

    return converted_express_number


class Import(BaseHandler):
    @require('operator', 'service')
    def get(self):
        self.render('real/order_shipping.html', error=0, message='', success_list=[], failure_list=[])

    @require('operator', 'service')
    @tornado.gen.coroutine
    def post(self):
        if not self.request.files:
            self.render('real/import_shipping.html', error=1, message='', success_list=[], failure_list=[])

        #读取文件
        order_shipping_file = self.request.files['order_shipping_file'][0]
        try:
            book = open_workbook(file_contents=order_shipping_file['body'])
            sheet = book.sheet_by_index(0)
        except:
            message = u"打开%s发生错误，请重新选择上传文件" % (order_shipping_file['filename'])
            self.render('real/order_shipping.html', error=1, message=message, success_list=[], failure_list=[])

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
            if not (express_company or express_number):
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
                        u'实物发货,备注:%s,订单号:%s' % (item.goods_name.decode('utf-8'), order_no), item.order_id)
                #更新运物流信息
                self.db.execute('update order_shipping_info set express_company_id = %s, express_number = %s '
                                'where id = %s', express_company_id.id, express_number, real_items[0].shipping_info_id)
                # 记录订单日志
                self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                                'values (NOW(), 1, %s, %s, %s)',
                                "%s" % self.current_user.name, "实物发货成功, 本次发货数量%s个" % len(real_items) ,
                                real_items[0].order_id)

                #分销商为taobao时自动发货
                if real_items[0]['distr_shop_id']== options.shop_id_taobao \
                    or real_items[0]['distr_shop_id'] == options.shop_id_tmall:
                    taobao_list.add(real_items[0].order_id)
                    taobao_map[str(real_items[0].order_id)] = [real_items[0]['distr_shop_id'],
                                                               express_number, express_company]


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
                    'company_code': taobao_map[str(taobao_item)][2],
                }
                #此处循环取得队列中的信息，先进行取状态。若状态为WAIT_SELLER_SEND_GOODS，则加入队列
                app_info = json.loads(self.db.get('select taobao_api_info from distributor_shop where id = %s',
                                                  int(taobao_map[str(taobao_item)][0])).taobao_api_info,
                                      object_hook=json_hook)
                status = yield order_status(params['tid'], app_info)

                logging.info('status:%s',status.ok)
                if status.ok:
                    params.update({'retry': 0})
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
                self.render('real/order_shipping.html', error=1, message=message, success_list=[], failure_list=[])
            else:
                message = u"%s已经导入成功" % (order_shipping_file['filename'])
                self.render('real/order_shipping.html', error=2, message=message,
                            success_list=success_list, failure_list=failure_list, taobao_failure=taobao_failure)

        message = u"%s已经导入成功" % (order_shipping_file['filename'])
        self.render('real/order_shipping.html', error=2, message=message, success_list=success_list,
                    failure_list=failure_list, taobao_failure=taobao_failure)


@tornado.gen.coroutine
def order_status(tid, app_info):
    order_status = Taobao('taobao.trade.get')
    order_status.set_app_info(app_info.app_key, app_info.app_secret_key)
    order_status.set_session(app_info.session)
    response = yield order_status(tid=tid, fields='status')
    logging.info("response.body:%s",response.body)
    order_status.parse_response(response.body)
    if order_status.is_ok():
        logging.info('order_status.message.trade.status :%s,%s', order_status.message.trade.status)
        if order_status.message.trade.status == 'WAIT_SELLER_SEND_GOODS':
            raise tornado.gen.Return(PropDict(ok=True, status='SEND'))
        elif order_status.message.trade.status == 'TRADE_CLOSED':
            raise tornado.gen.Return(PropDict(ok=False, status='REFUND'))
        else:
            raise tornado.gen.Return(PropDict(ok=False, status='OTHER'))
    else:
        raise tornado.gen.Return(PropDict(ok=False, status='OTHER'))


