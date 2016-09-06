# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from . import sales_personal
from autumn.utils import json_dumps, generate_duration, format_chart_data
from datetime import datetime, date, timedelta


class Show(BaseHandler):
    """BOSS目录下报表的销售趋势汇总"""
    @require('developer_mgr', 'developer', 'operator_mgr', 'sales_manager', 'service_mgr', 'finance_mgr')
    def get(self):
        self.render('report/index.html')


class SupplierTendency(BaseHandler):
    """BOSS目录下报表的商户分类趋势"""
    @require('developer_mgr', 'developer', 'operator_mgr', 'sales_manager', 'service_mgr', 'finance_mgr')
    def get(self):
        today = datetime.now().date()
        start = today - timedelta(days=30)
        self.render('report/tendency_supplier.html', start=start, end=today)


class GoodsTendency(BaseHandler):
    """BOSS目录下报表的商品分类趋势"""
    @require('developer_mgr', 'developer', 'operator_mgr', 'sales_manager', 'service_mgr', 'finance_mgr')
    def get(self):
        today = datetime.now().date()
        start = today - timedelta(days=30)
        self.render('report/tendency_goods.html', start=start, end=today)

    def post(self):
        goods_id = self.get_argument('id', '')
        start_arg = self.get_argument('start', '')
        end_arg = self.get_argument('end', '')
        data = []
        categories, start, end = generate_duration(start_arg, end_arg)

        goods = self.db.get('select id, short_name from goods where id=%s and deleted=0', goods_id)
        # 查不到商品，返回
        if not goods:
            data.append({'name': '商品不存在',
                         'data': format_chart_data([], start, categories)})

        goods_amount = self.db.query('select cast(i.created_at as DATE) as archive_date, sum(payment) as amount from '
                                     'item i where goods_id=%s and cast(i.created_at as DATE)>=%s '
                                     'and cast(i.created_at as DATE)<=%s '
                                     'group by archive_date order by archive_date asc',
                                     goods_id, start, end)

        # 如果有销售数据
        if goods_amount:
            # 补全时间轴
            sales_data = format_chart_data(goods_amount, start, categories)
            # 添加到返回的数据列表上
            data.append({'name': goods.short_name, 'data': sales_data})

        # 没有数据,返回空数据
        if not data:
            data.append({'name': '无数据', 'data': format_chart_data([], start, categories)})

        self.write(json_dumps(data, decimal_fmt=float))


class Ranking(BaseHandler):
    """BOSS目录下报表的排名"""
    @require('developer_mgr', 'developer', 'operator_mgr', 'sales_manager', 'service_mgr', 'finance_mgr')
    def get(self):
        start_arg = self.get_argument('start', '')
        end_arg = self.get_argument('end', '')
        # 没指定日期，默认显示7天
        if not start_arg or not end_arg:
            today = date.today()
            start = today - timedelta(days=7)
            end = today - timedelta(days=1)
        else:
            start = datetime.strptime(start_arg, '%Y-%m-%d').date()
            end = datetime.strptime(end_arg, '%Y-%m-%d').date()

        # 销售人员业绩排名
        sales_data = self.db.query('select o.name, sum(payment) as sales, count(payment) as sales_count, '
                                   'sum(refund_value) as refund, count(refund_at) as refund_count, '
                                   'sum(CASE WHEN cheat_at is NULL THEN 0.00 ELSE sales_price END) as cheat, '
                                   'count(cheat_at) as cheat_count from item i, operator o where i.sales_id=o.id '
                                   'and cast(i.created_at as DATE)>=%s and cast(i.created_at as DATE)<=%s '
                                   'group by sales_id order by sales desc limit 10', start, end)
        # 商户销售排名
        supplier_data = self.db.query('select sp.short_name, sum(payment) as sales, count(i.created_at) as sales_count, '
                                      'sum(refund_value) as refund, count(refund_at) as refund_count, '
                                      'sum(CASE WHEN cheat_at is NULL THEN 0.00 ELSE sales_price END) as cheat, '
                                      'count(cheat_at) as cheat_count from item i, supplier sp where i.sp_id=sp.id and '
                                      'cast(i.created_at as DATE)>=%s and cast(i.created_at as DATE)<=%s '
                                      'group by sp_id order by sales desc limit 10', start, end)
        # 商品销售排名
        goods_data = self.db.query('select g.short_name, sum(payment) as sales, count(i.created_at) as sales_count, '
                                   'sum(refund_value) as refund, count(refund_at) as refund_count, '
                                   'sum(CASE WHEN cheat_at is NULL THEN 0.00 ELSE i.sales_price END) as cheat, '
                                   'count(cheat_at) as cheat_count from item i, goods g where i.goods_id=g.id '
                                   'and cast(i.created_at as DATE)>=%s and cast(i.created_at as DATE)<=%s '
                                   'group by goods_id order by sales desc limit 10', start, end)

        self.render('report/ranking.html', start=start, end=end,
                    sales_data=sales_data, supplier_data=supplier_data, goods_data=goods_data)


class Prepayment(BaseHandler):
    """BOSS目录下报表的预付款使用趋势"""
    @require('developer_mgr', 'developer', 'operator_mgr', 'sales_manager', 'service_mgr', 'finance_mgr')
    def get(self):
        suppliers = self.db.query('select sp.short_name, sp.id from external_money em, supplier sp '
                                  'where sp.id=em.uid and em.deleted=0 and em.source<2 and em.type=1 '
                                  'group by sp.short_name, sp.id')
        self.render('report/prepayment.html', suppliers=suppliers)

    @require('developer_mgr', 'developer', 'operator_mgr', 'sales_manager', 'service_mgr', 'finance_mgr')
    def post(self):
        supplier_id = self.get_argument('supplier_id', '')
        data = []

        # supplier id 不存在
        if not supplier_id:
            data.append({
                'error': '没有该商户数据',
                'name': '没有该商户数据',
                'data': ''
            })
            return

        prepayment = self.db.get('select sum(amount) as amount from external_money where uid=%s and type=1 '
                                 'and deleted=0 and source<2', supplier_id)
        if not prepayment:
            data.append({
                'error': '没有该商户数据',
                'name': '没有该商户数据',
                'data': ''
            })
            return

        total = prepayment.amount
        start = self.db.get('select cast(created_at as DATE) as start from external_money where uid=%s and type=1 '
                            'and deleted=0 and source<2 order by created_at asc limit 1', supplier_id).start
        end = datetime.now().date()
        duration = (end - start).days + 1
        categories = [(start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(duration)]

        usage = self.db.query('select sum(i.purchase_price) as amount, cast(i.created_at as DATE) as archive_date from item i '
                              'where sp_id=%s and cast(i.created_at as DATE)>=%s and cast(i.created_at as DATE)<=%s '
                              'group by cast(i.created_at as DATE) order by cast(i.created_at as DATE) asc',
                              supplier_id, start, end)

        if usage:
            result = []
            length = len(usage)
            index = 0
            current_day = start
            for i in range(len(categories)):
                if index < length and current_day == usage[index].archive_date:
                    total = total - usage[index].amount
                    result.append(total)
                    index += 1
                else:
                    result.append(total)
                current_day += timedelta(days=1)

            data.append({
                        'name': '预付款剩余',
                        'data': [[categories[i], result[i]] for i in range(len(categories))]
                        })
        else:
            data.append({
                        'name': '预付款剩余',
                        'data': [[cate, total] for cate in categories]
                        })

        self.write(json_dumps(data, decimal_fmt=float))


