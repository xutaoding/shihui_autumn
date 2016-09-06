# -*- coding: utf-8 -*-
from . import BaseHandler
import time
import logging
from tornado.options import options
import tornado.gen
from autumn.order import new_distributor_order, new_distributor_item
from autumn.sms import CouponConsumedMessage
from autumn.coupon import local_check, local_verify, partner_api_verify, partner_browser_verify
from datetime import datetime
import rmb
from autumn.utils import json_dumps

upper = rmb.wrapper(digits=u'零一二三四五六七八九', words=u'亿万千百十元角分整')


class Verify(BaseHandler):
    @tornado.gen.coroutine
    def get(self):
        caller = self.get_argument('caller').encode('utf-8')
        coupon_sn = self.get_argument('coupon').encode('utf-8')
        sign = self.get_argument('sign').encode('utf-8')
        timestamp = self.get_argument('timestamp').encode('utf-8')
        logging.info('telephone verify. caller: %s, coupon_sn: %s, sign: %s, timestamp: %s',
                     caller, coupon_sn, sign, timestamp)

        if not caller:
            logging.error('telephone verify failed: empty caller.')
            self.write('1|主叫号码无效')
            return
        if not coupon_sn:
            logging.error('telephone verify failed: empty coupon.')
            self.write('2|券号为空')
            return
        if not sign:
            logging.error('telephone verify failed: empty sign.')
            self.write('3|签名无效')
            return
        if not timestamp:
            logging.error('telephone verify failed: empty timestamp.')
            self.write('3|时间戳无效')
            return

        if abs(int(time.time()) - int(timestamp)) > 300:
            logging.error('telephone verify failed: request timeout.')
            self.write('3|请求超时')
            return
        # 暂不检查签名
        # todo

        # 查找电话
        supplier_shop = self.db.get('select * from supplier_shop where deleted=0 and verify_phones like %s', '%'+caller+'%')
        #if not supplier_shop:
        #    #部分商家使用分机，出口线很多，不能一一录入，这里可以使用电话号码的前面一部分进行识别。
        #    #尝试模糊查找验证电话机
        #    supplier_user_list = self.db.query('select * from supplier_user where type="ANDROID"')
        #    for su in supplier_user_list:
        #        if caller.startswith(su.loginname):
        #            supplier_shop = su
        #            break
        if not supplier_shop:
            logging.error('telehphone verify failed. can not found valid supplier_user %s.', caller)
            self.write('1|您的电话还未绑定')
            return

        coupon = self.db.get('select id, sn, mobile from item_coupon where sn=%s', coupon_sn)
        if not coupon:
            if len(coupon_sn) == 9:
                for i in range(10):
                    coupon = self.db.get('select id, sn, mobile from item_coupon where sn=%s', '%s%s' % (i, coupon_sn))

        if coupon:
            #我们自己的券
            check_result = local_check(self.db, coupon.sn, supplier_shop.id)
            if not check_result.ok:
                ok, msg = (False, check_result.msg)
            else:
                #  合作伙伴API验证
                api_result = yield partner_api_verify(self.db, coupon.sn)
                if not api_result.ok:
                    ok, msg = (False, api_result.msg)
                else:
                    #  本地验证
                    verify_result = local_verify(self.db, coupon.sn, supplier_shop.id, '电话验证')
                    if verify_result.ok:
                        ok, msg = (True, verify_result.msg)
                    else:
                        ok, msg = (False, verify_result.msg)
        else:
            results = yield partner_browser_verify(self.db, [coupon_sn], supplier_shop.id)
            # 记录外部订单
            for result in results:
                if result.ok:
                    goods_info = self.db.get('select g.* from goods g where id=%s', result.goods_id)
                    verify_infos = {'goods_id': result.goods_id, 'shop_id': supplier_shop.id}
                    #创建分销订单
                    distributor_order_id = self.db.execute(
                        'insert into distributor_order(order_no, message, distributor_shop_id, created_at) '
                        'values (%s, %s, %s, NOW())', result.coupon_sn, json_dumps(verify_infos),
                        result.distributor_shop_id)
                    order_id, order_no = new_distributor_order(self.db, result.distributor_shop_id,
                                                               goods_info.sales_price, goods_info.sales_price, '')
                    #记录订单信息
                    new_order = new_distributor_item(
                        db=self.db,
                        order_id=order_id,
                        order_no=order_no,
                        sales_price=None,
                        count=1,
                        goods_info=goods_info,
                        mobile='',
                        distributor_shop_id=result.distributor_shop_id,
                        distributor_goods_id='',
                        distributor_coupons=[{'coupon_sn': result.coupon_sn, 'coupon_pwd': result.coupon_pwd or ''}],
                        use_distributor_coupon=True
                    )
                    if new_order.ok:
                        #更新分销订单id
                        self.db.execute('update orders set distributor_order_id=%s where id = %s',
                                        distributor_order_id, order_id)
                        #更新订单id
                        self.db.execute('update distributor_order set order_id=%s where id=%s',
                                        order_id, distributor_order_id)
                        #更新该券验证的门店
                        self.db.execute('update item set sp_shop_id = %s where order_id=%s', supplier_shop.id, order_id)
                        self.redis.lpush(options.queue_coupon_local_verify, json_dumps({'coupon': result.coupon_sn,
                                                                                        'shop_id': supplier_shop.id,
                                                                                        'retry': 0,
                                                                                        'used_at': datetime.now()}))
            ok, msg = (results[0].ok, results[0].msg)

        if not ok:
            logging.error('telephone verify failed. %s', msg)
            self.write('2|验证失败')
        else:
            logging.info('telephone verify ok. caller: %s, coupon_sn: %s, sign: %s, timestamp: %s',
                         caller, coupon_sn, sign, timestamp)

            # 发送验证确认短信
            CouponConsumedMessage(self.redis, [coupon.sn], supplier_shop.name, coupon.mobile).send()

            if coupon:
                face_value = self.db.get('select face_value from item i, item_coupon c where i.id=c.item_id '
                                         'and c.id=%s', coupon.id).face_value
                self.write('0|券尾号%s验证成功，面值%s' % (coupon_sn[-4:], upper(face_value).encode('utf-8')))
            else:
                self.write('0|券尾号%s验证成功' % coupon_sn[-4:])
