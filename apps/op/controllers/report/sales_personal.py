# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from autumn.utils import json_dumps, generate_duration, format_chart_data


class Summary(BaseHandler):
    """销售所有信息汇总趋势图"""
    @require()
    def get(self):
        self.render('report/sales_personal_summary.html')

    @require()
    def post(self):
        user = self.get_current_user()
        start_arg = self.get_argument('start', '')
        end_arg = self.get_argument('end', '')
        total = self.get_argument('total', '')  # 用来分辨是销售人员查询个人，还是查询所有
        data = []
        extend_sql = ''
        categories, start, end = generate_duration(start_arg, end_arg)

        # 没有total, 需查询销售人员关联的商户
        if not total:
            related_suppliers = self.db.query('select id from supplier where sales_id=%s', user.id)
            ids = ','.join([str(item.id) for item in related_suppliers])
            # 没有关联商户,返回空数据
            if not ids:
                data.append({'name': '无数据', 'data': format_chart_data([], start, categories)})
                self.write(json_dumps(data, decimal_fmt=float))
                return
            extend_sql = ' and sp_id in (' + ids + ') '

        # 该销售人员旗下所有商户的'销售'金额数据按日归档
        sales_sql = 'select cast(i.created_at as DATE) as archive_date, sum(payment) as amount from item i ' \
                    'where cast(i.created_at as DATE)>=%s and cast(i.created_at as DATE)<=%s ' \
                    + extend_sql + 'group by archive_date order by archive_date asc'
        sales_amount = self.db.query(sales_sql, start, end)
        sales_data = format_chart_data(sales_amount, start, categories)

        # 该销售人员旗下所有商户的'消费'金额数据按日归档
        consumed_sql = 'select cast(i.used_at as DATE) as archive_date, sum(payment) as amount from item i ' \
                       'where i.used_at is not null and cast(i.used_at as DATE)>=%s and cast(i.used_at as DATE)<=%s ' \
                       + extend_sql + 'group by archive_date order by archive_date asc'
        consumed_amount = self.db.query(consumed_sql, start, end)
        consumed_data = format_chart_data(consumed_amount, start, categories)

        # 该销售人员旗下所有商户'退款'金额数据按日归档
        refund_sql = 'select cast(i.refund_at as DATE) as archive_date, sum(refund_value) as amount from item i ' \
                     'where i.refund_at is not null and cast(i.refund_at as DATE)>=%s and cast(i.refund_at as DATE)<=%s ' \
                     + extend_sql + 'group by archive_date order by archive_date asc'
        refund_amount = self.db.query(refund_sql, start, end)
        refund_data = format_chart_data(refund_amount, start, categories)

        # 刷单数据
        cheat_sql = 'select cast(i.cheat_at as DATE) as archive_date, sum(payment) as amount from item i ' \
                    'where i.cheat_at is not null and cast(i.cheat_at as DATE)>=%s and cast(i.cheat_at as DATE)<=%s ' \
                    + extend_sql + 'group by archive_date order by archive_date asc'
        cheat_amount = self.db.query(cheat_sql, start, end)
        cheat_data = format_chart_data(cheat_amount, start, categories)

        # 准备回传数据
        data = [
            {
                'name': '销售金额',
                'data': sales_data
            },
            {
                'name': '消费金额',
                'data': consumed_data
            },
            {
                'name': '退款金额',
                'data': refund_data
            },
            {
                'name': '刷单金额',
                'data': cheat_data
            },
        ]
        self.write(json_dumps(data, decimal_fmt=float))


class SupplierSide(BaseHandler):
    """销售旗下商户销售额趋势图"""
    def get(self):
        self.render('report/sales_personal_supplier.html')

    def post(self):
        user = self.get_current_user()
        supplier_id = self.get_argument('id', '')
        start_arg = self.get_argument('start', '')
        end_arg = self.get_argument('end', '')
        total = self.get_argument('total', '')  # 用来分辨是销售人员查询个人，还是查询所有
        data = []
        categories, start, end = generate_duration(start_arg, end_arg)

        # 没有total, 需查询销售人员关联的商户
        if not total:
            # 查询商家
            supplier = self.db.get('select short_name, id from supplier where sales_id=%s and deleted=0 '
                                   'and id=%s', user.id, supplier_id)
        else:
            supplier = self.db.get('select short_name, id from supplier where id=%s and deleted=0', supplier_id)
        # 商家不存在
        if not supplier:
            data.append({'name': '商家不存在或者您不是该商家的关联销售人员', 'data': format_chart_data([], start, categories)})
            self.write(json_dumps(data, decimal_fmt=float))
            return

        # 对商家，根据日期统计销售
        sales_amount = self.db.query('select cast(i.created_at as DATE) as archive_date, sum(payment) as amount '
                                     'from item i where sp_id=%s '
                                     'and cast(i.created_at as DATE)>=%s and cast(i.created_at as DATE)<=%s '
                                     'group by archive_date order by archive_date asc',
                                     supplier_id, start, end)
        # 如果有销售数据
        if sales_amount:
            # 补全时间轴
            sales_data = format_chart_data(sales_amount, start, categories)
            # 添加到返回的数据列表上
            data.append({'name': supplier.short_name, 'data': sales_data})

        # 没有数据,返回空数据
        if not data:
            data.append({'name': '无数据', 'data': format_chart_data([], start, categories)})

        self.write(json_dumps(data, decimal_fmt=float))


class ChannelSide(BaseHandler):
    """销售旗下所有商户的商品在不同渠道的趋势图"""
    def get(self):
        self.render('report/sales_personal_channel.html')

    def post(self):
        user = self.get_current_user()
        start_arg = self.get_argument('start', '')
        end_arg = self.get_argument('end', '')
        total = self.get_argument('total', '')  # 用来分辨是销售人员查询个人，还是查询所有
        data = []
        extend_sql = ''
        categories, start, end = generate_duration(start_arg, end_arg)

        # 没有total, 需查询销售人员关联的商户
        if not total:
            related_suppliers = self.db.query('select id from supplier where sales_id=%s', user.id)
            ids = ','.join([str(item.id) for item in related_suppliers])
            # 没有关联商户,返回空数据
            if not ids:
                data.append({'name': '无数据', 'data': format_chart_data([], start, categories)})
                self.write(json_dumps(data, decimal_fmt=float))
                return
            extend_sql = ' and sp_id in (' + ids + ') '

        # 该销售人员旗下所有商户的所有商品在分销商中的销售的数据按日归档
        sql = 'select cast(i.created_at as DATE) as archive_date, sum(payment) as amount, distr_shop_id from item i ' \
              'where cast(i.created_at as DATE)>=%s and cast(i.created_at as DATE)<=%s ' \
              + extend_sql + 'group by archive_date, distr_shop_id order by archive_date, distr_shop_id asc '
        account_sequence = self.db.query(sql, start, end)

        # 获得所有分销渠道信息
        account_info = self.db.query('select id, name from distributor_shop where deleted = 0')
        data = []
        # 生成有销售数据的分销渠道的系列, 按分销渠道，一个个查
        for item in account_info:
            temp_list = []
            for sequence in account_sequence:
                if sequence.distr_shop_id == item.id:
                    temp_list.append(sequence)
            if temp_list:
                # 将有销售数据的分销渠道生成数据
                data.append({'name': item.name, 'data': format_chart_data(temp_list, start, categories)})
        # 没有数据,返回空数据
        if not data:
            data.append({'name': '无数据', 'data': format_chart_data([], start, categories)})

        self.write(json_dumps(data, decimal_fmt=float))

