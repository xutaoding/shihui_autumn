# -*- coding: utf-8 -*-

from .. import BaseHandler
from voluptuous import Schema
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator
from .. import require

search_list = Schema({
    'supplier_name': str,
    'supplier': str,
    'goods': str,
})


class RecommendList(BaseHandler):
    @require()
    def get(self):
        form = Form(self.request.arguments, search_list)
        unrecommend_sql = """select g.id, g.short_name, g.created_at, g.purchase_price, g.sales_price
                             from goods g join supplier s on g.supplier_id = s.id
                             where g.off_sale_at > NOW() and g.deleted = 0
                             and g.id not in  (select goods_id from ktv_product_goods
                                               union select gpp.goods_id from goods_property gpp where gpp.name = 'hidden' and gpp.value = 1
                                               union select gq.goods_id from goods_property gq where gq.name = 'recommend' and gq.value = 1) """

        params = []

        if form.supplier.value:
            unrecommend_sql += 'and g.supplier_id = %s '
            params.append(form.supplier.value)

        if form.goods.value:
            unrecommend_sql += 'and g.short_name like %s '
            params.append('%' + form.goods.value + '%')

        unrecommend_sql += 'order by g.created_at desc '

        page = Paginator(self, unrecommend_sql, params)

        recommend_sql = """select distinct(g.id), g.short_name, g.created_at, g.purchase_price, g.sales_price
                           from goods g
                           join (select gpp.goods_id from goods_property gpp where gpp.name = 'recommend' and gpp.value = 1 and gpp.goods_id not in
                                (select gq.goods_id from goods_property gq where gq.name='hidden' and gq.value = 1)) gp on gp.goods_id = g.id
                           where g.off_sale_at > NOW() and g.deleted = 0
                           and g.id not in (select goods_id from ktv_product_goods) order by g.created_at desc """
        recommend_page = self.db.query(recommend_sql)

        self.render('seewi/recommend.html', form=form, page=page, recommend_page=recommend_page)


class AddRecommend(BaseHandler):
    @require('operator')
    def post(self):
        goods_id = self.get_argument('goods_id')
        recommend_len = len(self.db.query('select goods_id from goods_property where name="recommend" and value = 1'))
        if recommend_len >= 4:
            self.redirect(self.reverse_url('yibaiquan.recommend.list'))
            return

        pro = self.db.get('select g.* from goods_property g where g.goods_id = %s and g.name = "recommend" limit 1',
                          goods_id)

        if pro:
            self.db.execute('update goods_property set value = 1 where goods_id = %s and name = "recommend" ', goods_id)
        else:
            self.db.execute('insert into goods_property(goods_id, name, value) values(%s, "recommend", 1)', goods_id)

        self.redirect(self.reverse_url('yibaiquan.recommend.list'))


class CancelRecommend(BaseHandler):
    @require('operator')
    def post(self):
        goods_id = self.get_argument('goods_id')

        self.db.execute('update goods_property set value = 0 where goods_id = %s and name="recommend" ', goods_id)

        self.redirect(self.reverse_url('yibaiquan.recommend.list'))