# -*- coding: utf-8 -*-
from .. import BaseHandler
from .. import require
import StringIO
from xlwt import Workbook
from autumn.torn.form import Form, Date
from voluptuous import Schema
from datetime import date, timedelta, datetime
from autumn.torn.paginator import Paginator
from autumn.utils import PropDict
from autumn.utils.dt import ceiling, truncate

list_schema = Schema({
    'start_date': Date('%Y-%m-%d'),
    'end_date': Date('%Y-%m-%d'),
    'supplier': str,
    'supplier_name': str,
    'summary_type': str,
    'action': str,
}, extra=True)


class ChannelGoods(BaseHandler):
    """渠道商品销售明细"""
    @require()
    def get(self):
        form = Form(self.request.arguments, list_schema)
        if not form.summary_type.value:
            form.summary_type['value'] = 'goods_type'

        distr_shops = self.db.query('select id, name from distributor_shop where deleted = 0 ')

        common_fields = """
            i.goods_name, i.goods_id,
            sum(case when i.created_at <=%s and i.created_at >=%s then 1 else 0 end) as sales_count,
            sum(case when i.created_at <=%s and i.created_at >=%s then i.payment else 0 end) as sales_amount,
            sum(case when i.created_at <=%s and i.created_at >=%s then i.purchase_price else 0 end) as cost,
            sum(case when i.created_at <=%s and i.created_at >=%s then i.payment-i.purchase_price else 0 end) as profit,
            sum(case when i.used_at <=%s and i.used_at >=%s then 1 else 0 end) as used,
            sum(case when i.used_at <=%s and i.used_at >=%s then i.payment else 0 end) as used_amount,
            sum(case when i.refund_at <=%s and i.refund_at >=%s and used_at is not NULL then 1 else 0 end) as vrefund,
            sum(case when i.refund_at <=%s and i.refund_at >=%s and used_at is not NULL then i.refund_value else 0 end) as vrefund_amount,
            sum(case when i.refund_at <=%s and i.refund_at >=%s and used_at is NULL then 1 else 0 end) as refund,
            sum(case when i.refund_at <=%s and i.refund_at >=%s and used_at is NULL then i.refund_value else 0 end) as refund_amount,
            sum(case when i.cheat_at <=%s and i.cheat_at >=%s then 1 else 0 end) as cheat,
            sum(case when i.cheat_at <=%s and i.cheat_at >=%s then i.payment else 0 end) as cheat_amount,
            sum(case when i.cheat_at <=%s and i.cheat_at >=%s then i.cheat_value-i.purchase_price else 0 end) as cheat_profit
        """

        sql = ''
        sql_foot = ''
        if form.summary_type.value == 'goods_type':
            sql += 'select gc.name category_name, NULL as dsid, ' + common_fields
            sql += """ from item i, goods g, goods_category gct, goods_category gc
                    where i.goods_id = g.id and g.category_id=gct.id and gct.parent_id=gc.id
                  """
            sql_foot = 'group by i.goods_id order by gc.id '
        elif form.summary_type.value == 'distr_shop':
            sql += 'select ds.name distr_shop_name, ds.id dsid, ' + common_fields
            sql += """ from item i, distributor_shop ds where i.distr_shop_id=ds.id """
            sql_foot = 'group by ds.id, i.goods_id order by ds.id '

        sql += ' and (i.created_at <=%s and i.created_at >=%s or ' \
               ' i.used_at <=%s and i.used_at >=%s or ' \
               ' i.refund_at <=%s and i.refund_at >=%s or ' \
               ' i.cheat_at <=%s and i.cheat_at >=%s ) '

        params = []
        # 未指定截止日期，默认为今天
        if not form.end_date.value:
            end = ceiling(datetime.today(), today=True)
            form.end_date.value = end
        else:
            end = form.end_date.value
        # 未指定开始日期，默认为最近7天
        if not form.start_date.value:
            start = truncate(datetime.today() - timedelta(days=6))
            form.start_date.value = start
        else:
            start = form.start_date.value

        for i in range(17):
            params.append(end)
            params.append(start)

        # 指定商户
        if form.supplier.value:
            sql += ' and i.sp_id=%s '
            params.append(form.supplier.value)

        sql += sql_foot

        if form.action.value == 'download':
            distr_shops = self.db.query('select id, name from distributor_shop')
            distr_shops = PropDict([(i.id, i.name) for i in distr_shops])
            page = self.db.query(sql, *params)
            title = [u'商品名称', u'销售数量', u'销售金额', u'成本', u'利润', u'已消费或发货',
                     u'消费金额', u'未消费退款数量', u'未消费退款金额', u'已消费退款数量', u'已消费退款金额',
                     u'刷单数量', u'刷单金额', u'刷单利润']
            range_list = ['goods_name', 'sales_count', 'sales_amount', 'cost', 'profit', 'used', 'used_amount',
                          'refund', 'refund_amount', 'vrefund', 'vrefund_amount', 'cheat', 'cheat_amount', 'cheat_profit']
            if form.summary_type.value == 'goods_type':
                title.append(u'大类')
                range_list.append('category_name')
            else:
                title.append(u'渠道')
                range_list.append('distr_shop_name')
            self.set_header('Content-type', 'application/excel')
            self.set_header('Content-Disposition', u'attachment; filename='+u'商品销售报表'+start+u'至'+end+u'.xls')
            order_excel = Workbook(encoding='utf-8')
            write_order_excel = order_excel.add_sheet('sheet0')

            for index, content in enumerate(title):
                write_order_excel.write(0, index, content)

            for i, item in enumerate(page):
                for j, content in enumerate(range_list):
                    v = item.get(content, '')
                    v = v if v else 0
                    write_order_excel.write(i + 1, j, v)

            stream = StringIO.StringIO()
            order_excel.save(stream)
            self.write(stream.getvalue())
            pass
        else:
            # 查询
            page = Paginator(self, sql, params)
            self.render('finance/channel_goods_report.html', form=form, page=page, distr_shops=distr_shops)
