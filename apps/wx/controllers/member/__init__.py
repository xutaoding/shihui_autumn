# -*- coding: utf-8 -*-
from tornado.options import options
import tornado.web
import json
from .. import BaseHandler
from tornado.httputil import url_concat
import random
from autumn.utils import json_dumps


class UserInfo(BaseHandler):
    """微信会员首页"""
    @tornado.web.authenticated
    def get(self):
        user = self.current_user
        if user.level == 0:
            # 还没注册
            self.redirect(url_concat(self.reverse_url('member_join'), {'wx_id': user.wx_id}))
        else:
            # 获取模块
            blocks = self.db.query('select * from wx_mem_block where sp_id=%s and deleted=0 order by display_order asc',
                                   user.sp_id)
            first = []
            second = []
            for b in blocks:
                if b.group == 1:
                    first.append(b)
                else:
                    second.append(b)
            # 会员等级
            try:
                raw_level = self.db.get('select value from supplier_property where sp_id=%s and name="wx_level"', user.sp_id).value
                level = json.loads(raw_level).get(str(user.level))
            except:
                level = ""

            # 获取未读消息, 商户群发的，和发送到指定用户的都是
            msg = self.db.get('select count(mm.id) as num from wx_member_msg mm, member m where mm.id > m.max_msg_id '
                              'and ((mm.iid=m.sp_id and mm.type=0) or (mm.iid=m.id and mm.type=1)) and  wx_id=%s',
                              user.wx_id)
            # 获取券和奖品信息
            coupon_num = self.db.get('select count(1) as num from orders o join item i '
                                     'on o.id = i.order_id join item_coupon ic on i.id = ic.item_id join goods g '
                                     'on i.goods_id = g.id where o.distributor_user_id = %s ', user.wx_id)
            sn_num = self.db.get('select count(1) as num from wx_activity_rewards r, wx_activity_sn s '
                                 'where r.id=s.rewards_id and s.mem_id=%s', user.id)
            self.render('member/index.html', first=first, second=second, msg_num=msg.num, level=level,
                        coupon_num=coupon_num, sn_num=sn_num)


class Join(BaseHandler):
    """跳转到加入会员"""
    @tornado.web.authenticated
    def get(self):
        self.render('member/join.html', error=None)

    @tornado.web.authenticated
    def post(self):
        user = self.current_user
        name = self.get_argument('name', '')
        mobile = self.get_argument('mobile', '')
        gender = self.get_argument('gender', '')
        vcode = self.get_argument('vcode', '')

        ex_vcode = self.redis.get("%s:%s" % (options.queue_vcode, user.wx_id))
        if vcode == ex_vcode:
            self.db.execute('update member set name=%s, mobile=%s, gender=%s, level=1, last_active=NOW(),source="微信" '
                            'where id=%s',
                            name, mobile, gender, user.id)
            self.redirect(url_concat(self.reverse_url('member_index'), {'wx_id': user.wx_id}))
        else:
            self.render('member/join.html', error='验证码错误')


class ChangeInfo(BaseHandler):
    """修改会员资料"""
    @tornado.web.authenticated
    def get(self):
        self.render('member/info.html')

    @tornado.web.authenticated
    def post(self):
        user = self.current_user
        gender = self.get_argument('gender', '')
        age = self.get_argument('age', 0)
        birth_date = self.get_argument('birth_date', '1980-01-01')
        address = self.get_arguments('address', '')

        self.db.execute('update member set gender=%s, age=%s, birth_date=%s, address=%s, last_active=NOW() '
                        'where id=%s ',
                        gender, age, birth_date, address, user.id)
        self.redirect(url_concat(self.reverse_url('member_index'), {'wx_id': user.wx_id}))


class ReadMeg(BaseHandler):
    """用户消息"""
    @tornado.web.authenticated
    def get(self):
        msgs = self.db.query('select * from wx_member_msg where type=0 and iid=%s order by created_at desc limit 10',
                             self.current_user.sp_id)
        ids = [int(msg.id) for msg in msgs]
        if not ids:
            ids = [0]
        max_id = max(ids)
        self.render('member/msg.html', msgs=msgs, max_id=max_id)

    @tornado.web.authenticated
    def post(self):
        """更新最大消息id"""
        max_msg_id = self.get_argument('max_msg_id', 0)
        user = self.current_user
        self.db.execute('update member set max_msg_id=%s where id=%s', max_msg_id, user.id)


class SendVCode(BaseHandler):
    """发送短信验证码"""
    @tornado.web.authenticated
    def post(self):
        user = self.current_user
        mobile = self.get_argument('mobile', '').encode('utf-8')
        if not mobile:
            self.redirect(url_concat(self.reverse_url('member_join'), {'wx_id': user.wx_id}))

        # 先去查查之前有没有产生验证码
        ex_vcode = self.redis.get("%s:%s" % (options.queue_vcode, user.wx_id))
        if ex_vcode:
            vcode = ex_vcode
        else:
            vcode = str(random.randint(100000, 999999))
            # 放入REDIS 记录验证码
            self.redis.setex("%s:%s" % (options.queue_vcode, user.wx_id), 600, vcode)
        sms_content = {
            'mobile': mobile,
            'sms': '验证码：%s（10分钟内有效），%s会员注册【一百券】' % (vcode, user.sp_name),
            'retry': 0,
        }
        # 放入亿美短信队列
        self.redis.lpush(options.queue_coupon_send_emay, json_dumps(sms_content))


class Shops(BaseHandler):
    """使用门店信息"""
    @tornado.web.authenticated
    def get(self):
        # 获取门店
        shops = self.db.query('select * from supplier_shop where supplier_id=%s and deleted=0', self.current_user.sp_id)
        self.render('member/shops.html', shops=shops)
