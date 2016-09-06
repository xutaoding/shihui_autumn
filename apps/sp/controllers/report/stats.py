# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from autumn.torn.form import Form, Date
from autumn.utils import generate_duration, format_chart_data, json_dumps
from voluptuous import Schema
from datetime import date, timedelta

list_schema = Schema({
    'start_date': Date('%Y-%m-%d'),
    'end_date': Date('%Y-%m-%d'),
    'supplier_shop': str,
    'supplier_input': str,
    'summary_type': str,
}, extra=True)


class SalesReport(BaseHandler):
    """商品销售统计报表"""
    @require('manager')
    def get(self):
        supplier_id = self.current_user.supplier_id
        summary_type = self.get_argument('summary_type', '')
        if not summary_type:
            summary_type = 'goods_sales'
        form = Form(self.request.arguments, list_schema)
        # 查询
        result = data_query(self.db, form, supplier_id, summary_type)

        self.render('report/sales.html', form=form, supplier_id=supplier_id, page=result)


class ShopReport(BaseHandler):
    """门店统计报表"""
    @require('manager')
    def get(self):
        supplier_id = self.current_user.supplier_id
        summary_type = self.get_argument('summary_type', '')
        if not summary_type:
            summary_type = 'supplier_shop'
        form = Form(self.request.arguments, list_schema)
        # 查询
        result = data_query(self.db, form, supplier_id, summary_type)

        self.render('report/shop.html', form=form, supplier_id=supplier_id, page=result)


class ChannelReport(BaseHandler):
    """渠道销售报表"""
    @require('manager')
    def get(self):
        supplier_id = self.current_user.supplier_id
        summary_type = self.get_argument('summary_type', '')
        if not summary_type:
            summary_type = 'distr_shop'
        form = Form(self.request.arguments, list_schema)
        # 查询
        result = data_query(self.db, form, supplier_id, summary_type)

        self.render('report/channel.html', form=form, supplier_id=supplier_id, page=result)


class GetData(BaseHandler):
    """获取highchart图的数据"""
    # todo 3个if 可以优化合并成一个
    @require('manager')
    def post(self):
        # 获得Post参数
        start_arg = self.get_argument('start', '')
        end_arg = self.get_argument('end', '')
        summary_type = self.get_argument('summary_type', '')
        supplier_input = self.get_argument('supplier_input', '')
        supplier_id = self.current_user.supplier_id
        categories, start, end = generate_duration(start_arg, end_arg)
        # 初始化共同参数
        common_sql = ' cast(i.used_at as Date) as archive_date, sum(i.sales_price) as amount from item i ' \
                     'where used_at is not null and i.sp_id=%s and cast(i.used_at as Date) >= %s ' \
                     'and cast(i.used_at as Date) <= %s '
        group_sql = ' group by archive_date '
        order_sql = ' order by archive_date asc '
        params = [supplier_id, start, end]
        data = []  # 用来存储返回的数据
        # 准备不同请求的数据
        if summary_type == 'goods_sales':
            goods_sql = 'select id, short_name from goods where supplier_id=%s '
            goods_params = [supplier_id]
            # 根据输入的筛选条件，选出相应的goods id
            if supplier_input:
                goods_sql += ' and short_name like %s'
                goods_params.append('%'+supplier_input+'%')
            goods = self.db.query(goods_sql, *goods_params)
            sql = 'select i.goods_id, ' + common_sql
            if goods:
                sql += ' and i.goods_id in (' + ','.join([str(i.id) for i in goods]) + ') '
            sql = sql + group_sql + ', i.goods_id ' + order_sql
            result = self.db.query(sql, *params)
            for g in goods:
                current_line = []
                for r in result:
                    if r.goods_id == g.id:
                        current_line.append(r)
                if current_line:
                    data.append({'name': g.short_name, 'data': format_chart_data(current_line, start, categories)})
        elif summary_type == 'supplier_shop':
            shop_sql = 'select id, name from supplier_shop where supplier_id=%s '
            shop_params = [supplier_id]
            # 根据输入的门店筛选
            if supplier_input:
                shop_sql += ' and name like %s'
                shop_params.append('%' + supplier_input + '%')
            shops = self.db.query(shop_sql, *shop_params)
            sql = 'select i.sp_shop_id, ' + common_sql
            if shops:
                sql += ' and i.sp_shop_id in (' + ','.join([str(i.id) for i in shops]) + ') '
            sql = sql + group_sql + ', i.sp_shop_id ' + order_sql
            result = self.db.query(sql, *params)
            for s in shops:
                current_line = []
                for r in result:
                    if r.sp_shop_id == s.id:
                        current_line.append(r)
                if current_line:
                    data.append({'name': s.name, 'data': format_chart_data(current_line, start, categories)})
        elif summary_type == 'distr_shop':
            distr_sql = 'select id, name from distributor_shop where 1=1 '
            distr_params = []
            if supplier_input:
                distr_sql += ' and name like %s'
                distr_params.append('%' + supplier_input + '%')
            if distr_params:
                distr = self.db.query(distr_sql, *distr_sql)
            else:
                distr = self.db.query(distr_sql)
            sql = 'select i.distr_shop_id,' + common_sql
            if distr:
                sql += ' and i.distr_shop_id in (' + ','.join([str(i.id) for i in distr]) + ') '
            sql = sql + group_sql + ', i.distr_shop_id ' + order_sql
            result = self.db.query(sql, *params)
            for d in distr:
                current_line = []
                for r in result:
                    if r.distr_shop_id == d.id:
                        current_line.append(r)
                if current_line:
                    data.append({'name': d.name, 'data': format_chart_data(current_line, start, categories)})

        # 没有数据,返回空数据
        if not data:
            data.append({'name': '无数据', 'data': format_chart_data([], start, categories)})
        self.write(json_dumps(data, decimal_fmt=float))
        pass


def data_query(db, form, supplier_id, summary_type):

    common_fields = """
            i.goods_name, i.goods_id,
            count(i.used_at) as used, sum(case when i.used_at then i.sales_price else 0 end) as used_amount,
            count(i.refund_at) as refund, sum(case when i.refund_at then i.refund_value else 0 end) as refund_amount,
            count(i.cheat_at) as cheat, sum(case when i.cheat_at then i.cheat_value else 0 end) as cheat_amount
        """

    sql = ''
    sql_foot = ''
    params = []
    if summary_type == 'goods_sales':
        sql += ' select ' + common_fields
        sql += """ from item i
                   where used_at is not null"""
        if form.supplier_input.value:
            sql += ' and i.goods_name like %s'
            params.append('%' + form.supplier_input.value + '%')
        sql_foot = 'group by i.goods_id order by sum(case when i.used_at then i.sales_price else 0 end) desc'
    elif summary_type == 'supplier_shop':
        sql += 'select sp.name shop_name, ' + common_fields
        sql += """ from item i, supplier_shop sp
                   where i.sp_shop_id = sp.id and used_at is not null
               """
        if form.supplier_input.value:
            sql += ' and i.sp_shop_id=%s '
            params.append(form.supplier_shop.value)
        sql_foot = 'group by i.sp_shop_id order by sum(case when i.used_at then i.sales_price else 0 end) desc'
    elif summary_type == 'distr_shop':
        sql += 'select ds.name distr_shop_name, ' + common_fields
        sql += """ from item i, distributor_shop ds where i.distr_shop_id=ds.id """
        if form.supplier_input.value:
            sql += ' and ds.name like %s '
            params.append('%' + form.supplier_input.value + '%')
        sql_foot = ' group by ds.id order by sum(case when i.used_at then i.sales_price else 0 end) desc '

    sql += ' and cast(i.used_at as Date)<=%s and cast(i.used_at as Date)>=%s '

    # 未指定截止日期，默认为今天
    if not form.end_date.value:
        end = date.today()
        form.end_date.value = end
        params.append(end)
    else:
        end = form.end_date.value
        params.append(form.end_date.value)
        # 未指定开始日期，默认为最近7天
    if not form.start_date.value:
        start = end - timedelta(days=6)
        form.start_date.value = start
        params.append(start)
    else:
        params.append(form.start_date.value)

    # 指定商户
    sql += ' and i.sp_id=%s '
    params.append(supplier_id)

    sql += sql_foot

    result = db.query(sql, *params)
    return result
