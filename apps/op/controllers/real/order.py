# -*- coding: utf-8 -*-
import random
import string
import tornado.gen
import xlrd
import json
import logging
from .. import BaseHandler, require
from tornado.options import options
from autumn.utils import json_dumps, json_hook
from autumn.api.taobao import Taobao
import re
from autumn import const
from decimal import Decimal
import time
partern = re.compile("^([^x]*)x(\\d+)$")


class ImportPartnerOrder(BaseHandler):
    @require()
    def get(self):
        """ 导入渠道订单展示页面 """
        self.render('real/order.html', partner='TB', existed_orders=[], unbind_goods=[], success_orders=[], message='')

    @require('operator', 'service')
    @tornado.gen.coroutine
    def post(self):
        """ 导入渠道订单 """
        if not self.request.files:
            self.render('real/order.html', partner='TB', existed_orders=[], unbind_goods=[], success_orders=[],
                        message=u'请选择文件')

        #读取文件
        order_file = self.request.files['order_file'][0]
        book = xlrd.open_workbook(file_contents=order_file['body'])
        try:
            sheet = book.sheet_by_index(0)
        except:
            self.render('real/order.html', partner='TB', existed_orders=[], unbind_goods=[], success_orders=[],
                        message=u'文件格式错误，请检查')
            return

        partner = self.get_argument('partner').lower()
        #读取工作表的所有行数据内容
        rows = [sheet.row_values(i) for i in range(1, sheet.nrows)]
        #根据不同的渠道转换统一的数据格式
        converted_data = getattr(self, 'order_' + partner)(rows)

        #初始化各种变量
        existed_orders = []
        success_orders = set()
        unbind_goods = set()

        #处理渠道产生一百券对应的订单信息
        if partner == 'wb':
            process_wb_order(self, converted_data, existed_orders, unbind_goods, success_orders)
        else:
            #此处处理淘宝，京东，一号店的订单
            process_partner_order(self, partner, converted_data, False, existed_orders, unbind_goods, success_orders)

        self.render('real/order.html', partner=partner, existed_orders=existed_orders, unbind_goods=unbind_goods,
                    success_orders=success_orders, message='')

    def order_tb(self, rows):
        """ 转换淘宝的数据"""
        col_names = ('goods_no', 'distr_order_no', 'sales_price', 'buy_num', 'paid_at', 'options', 'remarks',
                     'express_info', 'receiver', 'phone', 'zip_code', 'address')
        return [dict([(col_names[i], row[i]) for i in range(len(col_names))]) for row in rows]

    def order_tm(self, rows):
        """ 转换天猫的数据"""
        return self.order_tb(rows)

    def order_jd(self, rows):
        """ 转换京东的数据"""
        col_names = ('distr_order_no', 'proj_name', 'proj_id', 'created_at', 'paid_at', 'buy_num', 'total_fee',
                     'refund_fee', 'receiver', 'address', 'phone', 'remarks', 'order_status', 'send_status',
                     'express_company', 'express_number')
        return [dict([(col_names[i], row[i]) for i in range(len(col_names))]) for row in rows]

    def order_yhd(self, rows):
        # 订单号	订单产品编号	外部ID	下单产品名	销售渠道	下单数量	商品单价	市场价	订单金额	下单时间	付款时间	发货时间	收货人姓名
        # 	收货人电话	收货人手机	留言	邮编	收货人地址	支付方式	发票	配送商	配送单号	状态	备注
        """ 转换一号店的数据"""
        col_names = ('distr_order_no', 'goods_no', 'outer_id', 'name', 'channel', 'buy_num', 'sales_price',
                     'market_price', 'total_fee', 'created_at', 'paid_at', 'used_at',
                     'receiver', 'tel', 'phone', 'remarks', 'zip_code', 'address', 'pay_way', 'invoice_title',
                     'express_info', 'express_no', 'status', 'remarks')
        return [dict([(col_names[i], row[i]) for i in range(len(col_names))]) for row in rows]

    def order_wb(self, rows):
        """ 转换WB的数据"""
        #对应58订单excel数据
        # ﻿订单编 数量 具体类型 快递费	总价	购买时间 	联系人 联系电话 省市区 详细地址	邮编	配送时间	备注	发货状态	快递公司	网址	快递单号
        col_names = ('distr_order_no', 'buy_num', 'goods_no', 'fee', 'sales_price', 'paid_at', 'receiver', 'phone',
                     'province', 'address', 'zip_code', 'express_info', 'remarks')
        return [dict([(col_names[i], row[i]) for i in range(len(col_names))]) for row in rows]


class TbAutoImportOrder(BaseHandler):
    @require('operator', 'service')
    @tornado.gen.coroutine
    def get(self):
        """ 淘宝自动导入订单处理"""
        app_info = json.loads(self.db.get('select taobao_api_info from distributor_shop where id=%s',
                                          options.shop_id_taobao).taobao_api_info, object_hook=json_hook)
        tm_app_info = json.loads(self.db.get('select taobao_api_info from distributor_shop where id=%s',
                                             options.shop_id_tmall).taobao_api_info, object_hook=json_hook)
        #初始化各种变量
        existed_orders = []
        unbind_goods = set()
        success_orders = set()
        #处理券生活8的订单
        yield get_taobao(self, app_info, existed_orders, unbind_goods, success_orders, 'tb')
        #处理天猫的订单
        yield get_taobao(self, tm_app_info, existed_orders, unbind_goods, success_orders, 'tm')
        self.render('real/order.html', existed_orders=existed_orders, unbind_goods=unbind_goods,
                    success_orders=success_orders, message='')


@tornado.gen.coroutine
def get_taobao(self, app_info, existed_orders, unbind_goods, success_orders, partner):
    page_index = 0
    taobao = Taobao('taobao.trades.sold.get')
    taobao.set_app_info(app_info.app_key, app_info.app_secret_key)
    taobao.set_session(app_info.session)
    while True:
        page_index += 1

        response = yield taobao(status='WAIT_SELLER_SEND_GOODS',
                                use_has_next='true',
                                page_size='100',
                                page_no=page_index,
                                fields='orders.outer_iid,tid,orders.payment,orders.num,pay_time,orders.price,'
                                       'shipping_type,orders.logistics_company,receiver_mobile,receiver_phone,'
                                       'receiver_name,receiver_state,receiver_city,receiver_district,'
                                       'receiver_address,receiver_zip,has_buyer_message')
        taobao.parse_response(response.body)
        if not taobao.is_ok():
            logging.error(taobao.error)
            break

        converted_data = []
        if 'trades' not in taobao.message.keys():
            logging.info(taobao.message)
        else:
            for trade in taobao.message.trades.values():
                for i in range(len(trade)):
                    buy_message = ""
                    #如果买家有留言，就去单独获取留言
                    if trade[i].has_buyer_message:
                        trade_get = Taobao('taobao.trade.get')
                        trade_get.set_app_info(app_info.app_key, app_info.app_secret_key)
                        trade_get.set_session(app_info.session)
                        trade_get_response = yield trade_get(tid=trade[i]['tid'],
                                                             fields='buyer_message')

                        trade_get.parse_response(trade_get_response.body)

                        #取得订单留言信息
                        buy_message = trade_get.message.trade.buyer_message

                    if not 'order' in trade[i].orders:
                        continue
                    for order_detail in trade[i].orders.order:
                        if trade[i].shipping_type == 'virtual':
                            logging.info('虚拟发货 跳过: ' + trade[i]['tid'])
                            continue
                        if not order_detail.outer_iid:
                            logging.info('该商品在淘宝上没有设置商品编码，请确认一下:' + trade[i].tid)
                            continue

                        mapping = {'goods_no': 'outer_iid', 'sales_price': 'price', 'buy_num': 'num'}
                        order_dict = {}
                        for key, value in mapping.iteritems():
                            order_dict[key] = order_detail[value]

                        order_dict['distr_order_no'] = trade[i].tid
                        order_dict['paid_at'] = trade[i].pay_time
                        order_dict['receiver'] = trade[i].receiver_name
                        order_dict['zip_code'] = trade[i].receiver_zip
                        order_dict['remarks'] = buy_message
                        order_dict['express_info'] = buy_message
                        if not trade[i].receiver_mobile:
                            order_dict['phone'] = trade[i].receiver_phone
                        else:
                            order_dict['phone'] = trade[i].receiver_mobile
                        order_dict['address'] = trade[i].receiver_state + trade[i].receiver_city + \
                                                trade[i].receiver_district + trade[i].receiver_address
                        converted_data.append(order_dict)
        #处理渠道产生一百券对应的订单信息
        process_partner_order(self, partner, converted_data, True, existed_orders, unbind_goods, success_orders)
        if taobao.message.has_next is False:
            break


def separate_wuba_order(order):
    import copy
    #取得58商品名称信息
    goods_no = order['goods_no']
    goods_no_lines = goods_no.split('\n')
    goods_len = len(goods_no_lines)
    new_order_list = []
    if goods_len > 1:
        #一个订单多个产品的场合 ﻿DQ冰淇淋缤纷卡 200元DQ缤纷卡x1
        for goods_no_line in goods_no_lines:
            if goods_no_line is '':
                continue
            matcher = re.match(partern, goods_no_line)
            if matcher:
                new_order = copy.deepcopy(order)
                new_order['goods_no'] = matcher.group(1)
                new_order['buy_num'] = matcher.group(2)
                new_order_list.append(new_order)
    else:
        new_order_list = [order]
    return new_order_list


def create_item(self, distr_shop_id, distr_id, goods_info, order_id, order_item_id, order_no, sales_id, commission):
    """ 生成实物订单item"""
    self.db.execute('insert into item (sales_price, discount, payment, purchase_price,face_value,'
                    'order_id,order_item_id, order_no,created_at,status,goods_name,'
                    'sp_id,goods_id,distr_shop_id,distr_id,sales_id,commission) '
                    'values (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s,%s,%s,%s,%s,%s,%s,%s)',
                    goods_info.sales_price, 0, goods_info.sales_price, goods_info.purchase_price,
                    goods_info.face_value, order_id, order_item_id, order_no, const.status.BUY,goods_info.short_name,
                    goods_info.supplier_id, goods_info.id, distr_shop_id, distr_id, sales_id, commission)


def process_wb_order(self, order_list, existed_orders, unbind_goods, success_orders):
    """处理58团的订单"""
    distributor_shop_id = options.shop_id_wuba
    for order in order_list:
        wb_order_no = order['distr_order_no']
        logging.info("Process OrderNO: %s", wb_order_no)

        #拆分58团购导入的实体券.
        separate_order_list = separate_wuba_order(order)
        if not separate_order_list:
            logging.info("excel数据格式有问题。外部订单: %s", wb_order_no)
            continue

        #判断是不是已经导入过的外部订单
        distributor_order = self.db.get('select * from distributor_order where distributor_shop_id=%s and '
                                        'order_no=%s', distributor_shop_id, wb_order_no)
        if distributor_order:
            existed_orders.append(wb_order_no.encode('utf-8'))
            continue
        else:
            #创建外部订单过程
            order_message = json_dumps(order)
            distributor_order_id = self.db.execute(
                'insert into distributor_order(order_no, message, distributor_shop_id, created_at) '
                'values (%s, %s, %s, NOW())', wb_order_no, order_message, options.shop_id_wuba)

        #开始创建一百券订单
        #订单总额
        order_amount = order['sales_price']
        # 生成订单
        while True:
            order_no = '%s%s' % (
                random.choice('123456789'), ''.join([random.choice(string.digits) for i in range(7)]))
            # 没有重复，停止
            if not self.db.get('select id from orders where order_no=%s', order_no):
                break
        order_id = self.db.execute(
            'insert into orders(distributor_shop_id, order_no, distributor_order_id,'
            'total_fee, payment,mobile, paid_at, status, created_at) values(%s, %s, %s, %s, %s, %s, %s, 1, NOW())',
            distributor_shop_id, order_no, distributor_order_id, order_amount, order_amount,
            order['phone'], order['paid_at'])

        #更新外部订单中的一百券订单Id
        self.db.execute('update distributor_order set order_id =%s where id =%s',
                        order_id, distributor_order_id)

        #创建实物订单物流信息
        order_shipping_info_id = self.db.execute(
            'insert into order_shipping_info(address, created_at, express_info, paid_at, '
            'receiver, phone, remarks, zip_code, distr_order_no) '
            'values(%s, NOW(), %s, %s, %s, %s, %s, %s, %s)',
            order['address'], order['express_info'], order['paid_at'], order['receiver'],
            order['phone'], order['remarks'], order['zip_code'], order['distr_order_no'])

        amount = 0
        for wuba_order in separate_order_list:

            # 找到关联的商品
            goods_info = self.db.get('select g.* from goods g, goods_distributor_shop gds '
                                     'where g.id = gds.goods_id and distributor_shop_id=%s and '
                                     'distributor_goods_id=%s',
                                     distributor_shop_id, wuba_order['goods_no'])
            if not goods_info:
                unbind_goods.add(wuba_order['goods_no'])
                logging.info("58未映射商品NO:%s", wuba_order['goods_no'].encode('utf-8'))
                #删除未映射已产生的订单关联信息
                self.db.execute('delete from order_shipping_info where id = %s', order_shipping_info_id)
                self.db.execute('delete from orders where id = %s', order_id)
                self.db.execute('delete from distributor_order where id = %s', distributor_order_id)
                continue

            # 生成 订单项
            count = wuba_order['buy_num']
            order_item_id = self.db.execute(
                'insert into order_item(distributor_shop_id, goods_id, num, order_id, sales_price, '
                'shipping_info_id, distributor_goods_no) values (%s, %s, %s, %s, %s,%s,%s)',
                distributor_shop_id, goods_info.id, count, order_id,
                goods_info.sales_price, order_shipping_info_id, wuba_order['goods_no'])

            # 查找销售人员，商户的账户
            supplier = self.db.get('select s.* from supplier s where s.id=%s', goods_info.supplier_id)

            # 放入消息表，以便通知商户发货
            url = '/shipping/show'
            self.db.execute('insert into notification(content, created_at, type, url, uid, user_type,title) '
                            'values(%s, NOW(), 1, %s, %s, 0,%s)', '有物品%s需要发货' % goods_info.short_name, url,
                            goods_info.supplier_id, u'发货通知')

            #取得商品佣金比例
            goods_commission = self.db.get('select ratio from goods_distributor_commission '
                                           'where goods_id=%s and distr_shop_id=%s', goods_info.id, distributor_shop_id)
            commission = goods_commission.ratio * goods_info.sales_price * Decimal('0.01') if goods_commission else 0

            #生成item
            for i in range(int(count)):
                create_item(self, distributor_shop_id, options.distributor_id_wuba, goods_info, order_id, order_item_id,
                            order_no, supplier.sales_id, commission)

                #根据一百券商品计算订单总金额
                amount += goods_info.sales_price * int(count)
                #成功的订单
                success_orders.add(str(wb_order_no))

        if amount > 0 and amount != order_amount:
            logging.info('58订单总金额和一百券不一致，外部订单号：%s', wb_order_no)

        # 记录订单日志
        self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                        'values (NOW(), 1, %s, %s, %s)',
                        "%s" % self.current_user.name, "生成新订单", order_id)


def process_partner_order(self, partner, order_list, tb_auto_import, existed_orders, unbind_goods, success_orders):
    """ 处理渠道的订单数据信息"""
    ###################处理京东，一号店，淘宝 渠道订单###################
    order_bool = 0
    order_id = 0
    shipping_id = 0
    # 分销店铺
    distributor = {
        'tb': options.shop_id_taobao,
        'tm': options.shop_id_tmall,
        'jd': options.shop_id_jingdong,
        'yhd': options.shop_id_yihaodian
    }
    # 分销商
    distr_id = {
        'tb': options.distributor_id_taobao,
        'tm': options.distributor_id_taobao,
        'jd': options.distributor_id_jingdong,
        'yhd': options.distributor_id_yihaodian,
    }
    distributor_shop = distributor[partner]
    distributor_id = distr_id[partner]
    logging.info('processing %s order start...', partner)
    for order in order_list:
        amount = 0
        if not tb_auto_import:
            if partner == 'jd':
                filename = self.request.files['order_file'][0]['filename']
                order['goods_no'] = filename.split('.')[0]
                order['sales_price'] = str(Decimal(order['total_fee']) / Decimal(order['buy_num']))
                order['zip_code'] = '000000'
                order['express_info'] = ''
            goods = self.db.get('select goods_id from goods_distributor_shop where '
                                'distributor_goods_id = %s and distributor_shop_id = %s limit 1',
                                order['goods_no'], distributor_shop)
        else:
            goods = self.db.get('select goods_id from goods_distributor_shop where '
                                'goods_link_id = %s and distributor_shop_id = %s limit 1',
                                order['goods_no'], distributor_shop)
        if not goods:
            unbind_goods.add(str(order['goods_no']))
            continue
        goods_id = goods.goods_id
        goods_info = self.db.get('select * from goods where id = %s ', goods_id)
        #如果是float，转为如2013-08-22 17：23：00格式
        if isinstance(order['paid_at'], float):
            order['paid_at'] = excel_time_translation(order['paid_at'])

        distr_order_no = order['distr_order_no']
        if isinstance(distr_order_no, float):
            distr_order_no = str(int(distr_order_no))

        #第一次循环，判断distributor_order是否已存在
        distributor_order = self.db.get('select * from distributor_order where order_no = %s limit 1',
                                        distr_order_no)
        if distributor_order:
            #如果第一次插入时发现是淘宝自动导入且存在外部订单号。默认为已导入，返回
            if tb_auto_import and not order_bool:
                logging.info('distributor order %s has exist', distr_order_no)
                existed_orders.append(str(distr_order_no))
                #如果已经存在了，则不再导入
                return
            else:
                distributor_order_id = distributor_order.id
                order_existed = self.db.get('select id from orders where distributor_order_id = %s',
                                       distributor_order_id)

                order_id = order_existed.id if order_existed else 0
                if not order_id:
                    #删除没创建订单成功的外部订单
                    self.db.execute('delete from distributor_order where id = %s', distributor_order_id)
                    continue

                if not order_bool:
                    existed_orders.append(str(distr_order_no))
                    continue
                shipping_id = self.db.get('select id from order_shipping_info where distr_order_no = %s '
                                          'limit 1', distr_order_no)['id']
        else:
            # 生成一百券订单
            while True:
                order_no = '%s%s' % (
                    random.choice('123456789'), ''.join([random.choice(string.digits) for i in range(7)]))
                # 没有重复，停止
                if not self.db.get('select id from orders where order_no=%s', order_no):
                    break
            order_id = self.db.execute(
                'insert into orders(distributor_shop_id, created_at, order_no, mobile, status, paid_at) '
                'values(%s, NOW(), %s, %s, 1, NOW())', distributor_shop, order_no, order['phone'])

            distributor_order_id = self.db.execute('insert into distributor_order(order_no, created_at, message, '
                                                   'distributor_shop_id, order_id) values(%s, NOW(), %s, %s, %s)',
                                                   order['distr_order_no'], json_dumps(order), distributor_shop,
                                                   order_id)
            self.db.execute('update orders set distributor_order_id = %s where id = %s',
                            distributor_order_id, order_id)

            shipping_id = self.db.execute(
                'insert into order_shipping_info(address, created_at, express_info, '
                'paid_at, receiver, phone, remarks, zip_code, distr_order_no) '
                'values(%s, NOW(), %s, %s, %s, %s, %s, %s, %s)',
                order['address'], order['express_info'], order['paid_at'], order['receiver'],
                order['phone'], order['remarks'], order['zip_code'], order['distr_order_no'])
        order_bool = 1

        order_item = self.db.get('select * from order_item where distributor_shop_id = %s and goods_id = %s and '
                                 'shipping_info_id = %s and distributor_goods_no = %s limit 1',
                                 distributor[partner], goods_id, shipping_id, order['goods_no'])
        if order_item:
            continue
        order_item_id = self.db.execute(
            'insert into order_item(distributor_shop_id, goods_id, num, order_id,sales_price,'
            'shipping_info_id, distributor_goods_no) values(%s, %s,%s, %s,%s, %s, %s)',
            distributor_shop, goods_id, order['buy_num'], order_id, order['sales_price'],
            shipping_id, order['goods_no'])
        sales_price = float(order['sales_price']) * float(order['buy_num'])
        amount += sales_price
        self.db.execute('update orders set payment = %s, total_fee = %s where id = %s',
                        amount, amount, order_id)

        supplier = self.db.get('select s.* from supplier s where s.id=%s', goods_info.supplier_id)

        # 放入消息表，以便通知商户发货
        url = '/shipping/show'
        self.db.execute('insert into notification(content, created_at, type, url, uid, user_type,title) '
                        'values(%s, NOW(), 1, %s, %s, 0,%s)', '有物品%s需要发货' % goods_info.short_name,
                        url, goods_info.supplier_id, u'发货通知')
        #取得商品佣金比例
        goods_commission = self.db.get('select ratio from goods_distributor_commission '
                                       'where goods_id=%s and distr_shop_id=%s', goods_info.id, distributor_shop)
        commission = goods_commission.ratio * goods_info.sales_price * Decimal('0.01') if goods_commission else 0

        #生成real_item
        for i in range(int(order['buy_num'])):
            create_item(self, distributor_shop, distributor_id, goods_info, order_id,
                        order_item_id, order_no, supplier.sales_id, commission)

        success_orders.add(str(distr_order_no))
        # 记录订单日志
        self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
                        'values (NOW(), 1, %s, %s, %s)',
                        "分销商id:%s" % distributor_shop, "生成新订单", order_id)


def excel_time_translation(excel_time):
    temp_time = (float(excel_time) - 19 - 70 * 365) * 86400 - 8 * 3600
    time_string = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(temp_time))
    return time_string
