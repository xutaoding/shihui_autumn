# -*- coding: utf-8 -*-

from ..import BaseHandler
from ..import require
from datetime import datetime, date, timedelta
from autumn.utils import format_chart_data, generate_duration, json_dumps


class OnSale(BaseHandler):
    @require()
    def get(self):
        goods_status = self.db.query('select ds.name, count(1) c '
                                     'from goods_distributor_shop gds, distributor_shop ds '
                                     'where gds.distributor_shop_id=ds.id and gds.status="ON_SALE" and ds.deleted=0 '
                                     'group by gds.distributor_shop_id ')
        total_goods = self.db.get('select count(distinct(goods_id)) as total '
                                  'from goods_distributor_shop where status="ON_SALE"')
        self.render('goods/on_sale.html', goods_status=goods_status, total_goods=total_goods)

    @require()
    def post(self):
        start_arg = self.get_argument('start', '')
        end_arg = self.get_argument('end', '')
        # 没指定日期，默认显示7天
        if not start_arg or not end_arg:
            today = date.today()
            start = today - timedelta(days=6)
            end = today - timedelta(days=0)
        else:
            start = datetime.strptime(start_arg, '%Y-%m-%d').date()
            end = datetime.strptime(end_arg, '%Y-%m-%d').date()
        onsale_sql = """
        select count(id) as amount, cast(onsale_at as Date) as archive_date
        from goods_distributor_shop where status="ON_SALE" and onsale_at is not NULL
        and cast(onsale_at as DATE)>=%s and cast(onsale_at as DATE)<=%s
        group by archive_date order by archive_date asc
        """
        offsale_sql = """
        select count(id) as amount, cast(offsale_at as Date) as archive_date
        from goods_distributor_shop where status="OFF_SALE" and offsale_at is not NULL
        and cast(offsale_at as DATE)>=%s and cast(offsale_at as DATE)<=%s
        group by archive_date order by archive_date asc
        """

        onsale_amount = self.db.query(onsale_sql, start, end)
        offsale_amount = self.db.query(offsale_sql, start, end)
        categories, start, end = generate_duration(start_arg, end_arg)
        onsale_data = format_chart_data(onsale_amount, start, categories)
        offsale_data = format_chart_data(offsale_amount, start, categories)

        data = [
            {
                'name': '上架商品数量',
                'data': onsale_data
            },
            {
                'name': '下架商品数量',
                'data': offsale_data
            },
        ]

        self.write(json_dumps(data, decimal_fmt=float))
