# -*- coding: utf-8 -*-
from .. import BaseHandler
from xlwt import Workbook
from .. import require
import StringIO
from voluptuous import Schema, All, Coerce, Range
from autumn.torn.form import Form, Date
from autumn.torn.paginator import Paginator
from autumn.utils import PropDict

list_schema = Schema({
    'name': str,
    'operator_id': str,
    'start_date': Date('%Y-%m-%d'),
    'end_date': Date('%Y-%m-%d'),
    'action': str,
    'kind': All(Coerce(int), Range(min=1, max=3)),
}, extra=True)


class Profit(BaseHandler):
    @require()
    def get(self):
        """销售业绩"""
        form = Form(self.request.arguments, list_schema)
        op_id = form.operator_id.value
        start = form.start_date.value
        end = form.end_date.value
        download = form.action.value if form.action.value else 'show'

        if not form.validate():
            return self.render('finance/profit.html', form=form, page=[], name='输入正确参数查询', total='', amount='',
                               sale_amount='', sum_commission='')

        operator = self.db.get('select * from operator where id=%s', op_id)
        if not operator:
            return self.render('finance/profit.html', form=form, page=[], name='销售人员不存在', total='', amount='',
                               sale_amount='', sum_commission='')

        sql = ''
        sum_sql = ''
        kind = ''
        kind0 = ''
        kind1 = ''
        sale_amount = 0
        params = [op_id]
        # 统计消费(验证)明细(不包含刷单)
        if form.kind.value == 1:
            sql = 'select goods_name, used_at as time, sales_price, purchase_price, payment as amount, ' \
                  '(payment-purchase_price) as profit, commission, order_no, order_id, distr_shop_id from item where sales_id=%s ' \
                  'and used_at is not null and cheat_at is null and status=2 '
            sum_sql = 'select sum(payment) amount, sum(commission) commission, sum(payment-purchase_price) as total ' \
                      'from item where sales_id=%s and used_at is not null and cheat_at is null and status=2 '
            sale_sql = 'select sum(payment) amount from item where sales_id=%s and created_at is not null '
            kind = '-消费利润汇总：'
            kind0 = '消费总金额：'
            kind1 = '渠道佣金：'

            if start:
                sql += 'and cast(used_at as Date)>=%s '
                sum_sql += 'and cast(used_at as Date)>=%s '
                sale_sql += 'and cast(created_at as Date)>=%s '
                params.append(start)
            if end:
                sql += 'and cast(used_at as Date)<=%s '
                sum_sql += 'and cast(used_at as Date)<=%s '
                sale_sql += 'and cast(created_at as Date)<=%s '
                params.append(end)
            sql += 'order by used_at desc'
            sale_amount = self.db.get(sale_sql, *params).amount
            sale_amount = (',销售总金额：' + str(sale_amount)) if sale_amount else ''
        # 统计"已消费"退款明细
        if form.kind.value == 2:
            sql = 'select goods_name, refund_at as time, sales_price, purchase_price, refund_value as amount, ' \
                  '(purchase_price-refund_value) as profit, commission, order_no, order_id, distr_shop_id from item where sales_id=%s ' \
                  'and refund_at is not null and used_at is not null '
            sum_sql = 'select sum(refund_value) amount,sum(commission) commission,sum(purchase_price-refund_value) as total ' \
                      'from item where sales_id=%s and refund_at is not null and used_at is not null '
            kind = '-已消费退款负利润汇总：'
            kind0 = '退款总金额：'
            kind1 = '渠道佣金：'

            if start:
                sql += 'and cast(refund_at as Date)>=%s '
                sum_sql += 'and cast(refund_at as Date)>=%s '
                params.append(start)
            if end:
                sql += 'and cast(refund_at as Date)<=%s '
                sum_sql += 'and cast(refund_at as Date)<=%s '
                params.append(end)
            sql += 'order by refund_at desc'
        # 统计刷单明细
        if form.kind.value == 3:
            sql = 'select goods_name, cheat_at as time, sales_price, purchase_price, sales_price as amount, ' \
                  '(cheat_value-purchase_price) as profit, commission, order_no, order_id, distr_shop_id from item where sales_id=%s ' \
                  'and cheat_at is not null '
            sum_sql = 'select sum(sales_price) amount,sum(commission) commission,sum(cheat_value-purchase_price) total ' \
                      'from item where sales_id=%s and cheat_at is not null '
            kind = '-刷单利润(手续费)汇总：'
            kind0 = '刷单总金额：'
            kind1 = '刷单佣金：'

            if start:
                sql += 'and cast(cheat_at as Date)>=%s '
                sum_sql += 'and cast(cheat_at as Date)>=%s '
                params.append(start)
            if end:
                sql += 'and cast(cheat_at as Date)<=%s '
                sum_sql += 'and cast(cheat_at as Date)<=%s '
                params.append(end)
            sql += 'order by cheat_at desc'

        if download == 'download':
            distr_shops = self.db.query('select id, name from distributor_shop')
            distr_shops = PropDict([(i.id, i.name) for i in distr_shops])
            page = self.db.query(sql, *params)
            title = [u'交易时间', u'订单号', u'渠道', u'商品名称', u'售价', u'进价', u'实际金额', u'利润', u'佣金']
            self.set_header('Content-type', 'application/excel')
            self.set_header('Content-Disposition', u'attachment; filename=' +
                                                   u'销售业绩-'+operator.name.decode('utf-8')+u'.xls')
            order_excel = Workbook(encoding='utf-8')
            write_order_excel = order_excel.add_sheet('0')

            for index, content in enumerate(title):
                write_order_excel.write(0, index, content)

            range_list = ['time', 'order_no', 'distr_shop_id', 'goods_name', 'sales_price', 'purchase_price', 'amount',
                          'profit', 'commission']

            for i, item in enumerate(page):
                for j, content in enumerate(range_list):
                    v = item.get(content, '')
                    v = v if v else 0
                    if content == 'time':
                        v = str(v)
                    if content == 'distr_shop_id':
                        v = distr_shops.get(item.get(content))
                    write_order_excel.write(i + 1, j, v)

            stream = StringIO.StringIO()
            order_excel.save(stream)
            self.write(stream.getvalue())
        else:
            page = Paginator(self, sql, params)
            summary = self.db.get(sum_sql, *params)
            sum_total = summary.total if summary.total else '0'
            sum_commission = summary.commission if summary.commission else '0'
            self.render("finance/profit.html", form=form, page=page, name=operator.name, total=kind + str(sum_total),
                        amount=kind0 + str(summary.amount), sale_amount=sale_amount,
                        sum_commission=kind1 + str(sum_commission))
