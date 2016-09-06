# -*- coding: utf-8 -*-
import json
from datetime import datetime
import time
from autumn import const
from autumn.api.lashou import LashouBrowser
from autumn.utils import PropDict, json_hook
from autumn.api import Taobao, Jingdong, Wuba, NuomiBrowser, MeituanBrowser, DianpingBrowser
from tornado.options import options
from tornado import gen
import logging
import httplib
import urllib


def local_check(db, coupon_sn, shop_id):
    """
    :type db torndb.Connection
    """
    coupon = db.get('select i.sp_id, i.status, c.expire_at, c.mobile, g.all_shop, i.goods_id from item i, '
                    'item_coupon c,goods g where c.sn=%s and i.id=c.item_id and g.id=i.goods_id ',
                    coupon_sn)
    if not coupon:
        return PropDict(ok=False, coupon_sn=coupon_sn, msg='券号不存在')

    shop = db.get('select s.* from supplier_shop s where id=%s', shop_id)

    if coupon.sp_id != shop.supplier_id:
        return PropDict(ok=False, coupon_sn=coupon_sn, msg='券号不存在')
    if coupon.status != const.status.BUY:
        return PropDict(ok=False, coupon_sn=coupon_sn, msg='该券已使用或已退款')
    if coupon.expire_at < datetime.now():
        return PropDict(ok=False, coupon_sn=coupon_sn, msg='该券已过期')
    #检查是不是属于该店的券
    #全部店铺直接验证，指定门店则判断是否和选择的门店是否一致
    if coupon.all_shop == '0':
        shops = db.query('select gss.supplier_shop_id id from goods_supplier_shop gss,goods g '
                         'where g.id=gss.goods_id and g.id=%s', coupon.goods_id)
        if int(shop_id) not in [i.id for i in shops]:
            return PropDict(ok=False, coupon_sn=coupon_sn, msg='该券不能在此门店使用!')

    return PropDict(ok=True, coupon_sn=coupon_sn, coupon=coupon)


@gen.coroutine
def partner_api_verify(db, coupon_sn):
    # 查找券信息
    coupon = db.get('select i.*, c.*, c.id cid from item i, item_coupon c where c.sn=%s and i.id=c.item_id', coupon_sn)
    coupon_sn = coupon_sn.encode('utf-8')
    logging.info('被验证券sn：%s', coupon.sn)
    if not coupon:
        raise gen.Return(PropDict(ok=False, coupon_sn=coupon_sn, msg='券号不存在'))

    distributor_order = db.get('select do.* from distributor_order do, orders o where do.id=o.distributor_order_id '
                               'and o.id=%s', coupon.order_id)
    if coupon.distr_id == options.distributor_id_taobao:
        # 淘宝验证
        distributor_shop = db.get('select * from distributor_shop where id=%s', distributor_order.distributor_shop_id)

        order_message = json.loads(distributor_order.message, object_hook=json_hook)
        app_info = json.loads(distributor_shop.taobao_api_info, object_hook=json_hook)

        taobao = Taobao('taobao.vmarket.eticket.consume')
        taobao.set_app_info(app_info.app_key, app_info.app_secret_key)
        if app_info.app_key == options.taobao_kunran_app_key:
            taobao.add_fields(codemerchant_id=options.taobao_kunran_id, posid=options.taobao_coupon_posid)
            taobao.set_session(app_info.merchant_session)
        else:
            taobao.set_session(app_info.session)

        response = yield taobao(order_id=distributor_order.order_no, verify_code=coupon_sn, token=order_message.token,
                                consume_num=1)
        logging.info('taobao coupon verify. coupon_sn:%s, result:%s', coupon_sn, response.body)

        taobao.parse_response(response.body)
        if taobao.is_ok():
            raise gen.Return(PropDict(ok=True, coupon_sn=coupon_sn, msg='验证成功'))
        else:
            raise gen.Return(PropDict(ok=False, coupon_sn=coupon_sn, msg=taobao.error.msg.encode('utf-8')))

    elif coupon.distr_id == options.distributor_id_jingdong:
        # 京东验证
        shop = db.get('select taobao_seller_id, taobao_api_info from distributor_shop where id=%s',
                      coupon.distr_shop_id)
        api_info = json.loads(shop.taobao_api_info, object_hook=json_hook)

        jingdong = Jingdong('verifyCode', str(shop.taobao_seller_id), api_info.vender_key, api_info.secret_key)
        response = yield jingdong(jd_order_id=distributor_order.order_no, coupon_id=coupon.distr_sn,
                                  coupon_pwd=coupon.distr_pwd)
        logging.info('jingdong coupon verify. coupon_sn:%s, result:%s', coupon_sn, response.body)

        jingdong.parse_response(response.body)
        if jingdong.is_ok():
            raise gen.Return(PropDict(ok=True, coupon_sn=coupon_sn, msg='验证成功'))
        else:
            raise gen.Return(PropDict(ok=False, coupon_sn=coupon_sn, msg='验证失败'))

    elif coupon.distr_shop_id == options.shop_id_wuba:
        # 58验证
        wuba = Wuba('order.ticketcheck')
        # todo 弥补之前的错误
        if 211796 < coupon.cid < 219863:
            oid = coupon.order_id
        else:
            oid = coupon.order_no
        response = yield wuba(ticketId=coupon.cid, orderId=oid, ticketIdIndex=0)
        logging.info('wuba coupon verify. coupon_sn:%s, result:%s', coupon_sn, response.body)

        wuba.parse_response(response.body)
        if wuba.is_ok() and wuba.message.data.result == 1:
            raise gen.Return(PropDict(ok=True, coupon_sn=coupon_sn, msg='验证成功'))
        else:
            raise gen.Return(PropDict(ok=False, coupon_sn=coupon_sn, msg='验证失败'))
    else:
        logging.info('partner api verify skip. coupon_sn:%s', coupon_sn)
        raise gen.Return(PropDict(ok=True, coupon_sn=coupon_sn, msg='无需第三方验证'))


@gen.coroutine
def partner_browser_verify(db, coupon_list, shop_id):
    shop = db.get('select * from supplier_shop where id=%s', shop_id)
    coupon_len = len(coupon_list[0])
    results = []
    requests = []
    clients = []
    if coupon_len == 12 and shop.nuomi_params:
        logging.info('nuomi params:%s', shop.nuomi_params)
        # 同时发起多个糯米单券验证请求
        nuomi_params = json.loads(shop.nuomi_params, object_hook=json_hook)
        for coupon_sn in coupon_list:
            client = NuomiBrowser('verify', nuomi_params)
            clients.append(client)
            requests.append(client.fetch(code=coupon_sn))
    if coupon_len == 12 and shop.meituan_params:
        logging.info('meituan params:%s', shop.meituan_params)
        # 同时发起多个美团单券验证请求
        meituan_params = json.loads(shop.meituan_params, object_hook=json_hook)
        for coupon_sn in coupon_list:
            client = MeituanBrowser('verify', meituan_params)
            clients.append(client)
            requests.append(client.fetch(code='%s' % coupon_sn,
                                         poiid=meituan_params.poiid))
    if coupon_len == 10 and shop.dianping_params:
        # 发起单个点评的批量验证请求
        dianping_params = json.loads(shop.dianping_params, object_hook=json_hook)
        client = DianpingBrowser('verify', dianping_params)
        clients.append(client)
        requests.append(client.fetch(serialNums=','.join(coupon_list)))

    if coupon_len == 8 and shop.lashou_params:
        # 同时发起多个拉手单券验证
        lashou_params = json.loads(shop.lashou_params, object_hook=json_hook)
        for coupon_sn in coupon_list:
            client = LashouBrowser('verify', lashou_params)
            clients.append(client)
            client.add_field('class', 'Check')
            requests.append(client.fetch(password=coupon_sn, act='submit_one',
                                         three_status=0, random=int(time.time()*1000)))

    if not requests:
        # 没有找到合适的合作伙伴
        logging.info('browser verify failed: no suitable partner. %s', ','.join(coupon_list))
        for coupon_sn in coupon_list:
            results.append(PropDict(ok=False, coupon_sn=coupon_sn, msg='验证失败'))
        raise gen.Return(results)
    responses = yield requests
    for i in range(len(requests)):
        logging.info('request:%s response:%s', clients[i], responses[i].body)
        clients[i].parse_response(responses[i].body)
        if clients[i].is_ok():
            # 查找券与商品ID的对应关系
            order_info = clients[i].find_order_info()
            logging.info(order_info)
            if isinstance(order_info, list):
                for gi in order_info:
                    results.append(PropDict(ok=True, coupon_sn=gi.coupon_sn, goods_id=gi.goods_id,
                                            coupon_pwd=gi.coupon_pwd,
                                            distributor_shop_id=gi.distributor_shop_id, msg='验证成功'))
                # 多券验证，有一个OK就OK，所以要把错误结果在这里加上
                for e in clients[i].error:
                    results.append(PropDict(ok=False, coupon_sn=e.coupon_sn, msg=e.msg))
            else:
                results.append(PropDict(ok=True, coupon_sn=order_info.coupon_sn, coupon_pwd=order_info.coupon_pwd,
                                        distributor_shop_id=order_info.distributor_shop_id,
                                        goods_id=order_info.goods_id, msg='验证成功'))
        else:
            if isinstance(clients[i].error, list):
                # 多券验证，要把错误的结果也加上
                for e in clients[i].error:
                    results.append(PropDict(ok=False, coupon_sn=e.coupon_sn, msg=e.msg))
            else:
                # 添加单券验证失败的错误信息
                results.append(PropDict(ok=False, coupon_sn=clients[i].error.coupon_sn, msg=clients[i].error.msg))

    #  把未验证成功的也补全到结果中
    for coupon_sn in coupon_list:
        found = False
        for result in results:
            if result.coupon_sn == coupon_sn or result.coupon_pwd == coupon_sn:
                found = True
                break
        if not found:
            results.append(PropDict(ok=False, coupon_sn=coupon_sn, msg='验证失败'))
    results_filtered = filter_result(results)
    logging.info("partner_browser_verify results:%s", results_filtered)
    raise gen.Return(results_filtered)


def filter_result(results):
    """过滤外部验证的返回信息，避免因为2个渠道券号长度相同返回一个对一个错而在页面上显示错误的验证结果"""
    results_filtered = []
    coupon_sn_filtered = []
    for result in results:
        coupon_sn = result.coupon_sn
        if coupon_sn not in coupon_sn_filtered:
            coupon_sn_filtered.append(coupon_sn)
            same_coupons = [i for i in results if i.coupon_sn == coupon_sn]
            pass_coupon = [p for p in same_coupons if p.ok]
            if pass_coupon:
                results_filtered.append(pass_coupon[0])
            else:
                results_filtered.append(same_coupons[0])
    return results_filtered


def local_verify(db, coupon_sn, shop_id, operator, verified_at=None):
    if not verified_at:
        verified_at = datetime.now()

    coupon = db.get('select i.*, c.*, i.id as iid, c.id as cid '
                    'from item i, item_coupon c where c.sn=%s and i.id=c.item_id', coupon_sn)
    if not coupon:
        return PropDict(ok=False, coupon_sn=coupon_sn, msg='券号不存在')

    shop = db.get('select * from supplier_shop where id=%s', shop_id)

    db.execute('update item set status=2, used_at=%s, sp_shop_id=%s '
               'where id=%s', verified_at, shop_id, coupon.iid)

    # 查找商户及门店的账户
    supplier_shop_account_id = db.get('select account_id from supplier_shop where id=%s', shop_id).account_id

    # 记录商户门店账务明细
    remark = '券消费:%s, 验证门店:%s, 商品:%s, 售价:%s, 付款:%s' \
             % (coupon_sn.encode('utf-8'), shop.name, coupon.goods_name, coupon.sales_price, coupon.payment)
    db.execute(
        'insert into account_sequence(type, account_id, item_id, amount, remark, created_at, status, '
        'trade_type, trade_id) values (%s, %s, %s, %s, %s, %s, 1, 1, %s)',
        const.seq.USED, supplier_shop_account_id, coupon.iid, coupon.purchase_price, remark,
        verified_at, coupon.order_id)

    # 记录日志
    db.execute(
        'insert into journal (created_at, type, created_by, message, iid) values (%s, 2, %s, %s, %s)',
        verified_at, operator, remark, coupon.cid
    )
    return PropDict(ok=True, coupon_sn=coupon_sn, shop_name=shop.name, msg='验证成功')


def refund_coupon(db, coupon_sn, operator, remark):
    """
    退款操作
    无论成功与否，都返回Dict: 如{"ok":False, "coupon_sn": 12341234, "msg":"券号不存在" }
    :param db:torndb.Connection
    :param coupon_sn:str
    :param operator:str
    :param remark:str
    :return: Dict
    """

    coupon = db.get('select *, c.id as cid from item i, item_coupon c where c.sn=%s and i.id=c.item_id', coupon_sn)
    # 检查券号是否存在
    if not coupon:
        return PropDict({'ok': False, 'coupon_sn': coupon_sn, 'msg': '券号不存在'})
    # 不是未消费不能退款
    if not const.status.BUY == coupon.status:
        return PropDict({'ok': False, 'coupon_sn': coupon_sn, 'msg': '券已消费或已退款'})
    goods = db.get('select * from goods where id=%s', coupon.goods_id)
    # 导入券不能退款
    if 'IMPORT' == goods.generate_type:
        return PropDict({'ok': False, 'coupon_sn': coupon_sn, 'msg': '导入券不能退款'})

    # 更新券状态
    db.execute('update item i join item_coupon c set i.refund_value=%s, i.refund_at=NOW(), '
               'status=3 where i.id=c.item_id and c.sn=%s',
               coupon.payment, coupon_sn.encode('utf-8'))
    # 更新库存
    db.execute('update goods set sales_count=sales_count-1, stock=stock+1 where id=%s', goods.id)
    # 记录日志
    db.execute('insert into journal (created_at, type, created_by, message, iid)'
               'values (NOW(), 2, %s, %s, %s)',
               operator,
               '券 %s 未消费退款，理由：%s' % (coupon_sn, remark),
               coupon.cid)

    logging.info('券 %s 未消费退款成功，理由:%s, 对应商品:%s' % (coupon_sn, remark, goods.short_name))
    return PropDict({'ok': True, 'coupon_sn': coupon_sn, 'msg': '退款成功'})
