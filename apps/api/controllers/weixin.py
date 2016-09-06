# -*- coding: utf-8 -*-
import json

import logging
import hashlib
from tornado.options import options
from . import BaseHandler
from autumn.goods import img_url
from autumn.utils import PropDict, json_dumps, json_hook
from autumn.api.weixin import verify_wx_request, wx_response, Weixin
import xml.etree.ElementTree as ET
from datetime import datetime
from tornado.template import Template
import time


class WeixinAPI(BaseHandler):
    # 对应原来的 heartbeat 方法
    def get(self, sp_id):
        params = PropDict([(name, self.get_argument(name).encode('utf-8')) for name in self.request.arguments])
        logging.info('Weixin heartbeat request: %s', json_dumps(params))
        token = hashlib.md5(options.cookie_secret + sp_id).hexdigest()
        if verify_wx_request(params, token):
            self.write(params.echostr)

    # 对应原来的 message 方法
    def post(self, sp_id):
        params = PropDict([(name, self.get_argument(name).encode('utf-8')) for name in self.request.arguments])
        token = hashlib.md5(options.cookie_secret + sp_id).hexdigest()
        if not verify_wx_request(params, token):
            logging.info('weixin msg verification failed')
            return
        else:
            logging.info('weixin request body: %s', self.request.body.replace('\n', ''))
            body = ET.fromstring(self.request.body)
            msg_type = body.findtext('./MsgType')
            sent_from = body.findtext('./FromUserName')
            mem = self.db.get('select * from member where wx_id=%s and sp_id=%s', sent_from, sp_id)
            if not mem:
                # 用户不存在，创建
                mem_id = create_member(self.db, sp_id, sent_from)
                mem = self.db.get('select * from member where id=%s', mem_id)
            properties = self.db.query('select * from supplier_property where sp_id=%s', sp_id)
            sp_props = PropDict([(i.name, i.value) for i in properties])

            # 根据对应的消息类型处理消息
            getattr(self, msg_type)(sp_id, body, mem, sp_props)

    def event(self, sp_id, msg, mem, sp_props):
        msg_time = datetime.fromtimestamp(int(msg.findtext('./CreateTime')))
        event = msg.findtext('./Event').lower()
        wx_id = mem.wx_id
        # 取消订阅，更新数据库
        if event == 'unsubscribe':
            logging.info('user %s un-sub', wx_id)
            self.db.execute('update member set wx_unfollow_at=%s where id=%s', msg_time, mem.id)  # 更新取消时间
            self.write('')  # 退订，什么都不返回
            return
        if event == 'subscribe':
            logging.info('user %s subscribe', wx_id)
            # 查是否存在用户
            if mem:
                # 如果是认证的服务号，去抓取一下用户信息
                if sp_props.wx_type == 'service' and sp_props.wx_verified == '1':
                    app_id = sp_props.app_id
                    app_secret = sp_props.app_secret
                    info = Weixin(method='user/info', db=self.db, sp_id=sp_id, body='')
                    info.set_app_info(app_id, app_secret)
                    response = info.sync_fetch(openid=wx_id, lang='zh_CN')
                    info.parse_response(response)
                    if info.is_ok():
                        nickname = info.message.nickname
                        # 暂时数据库未升级至可以存储emoji字符，故使用以下代码，升级数据库后可删除
                        import re
                        try:
                            # UCS-4
                            highpoints = re.compile(u'[\U00010000-\U0010ffff]')
                        except re.error:
                            # UCS-2
                            highpoints = re.compile(u'[\uD800-\uDBFF][\uDC00-\uDFFF]')
                        nickname = highpoints.sub(u'', nickname)
                        sex = {0: '未知', 1: '男', 2: '女'}.get(info.message.sex)
                        follow_at = datetime.fromtimestamp(info.message.subscribe_time)
                        head_img = info.message.headimgurl
                        self.db.execute('update member set wx_name = %s, gender = %s, last_active=NOW(), max_msg_id=0,'
                                        'head_img = %s, wx_follow_at = %s, country = %s, province = %s, city = %s '
                                        'where wx_id = %s and sp_id = %s',
                                        nickname, sex, head_img, follow_at, info.message.country,
                                        info.message.province, info.message.city,
                                        wx_id, sp_id)
                        logging.info('user %s fetch info successfully', wx_id)
                    else:
                        self.db.execute('update member set wx_follow_at=%s, last_active=NOW(), '
                                        'max_msg_id=0 where id=%s', msg_time, mem.id)
                        logging.info('user %s fetch info failed', wx_id)
                else:
                    self.db.execute('update member set wx_follow_at=%s, last_active=NOW(), '
                                    'max_msg_id=0 where id=%s', msg_time, mem.id)

            # 推送新关注消息
            app_msg = self.db.get('select wam.* '
                                  'from supplier_property sp join wx_app_msg wam on sp.value = wam.id '
                                  'where sp.sp_id = %s and name="wx_sub_msg" ', mem.sp_id)
            if app_msg:
                response = Template(wx_response['news']).generate(
                    to_user=mem.wx_id,
                    from_user=sp_props.wx_id,
                    time=int(time.time()),
                    items=[PropDict(
                        title=app_msg.title,
                        description=app_msg.summary,
                        picurl=img_url(app_msg.cover),
                        url='http://%s.quanfx.com/app_msg/%s?wx_id=%s' % (sp_id, app_msg.id, mem.wx_id)
                    )],
                )
                self.write(response)
                return
            else:
                self.write('')
                return
        if event == 'click':
            event_key = msg.findtext('./EventKey')
            action_type, action = event_key.split(':', 1)
            if action_type == 'website':
                cover = self.db.get('select * from supplier_property where sp_id=%s and name="wx_site_cover"',  sp_id)
                cover = json.loads(cover.value, object_hook=json_hook)
                response = Template(wx_response['news']).generate(
                    to_user=mem.wx_id,
                    from_user=sp_props.wx_id,
                    time=int(time.time()),
                    items=[PropDict(
                        title=cover.title,
                        description=cover.desc,
                        picurl=img_url(cover.pic),
                        url='http://%s.quanfx.com/?wx_id=%s' % (sp_id, mem.wx_id)
                    )],
                )
                self.write(response)
                return
            elif action_type == 'app_msg':
                app_msg = self.db.get('select * from wx_app_msg where id=%s and deleted=0', action)
                if app_msg:
                    response = Template(wx_response['news']).generate(
                        to_user=mem.wx_id,
                        from_user=sp_props.wx_id,
                        time=int(time.time()),
                        items=[PropDict(
                            title=app_msg.title,
                            description=app_msg.summary,
                            picurl=img_url(app_msg.cover),
                            url='http://%s.quanfx.com/app_msg/%s?wx_id=%s' % (sp_id, app_msg.id, mem.wx_id)
                        )],
                    )
                    self.write(response)
                    return
                else:
                    self.write('')
                    return
            elif action_type == 'app_msg_group':
                app_msg_group = self.db.get('select * from wx_app_msg_gp where deleted=0 and id=%s', action)
                if app_msg_group:
                    app_msgs = self.db.query('select * from wx_app_msg where deleted=0 and id in ('
                                             + app_msg_group.app_msgs + ')')
                    response = Template(wx_response['news']).generate(
                        to_user=mem.wx_id,
                        from_user=sp_props.wx_id,
                        time=int(time.time()),
                        items=[PropDict(
                            title=app_msg.title,
                            description=app_msg.summary,
                            picurl=img_url(app_msg.cover),
                            url='http://%s.quanfx.com/app_msg/%s?wx_id=%s' % (sp_id, app_msg.id, mem.wx_id)
                        ) for app_msg in app_msgs],
                    )
                    self.write(response)
                    return
                self.write('')
                return
            elif action_type == 'text':
                sms = self.db.get('select * from wx_menu where action like %s and sp_id = %s limit 1', '%' + action + '%', sp_id)
                if sms:
                    response = Template(wx_response['text']).generate(
                        to_user=mem.wx_id,
                        from_user=sp_props.wx_id,
                        time=int(time.time()),
                        content=sms.action[12:]
                    )
                    self.write(response)
                    return
                self.write('')
                return
            elif action_type == 'member':
                # 取会员卡封面
                cover = self.db.get('select * from supplier_property where sp_id=%s and name="wx_mem_cover"',  sp_id)
                if not cover:
                    # 没有会员卡封面，取官网封面
                    cover = self.db.get('select * from supplier_property where sp_id=%s and name="wx_site_cover"',  sp_id)
                cover = json.loads(cover.value, object_hook=json_hook)
                response = Template(wx_response['news']).generate(
                    to_user=mem.wx_id,
                    from_user=sp_props.wx_id,
                    time=int(time.time()),
                    items=[PropDict(
                        title=cover.title,
                        description=cover.desc,
                        picurl=img_url(cover.pic),
                        url='http://%s.quanfx.com/member?wx_id=%s' % (sp_id, mem.wx_id)
                    )],
                )
                self.write(response)
                return
            elif action_type == 'book':
                cover = self.db.get('select * from wx_booking_setting where sp_id=%s and id = %s', sp_id, action)
                logging.info(cover)
                if cover:
                    info = json.loads(cover.info, object_hook=json_hook)
                    response = Template(wx_response['news']).generate(
                        to_user=mem.wx_id,
                        from_user=sp_props.wx_id,
                        time=int(time.time()),
                        items=[PropDict(
                            title=info.title,
                            description=info.desc,
                            picurl=img_url(info.pic),
                            url='http://%s.quanfx.com/book/%s?wx_id=%s' % (sp_id, cover.id, mem.wx_id)
                        )],
                    )
                    self.write(response)
                    return
                else:
                    self.write('')
                    return
            elif action_type == 'mall':
                cover = self.db.get('select * from supplier_property where sp_id=%s and name="wx_mall_cover"', sp_id)
                if not cover:
                    # 没有商城封面，取官网封面
                    cover = self.db.get('select * from supplier_property where sp_id=%s and name="wx_site_cover"', sp_id)
                cover = json.loads(cover.value, object_hook=json_hook)
                response = Template(wx_response['news']).generate(
                    to_user=mem.wx_id,
                    from_user=sp_props.wx_id,
                    time=int(time.time()),
                    items=[PropDict(
                        title=cover.title,
                        description=cover.desc,
                        picurl=img_url(cover.pic),
                        url='http://%s.quanfx.com/mall/goods?wx_id=%s' % (sp_id, mem.wx_id)
                    )],
                )
                self.write(response)
                return
            elif action_type == 'activity':
                cover = self.db.get('select * from supplier_property where sp_id = %s and name="wx_activity_cover"',
                                    sp_id)
                if not cover:
                    # 没有商城封面，取官网封面
                    cover = self.db.get('select * from supplier_property where sp_id=%s and name="wx_site_cover"', sp_id)
                cover = json.loads(cover.value, object_hook=json_hook)
                response = Template(wx_response['news']).generate(
                    to_user=mem.wx_id,
                    from_user=sp_props.wx_id,
                    time=int(time.time()),
                    items=[PropDict(
                        title=cover.title,
                        description=cover.desc,
                        picurl=img_url(cover.pic),
                        url='http://%s.quanfx.com/activity/list?wx_id=%s' % (sp_id, mem.wx_id)
                    )],
                )
                self.write(response)
                return

    def text(self, sp_id, msg, mem, sp_props):
        """关键词应答"""
        content = msg.findtext('./Content')
        msg_time = datetime.fromtimestamp(int(msg.findtext('./CreateTime')))
        self.db.execute('insert into wx_msg (created_at, sent_from, sent_to, content, wx_msg_id)'
                        'values (%s, %s, %s, %s, %s)', msg_time, mem.id, sp_id, content,
                        msg.findtext('./MsgId'))

        mapping = self.db.get('select * from wx_keyword where sp_id = %s and deleted = 0 and key_type = 1 '
                              'and keyword=%s order by id desc limit 1', sp_id, content)
        if not mapping:
            mapping = self.db.get('select * from wx_keyword where sp_id = %s and deleted = 0 and key_type = 2 '
                                  'and keyword like %s order by id desc limit 1', sp_id, '%'+content+'%')
        if mapping:
            if mapping.response_type == 1:  # 文本
                response = Template(wx_response['text']).generate(
                    to_user=mem.wx_id,
                    from_user=sp_props.wx_id,
                    time=int(time.time()),
                    content=mapping.response,
                )
                self.write(response)
                return
            elif mapping.response_type == 2:  # 图文消息
                app_msg = self.db.get('select id, summary, title, cover from wx_app_msg where id=%s', mapping.response)
                response = Template(wx_response['news']).generate(
                    to_user=mem.wx_id,
                    from_user=sp_props.wx_id,
                    time=int(time.time()),
                    items=[PropDict(
                        title=app_msg.title,
                        description=app_msg.summary,
                        picurl=img_url(app_msg.cover),
                        url='http://%s.quanfx.com/app_msg/%s?wx_id=%s' % (sp_id, app_msg.id, mem.wx_id)
                    )],
                )
                self.write(response)
                return
            elif mapping.response_type == 3:
                app_msg_group = self.db.get('select * from wx_app_msg_gp where deleted=0 and id=%s', mapping.response)
                if app_msg_group:
                    app_msgs = self.db.query('select * from wx_app_msg where deleted=0 and id in ('
                                             + app_msg_group.app_msgs + ')')
                    response = Template(wx_response['news']).generate(
                        to_user=mem.wx_id,
                        from_user=sp_props.wx_id,
                        time=int(time.time()),
                        items=[PropDict(
                            title=app_msg.title,
                            description=app_msg.summary,
                            picurl=img_url(app_msg.cover),
                            url='http://%s.quanfx.com/app_msg/%s?wx_id=%s' % (sp_id, app_msg.id, mem.wx_id)
                        ) for app_msg in app_msgs],
                    )
                    self.write(response)
                    return
                self.write('')
                return
            
        self.write('')


def create_member(db, sp_id, wx_id):
    """记录新会员"""
    # 选分组
    cate = db.get('select id from member_category where sp_id=%s and name="未分组" '
                  'and deleted=0', sp_id)
    # 商户默认分组不存在，新建一个
    if not cate:
        cate_id = db.execute('insert into member_category (sp_id, name, deleted) '
                             'values (%s, "未分组", 0)', sp_id)
    else:
        cate_id = cate.id
    mid = db.execute('insert into member (sp_id, wx_id, source, created_at, last_active, level, '
                     'category_id, wx_follow_at, max_msg_id) values (%s, %s, "微信", NOW(), NOW(), 0,'
                     '%s, NOW(), 0)', sp_id, wx_id, cate_id)
    return mid



