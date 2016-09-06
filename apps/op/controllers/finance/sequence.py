# -*- coding: utf-8 -*-
from voluptuous import Schema

from autumn.torn.paginator import Paginator
from .. import BaseHandler
from .. import require
from autumn.torn.form import Form
from datetime import datetime, timedelta
from autumn import const
from xlwt import Workbook
import StringIO

list_schema = Schema({
    'shop_id': str,
    'supplier_id': str,
    'separate_account': str,
    'supplier_full_name': str,
    'supplier_name': str,
    'shop_name': str,
    'start_date': str,
    'end_date': str,
    'type': str,
    'status': str,
    'distr_id': str,
    'from_withdraw_shop_account_id': str,
    'action': str
}, extra=True)


class SupplierSequence(BaseHandler):
    @require()
    def get(self):
        """ 商户财务明细 """
        form = Form(self.request.arguments, list_schema)
        form.action.value = 'download' if form.action.value == 'download' else 'show'
        #从提现申请详情页面查看商户资金明细的时候接受的参数
        supplier_id = self.get_argument("from_withdraw_supplier", '')
        shop_account_id = self.get_argument("from_withdraw_shop_account_id", '')
        applied_at = self.get_argument("applied_at", '')
        status = self.get_argument("status", '')
        if supplier_id:
            form.end_date.value = applied_at
            form.supplier_id.value = supplier_id
            form.status.value = status

        if shop_account_id:
            form.from_withdraw_shop_account_id.value = shop_account_id
        if not form.supplier_id.value:
            return self.render('finance/supplier_sequence.html', form=form, page=[],
                               supplier_name='请先选择商户~', total_amount=0)

        sql = """select ass.*, i.order_id from account_sequence ass left join item i on ass.item_id=i.id
                where 1=1 """
        sum_sql = """ select sum(ass.amount) amount from account_sequence ass where 1=1 """
        params = []
        if shop_account_id:
            sql += 'and ass.account_id = %s '
            sum_sql += 'and ass.account_id = %s '
            params = [shop_account_id]
        else:
            if form.supplier_id.value:
                accounts = self.db.query('select account_id from supplier_shop '
                                         'where supplier_id=%s', form.supplier_id.value)
                sql += 'and ass.account_id in (%s) ' % ','.join(['%s'] * len(accounts))
                sum_sql += 'and ass.account_id in (%s) ' % ','.join(['%s'] * len(accounts))
                params = [str(i.account_id) for i in accounts]

        if form.status.value:
            sql += "and ass.status = %s "
            sum_sql += "and ass.status = %s "
            params.append(int(form.status.value))

        if form.start_date.value:
            sql += "and ass.created_at >= %s "
            sum_sql += "and ass.created_at >= %s "
            params.append(form.start_date.value)

        if form.end_date.value:
            sql += "and ass.created_at <= %s "
            sum_sql += "and ass.created_at <= %s "
            params.append(form.end_date.value)

        if form.type.value:
            sql += "and ass.type = %s "
            sum_sql += "and ass.type = %s "
            params.append(form.type.value)

        sql += "order by ass.id desc"

        if form.action.value == 'show':
            page = Paginator(self, sql, params)

            #总金额
            total_amount = self.db.get(sum_sql, *params).amount
            total_amount = total_amount if total_amount else '0'
            self.render("finance/supplier_sequence.html", form=form, page=page, supplier_name='',
                        total_amount=u'交易总金额:' + str(total_amount))
        else:
            #指定返回的类型
            self.set_header('Content-type', 'application/excel')
            sequence = Workbook(encoding='utf-8')
            filename = form.supplier_name.value + u'商户资金明细'
            #设定用户浏览器显示的保存文件名
            self.set_header('Content-Disposition', 'attachment; filename=' + filename + '.xls')

            title = [u'交易时间', u'备注', u'交易类型', u'收入支出', u'状态']

            write_distributor_sequence = sequence.add_sheet('0')

            for i, content in enumerate(title):
                write_distributor_sequence.write(0, i, content)

            range_list = ['created_at', 'remark', 'trade_type', 'amount', 'status']
            page = self.db.query(sql, *params)
            for i, item in enumerate(page):
                for j, content in enumerate(range_list):
                    v = item[content]
                    if content == 'created_at':
                        v = v.strftime('%Y-%m-%d %H:%M:%S')
                    elif content == 'trade_type':
                        v = {1: u'验证/发货', 2: u'退款', 3: u'刷单', 4: u'预付款', 5: u'保证金'}.get(item.type, '')
                    elif content == 'status':
                        v = {3: u'已结算', 1: u'未结算', 2: u'待结算'}.get(item.status, '')
                    else:
                        pass

                    write_distributor_sequence.write(i + 1, j, v)

            stream = StringIO.StringIO()
            sequence.save(stream)
            self.write(stream.getvalue())


class ResaleSequence(BaseHandler):
    @require()
    def get(self):
        """ 分销商财务明细 """
        abbrs = {
            1: const.status.BUY,
            2: const.status.USED,
            3: const.status.REFUND,
        }
        status = int(self.get_argument('status', 1))

        form = Form(self.request.arguments, list_schema)
        form.action.value = 'download' if form.action.value == 'download' else 'show'
        form.status.value = str(status)
        if not form.distr_id.value:
            form.distr_id.value = '10'
        params = [form.distr_id.value]

        common_fields = """,i.sales_price, do.order_no, i.goods_name, ds.name, i.order_id
                        from item i join distributor_shop ds join goods g
                        left join distributor_order do on i.order_id=do.order_id """
        where_sql = """where ds.id=i.distr_shop_id and i.distr_shop_id = %s and g.id=i.goods_id """

        if status == const.status.REFUND:
            sql = """select i.refund_at operator_at """
            sql += common_fields
            sql += where_sql
            if form.start_date.value:
                sql += "and i.refund_at >= %s "
                params.append(form.start_date.value)
            else:
                #默认显示前一周到现在的分销商资金明细
                sql += "and i.refund_at >= %s "
                params.append((datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
            if form.end_date.value:
                sql += "and i.refund_at <= %s "
                params.append(form.end_date.value)
            if form.type.value:
                sql += "and g.type =%s "
                params.append(form.type.value)
            sql += "order by i.refund_at desc"
        elif status == const.status.USED:
            sql = """select i.used_at operator_at """
            sql += common_fields
            sql += where_sql
            if form.start_date.value:
                sql += "and i.used_at >= %s "
                params.append(form.start_date.value)
            else:
                #默认显示前一周到现在的分销商资金明细
                sql += "and i.used_at >= %s "
                params.append((datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
            if form.end_date.value:
                sql += "and i.used_at <= %s "
                params.append(form.end_date.value)
            if form.type.value:
                sql += "and g.type =%s "
                params.append(form.type.value)

            sql += "order by i.used_at desc"
        else:
            sql = """select i.created_at operator_at """
            sql += common_fields
            sql += where_sql
            if form.start_date.value:
                sql += "and i.created_at >= %s "
                params.append(form.start_date.value)
            else:
                #默认显示前一周到现在的分销商资金明细
                sql += "and i.created_at >= %s "
                params.append((datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
            if form.end_date.value:
                sql += "and i.created_at <= %s "
                params.append(form.end_date.value)
            if form.type.value:
                sql += "and g.type =%s "
                params.append(form.type.value)
            sql += "order by i.created_at desc"

        if form.action.value == 'show':
            page = Paginator(self, sql, params)
            finance_list = self.db.query(sql, *params)

            #查询所有的分销渠道
            distributors = self.db.query('select id,name from distributor_shop')

            amount = sum([item.sales_price for item in finance_list])

            self.render("finance/resale_sequence.html", form=form, abbrs=abbrs, page=page, status=status,
                        distributors=distributors, amount=amount, distr_id=form.distr_id.value)
        else:
            page = self.db.query(sql, *params)
            #指定返回的类型
            self.set_header('Content-type', 'application/excel')
            sequence = Workbook(encoding='utf-8')

            # 分销商的资金明细
            filename = str(form.distr_id.value) + str('渠道资金明细')
            #设定用户浏览器显示的保存文件名
            self.set_header('Content-Disposition', 'attachment; filename=' + filename + '.xls')

            title = [u'渠道', u'外部订单号', u'商品名称', u'交易时间', u'交易金额']

            write_distributor_sequence = sequence.add_sheet('0')

            for i, content in enumerate(title):
                write_distributor_sequence.write(0, i, content)

            range_list = ['name', 'order_no', 'goods_name', 'operator_at', 'sales_price']

            for i, item in enumerate(page):
                for j, content in enumerate(range_list):
                    v = item[content]
                    if content == 'operator_at':
                        v = v.strftime('%Y-%m-%d %H:%M:%S')
                    write_distributor_sequence.write(i + 1, j, v)

            stream = StringIO.StringIO()
            sequence.save(stream)
            self.write(stream.getvalue())
