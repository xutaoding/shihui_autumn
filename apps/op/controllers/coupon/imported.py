# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
import logging
import re
from tornado.options import options
from voluptuous import Schema
from autumn.api import Jingdong
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator

list_schema = Schema({
    'supplier': str,
    'goods': str,
}, extra=True)


class Import(BaseHandler):
    @require('developer')
    def get(self):
        sql = """ select g.* from goods g where g.deleted = 0 and g.generate_type = 'IMPORT' """
        form = Form(self.request.arguments, list_schema)
        params = []

        if form.goods.value:
            sql += 'and g.name like %s '
            params.append('%' + form.goods.value + '%')

        page = Paginator(self, sql, params)
        self.render('coupon/imported.html', page=page, form=form)


class ImportCoupon(BaseHandler):
    """ 处理导入券 """
    @require('developer')
    def get(self, goods_id):
        goods = self.db.get('select g.* from goods g where g.deleted = 0 and g.id =%s', goods_id)
        self.render('coupon/import_coupon.html', goods=goods)

    @require('developer')
    def post(self, goods_id):
        # 读取输入内容
        import_text = self.get_argument('coupon_text', '')
        lines = import_text.splitlines()
        ptn = re.compile(r'^[a-zA-Z0-9]+(,[a-zA-Z0-9]*)?$')  # 只允许 a / a, / a,b 三种形式
        invalid_coupons = []   # 储存非法导入券
        imported_coupons = []  # 储存导入成功的券
        existing_coupons = []  # 储存重复的券
        coupons = []           # 临时存储合法导入券

        # 处理每一行导入券
        for line in lines:
            # 去空格
            line = line.strip().replace(' ', '')
            # 校验输入文字的合法性
            valid_line = re.match(ptn, line)
            if valid_line:
                # 分割券号密码
                coupon = (line + ',').split(',')
                coupons.append(tuple(coupon[:2]))
            else:
                invalid_coupons.append(line)

        goods = self.db.get('select g.* from goods g where g.deleted = 0 and g.id =%s', goods_id)
        if coupons:
            imported_coupons, existing_coupons = self.insert_import_coupon(goods, coupons)

        self.render('coupon/import_result.html', goods_name=goods.short_name, invalid_coupons=invalid_coupons,
                    existing_coupons=existing_coupons, imported_coupons=imported_coupons)

    def insert_import_coupon(self, goods, coupons):
        """ 插入数据库 """
        sql = """insert into coupon_imported (goods_id, coupon_sn, coupon_pwd, used, created_at) values """
        update_stock = """update goods set stock=stock+%s where goods.id=%s """
        params = []
        existing_coupons = []
        imported_coupons = []
        
        for coupon in coupons:
            # 检查是否有券号重复
            if not self.db.get('select id from item_coupon where sn=%s', coupon[0]):
                sql += '(%s, %s, %s, 0, now()),'
                params.append(goods.id)
                params.extend(coupon)
                imported_coupons.append(coupon[0])
            else:
                existing_coupons.append(coupon[0])

        # 有合法的导入券时才执行数据库操作
        if params:
            # 导入券号密码
            self.db.execute(sql[:-1], *params)
            # 更新库存
            self.db.execute(update_stock, len(imported_coupons), goods.id)

        return imported_coupons, existing_coupons


class JDImportCoupon(BaseHandler):
    """京东导入券查询"""
    @require('developer')
    def get(self):
        self.render('coupon/imported_jd.html', coupons=None)

    def post(self):
        order_id = self.get_argument('jd_order_id', '')
        coupon = self.get_argument('jd_coupon_no', '')

        # 根据订单号查券
        if order_id:
            coupons = []
            i = 0
            while True:
                jd_coupons = Jingdong(
                    'getCouponsList',
                    options.jingdong_fx_vender_id,
                    options.jingdong_fx_vender_key,
                    options.jingdong_fx_secret_key
                )
                response_coupons = jd_coupons.sync_fetch(order_id=order_id, start=i*100, count=100)
                jd_coupons.parse_response(response_coupons)
                if jd_coupons.is_ok():
                    current_coupons = [{'coupon_sn': c.findtext('CouponId'), 'coupon_pwd': c.findtext('CouponPwd'),
                                       'status': c.findtext('CouponStatus')}
                                       for c in jd_coupons.message.findall('Coupons/Coupon')]
                    coupons.extend(current_coupons)
                    i += 1
                    if len(current_coupons) != 100:
                        break
                else:
                    logging.error('failed to query jd_coupons for jd_order_id: %s', order_id)
                    break

            self.render('coupon/imported_jd.html', coupons=coupons)
            return
        # 根据券号查
        if coupon:
            jd = Jingdong(
                'queryCouponStatus',
                options.jingdong_fx_vender_id,
                options.jingdong_fx_vender_key,
                options.jingdong_fx_secret_key
            )
            resp = jd.sync_fetch(coupon=coupon)
            jd.parse_response(resp)
            if jd.is_ok():
                jd_coupons = [{'coupon_sn': c.findtext('CouponId'), 'coupon_pwd': c.findtext('CouponPwd'),
                               'status': str(c.findtext('CouponStatus'))}
                              for c in jd.message.findall('Coupons/Coupon')]
                self.render('coupon/imported_jd.html', coupons=jd_coupons)
                return

        self.render('coupon/imported_jd.html', coupons=None)

