# -*- coding: utf-8 -*-


import json
from .. import BaseHandler
from tornado.web import HTTPError
from autumn.torn.paginator import Paginator
from tornado.web import authenticated
from autumn.goods import img_url
from autumn.api.alipay import build_token_req_data, build_request, build_pay_req_data
import random
import string
from datetime import datetime, timedelta
from autumn.utils import json_dumps


class List(BaseHandler):
    """微商城商品列表"""
    @authenticated
    def get(self):
        user = self.current_user
        # 筛选可以在手机端显示的商品，首先必须是上架状态， 如果有预计上下架，必须在预计上下架范围内，券有效期不能过期
        sql = """select g.id, g.img_paths, g.short_name, g.face_value, g.sales_price from goods g, goods_property gp
                 where g.id = gp.goods_id and gp.name = "is_wx_on_sale" and gp.value = "1" and supplier_id = %s
                 and deleted = 0 and (g.on_sale_at is null or g.on_sale_at is not null and g.on_sale_at < NOW()) and
                 (g.off_sale_at is null or g.off_sale_at is not null and g.off_sale_at > NOW()) and
                 (g.expire_at is null or g.expire_at is not null and g.expire_at > NOW())
                 order by g.rank desc"""

        goods_list = Paginator(self, sql, [user.sp_id], 8)

        self.render('mall/list.html', goods_list=goods_list, img_url=img_url, json=json)


class GoodsDetail(BaseHandler):
    """微商城商品详情页面"""
    @authenticated
    def get(self, goods_id):
        user = self.get_current_user()
        goods = self.db.get('select g.* from goods g, goods_property gp '
                            'where g.id=%s and g.supplier_id=%s and deleted=0 and gp.goods_id=g.id and '
                            'gp.name="is_wx_on_sale" and gp.value="1" ',
                            goods_id, user.sp_id)
        img = json.loads(goods.img_paths)['720x400']
        if goods:
            self.render('mall/goods_detail.html', goods=goods, img_url=img_url, img=img)
        else:
            raise HTTPError(404)


class OrderInfo(BaseHandler):
    """微商城购买信息填写页面"""
    @authenticated
    def get(self):
        goods_id = self.get_argument('goods_id', '')
        user = self.get_current_user()
        goods = self.db.get('select * from goods where id=%s and supplier_id=%s and deleted=0', goods_id, user.sp_id)
        if not goods:
            raise HTTPError(404)
        else:
            self.render('mall/goods_order.html', goods=goods, img_url=img_url)

    @authenticated
    def post(self):
        num = self.get_argument('num')
        phone = self.get_argument('phone')
        type = self.get_argument('type')

        goods_id = self.get_argument('goods_id')
        goods = self.db.get('select id, sales_price, postage, max_buy, stock from goods '
                            'where id = %s and supplier_id = %s', goods_id, self.current_user.sp_id)

        if not goods:
            raise HTTPError(404)

        orders = self.db.query('select count(oi.num) num from orders o, order_item oi '
                               'where o.id = oi.order_id and o.distributor_user_id = %s and oi.goods_id = %s',
                               self.current_user.wx_id, goods.id)

        if goods.max_buy and goods.max_buy < (orders.num + int(num)):
            self.render('mall/error.html', goods_id=goods.id, reason='超过了最大购买数量')
            return
        elif goods.stock < int(num):
            self.render('mall/error.html', goods_id=goods.id, reason='商品库存不足')
            return
        else:
            # 如果符合条件，则减去商品库存
            self.db.execute('update goods set stock = stock - %s where id = %s', num, goods.id)

        # 如果是实物的话，先生成物流信息
        if type == 'R':
            address = self.get_argument('address')
            zip_code = self.get_argument('zip_code')
            name = self.get_argument('name')

            shipping_sql = """insert into order_shipping_info(address, created_at, phone, receiver, zip_code, freight)
                              values(%s, NOW(), %s, %s, %s, %s)"""

            shipping_id = self.db.execute(shipping_sql, address, phone, name, zip_code, goods.postage)

        # 生成订单号
        while True:
            order_no = '%s%s' % (
                random.choice('123456789'), ''.join([random.choice(string.digits) for i in range(7)]))
            # 没有重复，停止
            if not self.db.get('select id from orders where order_no=%s', order_no):
                break

        order_insert_sql = """insert into orders(distributor_shop_id, created_at, order_no, total_fee, payment,
                            post_fee, discount_fee, status, mobile, distributor_user_id)
                            values(%s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s)"""

        post_fee = 0 if type == 'E' else goods.postage
        discount_fee = 0
        total_fee = int(num) * goods.sales_price
        payment = total_fee + post_fee + discount_fee

        distributor_shop_id = self.db.get('select value from supplier_property where name="wx_shop_id" '
                                          'and sp_id = %s', self.current_user.sp_id)['value']
        order_id = self.db.execute(order_insert_sql, distributor_shop_id, order_no, total_fee, payment,
                                   post_fee, discount_fee, 0, phone, self.current_user.wx_id)

        item_insert_sql = """insert into order_item(distributor_shop_id, goods_id, num, order_id, sales_price %s)
                            values(%%s, %%s, %%s, %%s, %%s %s)"""
        item_insert_sql = item_insert_sql % (', shipping_info_id', ', %s') if type == 'R' else item_insert_sql % ('', '')
        params = [distributor_shop_id, goods.id, num, order_id, goods.sales_price]
        if type == 'R':
            params.extend([shipping_id])

        self.db.execute(item_insert_sql, *params)

        self.render('mall/turn_to_pay.html', order_id=order_id, goods_id=goods.id)


class OrderPay(BaseHandler):
    """微商城订单支付"""
    @authenticated
    def post(self):
        goods_id = self.get_argument('goods_id').encode('utf-8')
        order_id = self.get_argument('order_id').encode('utf-8')
        order_items = self.db.get('select * from order_item where order_id = %s', order_id)

        if not order_items or str(order_items.goods_id) != goods_id:
            raise HTTPError(404)

        out_order_no = order_id
        req_id = datetime.now().strftime('%Y%m%d%H%M%S') + order_id
        current_user = self.current_user

        key = 'o:alipay:%s' % order_id
        token_info = self.redis.get(key)

        if not token_info:
            base_url = 'http://' + self.request.host
            call_back_url = base_url + self.reverse_url('order') + '?wx_id=' + current_user.wx_id
            merchant_url = base_url + self.reverse_url('mall.pay.fail') + '?wx_id=' + current_user.wx_id

            token_req_data = build_token_req_data(self.db, current_user.sp_id, goods_id, order_items.num, out_order_no,
                                                  call_back_url, merchant_url, current_user.wx_id)

            token = build_request('token', token_req_data, req_id)
        else:
            token_info = json.loads(token_info)
            if token_info['expire_at'] < datetime.now().strftime('%Y-%m-%d %H%M%S'):
                # 设置为已关闭状态
                self.db.execute('update orders set status = 8 where id = %s', order_id)
                self.render('mall/error.html', goods_id=goods_id, reason='交易已关闭')
                return
            token = {'result': True, 'token': token_info['token']}

        if token['result']:
            self.redis.setex(key, 10800, json_dumps({'token': token['token'],
                                                     'expire_at': datetime.now() + timedelta(hours=2)}))
            pay_req_data = build_pay_req_data(token['token'])
            self.redirect(build_request('pay', pay_req_data))
        else:
            self.write(token['detail'])


class Failed(BaseHandler):
    """微商城支付成功后转到"""
    @authenticated
    def get(self):
        self.render('mall/fail.html')
