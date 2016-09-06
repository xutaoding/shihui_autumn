# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from voluptuous import Schema

from .. import BaseHandler
from .. import require
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator
import StringIO
from xlwt import Workbook


list_schema = Schema({
    'order_no': str,
    'mobile': str,
    'end_date': str,
    'start_date': str,
    'short_name': str,
    'distributor_order_no': str,
    'sales_name': str,
    'sales_id': str,
    'action': str,
    'dsid': str
}, extra=True)


class OrderList(BaseHandler):
    @require()
    def get(self):
        form = Form(self.request.arguments, list_schema)
        form.action.value = 'download' if form.action.value == 'download' else 'show'
        params = []

        sql = """select o.order_no, g.short_name gsname, g.id gid, o.id oid, ss.name, o.payment, o.created_at,
                 ds.name dsname,
                 dor.order_no distributor_order_number,  oi.num, g.purchase_price, o.status, o.mobile
                 %s
                 from order_item oi join orders o on oi.order_id = o.id
                 join goods g on oi.goods_id = g.id
                 left join supplier_shop ss on oi.distributor_shop_id = ss.id
                 left join distributor_order dor on dor.order_id = o.id
                 left join supplier s on g.supplier_id = s.id
                 left join distributor_shop ds on dor.distributor_shop_id = ds.id
                 %s
                 where 1=1 """
        if form.action.value == 'download':
            sql = sql % (', osi.paid_at, osi.created_at, osi.address, osi.remarks ',
                         'join order_shipping_info osi on oi.shipping_info_id = osi.id ')
        else:
            sql = sql % ('', '')

        if form.order_no.value:
            sql += 'and o.order_no=%s '
            params.append(form.order_no.value)

        if form.mobile.value:
            sql += 'and o.mobile=%s '
            params.append(form.mobile.value)

        if form.short_name.value:
            sql += 'and g.short_name like %s '
            params.append('%' + form.short_name.value + '%')

        if form.distributor_order_no.value:
            sql += 'and dor.order_no = %s '
            params.append(form.distributor_order_no.value)

        if form.end_date.value:
            sql += 'and o.created_at <= %s '
            params.append(form.end_date.value)

        if form.start_date.value:
            sql += 'and o.created_at > %s '
            params.append(form.start_date.value)

        if form.sales_id.value:
            sql += 'and s.sales_id = %s '
            params.append(form.sales_id.value)

        if form.dsid.value:
            sql += 'and ds.id = %s '
            params.append(form.dsid.value)

        # 如果一个条件都不指定，查询2个月内的
        if not any(map(bool, [form.order_no.value, form.mobile.value, form.short_name.value,
                              form.distributor_order_no.value, form.end_date.value, form.start_date.value])):
            start_date = datetime.now().date() - timedelta(days=60)
            sql += 'and o.created_at > %s '
            params.append(start_date)

        sql += 'order by oi.id desc '

        if form.action.value == 'show':
            page = Paginator(self, sql, params)

            order_nos = set([])
            order_list = []
            for order in page.rows:
                if order.order_no in order_nos:
                    for item in order_list:
                        if order.order_no in item.keys():
                            item[order.order_no]['item'].append({'gsname': order.gsname, 'gid': order.gid})
                else:
                    order_nos.add(order.order_no)
                    order_map = {order.order_no: {'item': [{'gsname': order.gsname, 'gid': order.gid}],
                                                  'payment': order.payment,
                                                  'created_at': order.created_at,
                                                  'oid': order.oid,
                                                  'distributor': order.dsname}}
                    order_list.append(order_map)
            self.render('order/list.html', form=form, order_list=order_list, page=page)
        else:
            page = self.db.query(sql, *params)
            title = [u'订单号', u'外部订单号', u'订单金额', u'商品名称', u'原价', u'总成本', u'订单状态', u'数量', u'付款时间',
                     u'发货时间', u'收货手机', u'收货地址', u'退货时间', u'订单留言']
            self.set_header('Content-type', 'application/excel')
            self.set_header('Content-Disposition', 'attachment; filename=order.xls')
            order_excel = Workbook(encoding='utf-8')
            write_order_excel = order_excel.add_sheet('0')

            for index, content in enumerate(title):
                write_order_excel.write(0, index, content)

            range_list = ['order_no', 'distributor_order_number', 'payment', 'gsname', 'price', 'purchase_price',
                          'status', 'num', 'paid_at', 'created_at', 'mobile', 'address', 'refund_at', 'remark']

            for i, item in enumerate(page):
                for j, content in enumerate(range_list):
                        v = item.get(content, '')
                        v = v if v else ''
                        if content == 'purchase_price':
                            v = float(item['purchase_price']) * int(item['num'])
                        elif content == 'price':
                            v = float(item['purchase_price']) * int(item['num'])
                        elif content in ['paid_at', 'created_at', 'refund_at']:
                            v = str(v)
                        elif content == 'status':
                            v = {0: '未付款', 1: '已付款', 2: '已消费', 3: '退款', 4: '待发货', 5: '已上传', 6: '冻结', 7: '退货中'}.get(item.status, '')
                        else:
                            pass

                        write_order_excel.write(i + 1, j, v)

            stream = StringIO.StringIO()
            order_excel.save(stream)
            self.write(stream.getvalue())


class OrderDetail(BaseHandler):
    @require('sales', 'operator', 'finance', 'service')
    def get(self, id):
        """ 显示订单详情 """
        # 订单信息
        order = self.db.get('select do.order_no distri_order_no,o.order_no,o.distributor_shop_id,o.created_at,ds.name,'
                            'o.paid_at,o.payment,o.id order_id, o.mobile from orders o '
                            'left join distributor_order do on o.id=do.order_id '
                            'left join distributor_shop ds on o.distributor_shop_id=ds.id '
                            'where o.id =%s', id)
        shipping_info = []
        ex_company = []
        #判断是否为电子订单
        type = self.db.get(
            'select g.type from goods g,order_item oi where oi.goods_id=g.id and oi.order_id=%s limit 1', id)['type']
        if type == 'E':
            items = self.db.query(
                'select oi.num,oi.goods_id,oi.sales_price,g.type,g.code,g.short_name,g.expire_at,oi.order_id, '
                'o.name sales_name from order_item oi ,goods g,supplier s,operator o where oi.goods_id=g.id and '
                's.id=g.supplier_id and o.id=s.sales_id and oi.order_id=%s', id)

        else:
            #订单明细
            items = self.db.query(
                'select ri.id real_id,oi.goods_id,oi.sales_price,ri.status,g.type,g.code,g.short_name, '
                'ri.order_id,oi.shipping_info_id,used_at,ri.refund_value,ri.sp_id,o.name sales_name from order_item oi '
                'left join item ri on oi.id =ri.order_item_id left join goods g on oi.goods_id=g.id '
                'left join supplier s on s.id=g.supplier_id left join operator o on o.id = s.sales_id '
                'where oi.order_id=%s', id)
            if items[0].shipping_info_id:
                #取得实物订单的收货信息
                shipping_info = self.db.get('select o.*,e.name from order_shipping_info o left join express_company e '
                                            'on o.express_company_id = e.id where o.id=%s',
                                            items[0].shipping_info_id)
                #快递公司信息
                ex_company = self.db.query('select * from express_company order by id desc')

        journals = self.db.query('select * from journal where type =1  and iid=%s order by id desc',
                                 items[0].order_id)

        self.render('order/detail.html', order=order, real_items=items, ex_company=ex_company,
                    shipping_info=shipping_info, type=type, journals=journals)


class ExpressEdit(BaseHandler):
    @require('operator', 'service')
    def post(self):
        """修改快递信息"""
        id = self.get_argument('shipping_id')
        order_id = self.get_argument('order_id')
        company_id = self.get_argument('company_id')
        express_number = self.get_argument('express_number')
        address = self.get_argument('address')
        phone = self.get_argument('phone')
        service_remark = self.get_argument('service_remark')

        old_order_shipping = self.db.get('select * from order_shipping_info where id = %s', int(id))
        params = []
        sql_params = []
        upd_flag = False
        message = "该订单修改了"
        sql = 'update order_shipping_info osi set '
        if company_id and (old_order_shipping.express_company_id != int(company_id)):
            sql_params.append("express_company_id = %s ")
            params.append(company_id)
            message += '快递公司'
            upd_flag = True
        if express_number and (old_order_shipping.express_number != express_number):
            sql_params.append("express_number = %s ")
            params.append(express_number)
            message += '快递单号,由%s→%s' % (old_order_shipping.express_number, express_number.encode('utf-8'))
            upd_flag = True
        if address and (old_order_shipping.address.decode('utf-8') != address):
            sql_params.append("address = %s ")
            params.append(address)
            message += '收货人地址,由%s→%s'% (old_order_shipping.address, address.encode('utf-8'))
            upd_flag = True
        if phone and (old_order_shipping.phone != phone):
            sql_params.append("phone = %s ")
            params.append(phone)
            message += '收货人电话,由%s→%s'% (old_order_shipping.phone, phone.encode('utf-8'))
            upd_flag = True

        sql += ','.join(sql_params)
        sql += ' where id = %s'
        params.append(id)
        if upd_flag:
            self.db.execute(sql, *params)
            item = self.db.get('select i.order_no,i.sp_id,oi.stock_batch_id from item i ,order_item oi '
                               'where i.order_item_id = oi.id and i.order_id =%s order by i.id desc limit 1', order_id)
            # 放入消息表，以便通知商户发货
            self.db.execute('insert into notification(content, created_at, type, url, uid, user_type,title) '
                            'values(%s, NOW(), 1, %s, %s, 0,%s)',
                            u'订单%s修改了收货人信息,如果该订单还未发货，请重新下载【%s批次】的发货单'
                            % (item.order_no, item.stock_batch_id), '/shipping/show',
                            item.sp_id, u'修改收货信息通知')

        if service_remark:
            message = "实物订单修改收货信息,客服备注:%s" % service_remark.encode('utf-8')
            upd_flag = True
        if upd_flag:
            #记录操作日志信息
            self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                            'values (NOW(), 1, %s, %s, %s)', self.current_user.name, message, order_id)

        self.redirect(self.reverse_url('order.show_detail', order_id))


