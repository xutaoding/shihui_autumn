# -*- coding: utf-8 -*-


from .. import BaseHandler
from .. import require
import hashlib
import json
import logging
from datetime import datetime, timedelta
from tornado.gen import coroutine
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.options import options
from autumn.api.weixin import Weixin
from autumn.utils import json_hook


class SupplierSetting(BaseHandler):
    """商户开通微信设置"""
    @require('developer')
    def get(self):
        self.render('temple/wx/supplier.html')

    @require('developer')
    def post(self):
        sp_id = self.get_argument('supplier_id', '')

        if not sp_id:
            self.redirect(self.reverse_url('temple.wx.setting'))
            return

        supplier = self.db.get('select * from supplier where id=%s and deleted=0', sp_id)
        if not supplier:
            self.redirect(self.reverse_url('temple.wx.setting'))
            return

        token = hashlib.md5(options.cookie_secret + str(sp_id)).hexdigest()
        is_binding = self.db.get('select * from supplier_property where sp_id=%s and name="wx_type"', sp_id)
        # 默认设置
        wx_type = 'service'
        wx_verified = '1'
        wx_id = ''
        app_id = ''
        app_secret = ''
        if is_binding:
            wx_type = is_binding.value
            wx_id = self.db.get('select * from supplier_property where sp_id=%s and name="wx_id"', sp_id).value
            wx_verified = self.db.get('select * from supplier_property where sp_id=%s and name="wx_verified"', sp_id).value
            # 除了未认证的订阅号，其他都有app_id和app_secret
            if not (wx_type == 'subscribe' and wx_verified == '0'):
                app_id = self.db.get('select * from supplier_property where sp_id=%s and name="app_id"', sp_id).value
                app_secret = self.db.get('select * from supplier_property where sp_id=%s and name="app_secret"', sp_id).value

        self.render('temple/wx/setting.html', token=token, supplier=supplier, wx_type=wx_type, wx_verified=wx_verified,
                    app_id=app_id, app_secret=app_secret, wx_id=wx_id)


class Binding(BaseHandler):
    """微信接入"""
    @coroutine
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        sp_id = self.get_argument('sp_id', '')
        wx_type = self.get_argument('account_type', '')
        wx_verified = self.get_argument('verified', '')
        sp_wx_id = self.get_argument('sp_wx_id', '')
        if not sp_id:
            self.write({'error': 'error', 'msg': '商户错误'})
            return
        if not wx_type:
            self.write({'error': 'error', 'msg': '微信账号类型为空'})
            return
        app_id = self.get_argument('app_id', '')
        app_secret = self.get_argument('app_secret', '')

        # 如果没有未分组，则新建一个未分组
        if not (self.db.get('select * from member_category where sp_id=%s and name="未分组"', sp_id)):
            self.db.execute('insert into member_category (sp_id, wx_grp_id, name, deleted) '
                            'values (%s, %s, %s, 0)', sp_id, '0', '未分组')

        if app_id or app_secret:
            # 有传入参数，尝试验证
            http_client = AsyncHTTPClient()
            request = HTTPRequest(url='%s/token?grant_type=client_credential&appid=%s&secret=%s' %
                                      (options.weixin_gateway_url, app_id, app_secret))
            response = yield http_client.fetch(request)
            response = json.loads(response.body, object_hook=json_hook)
            if 'errcode' in response:
                logging.error('weixin setting failed: %s', response.errmsg)
                self.write({'error': response.errmsg, 'msg': '验证失败，请确认您的app_id和app_secret'})
                return
            else:
                logging.info('add sp=%s app_id: %s, app_secret: %s', sp_id, app_id, app_secret)
                # 先删除
                self.db.execute('delete from supplier_property where sp_id=%s and name="app_id"', sp_id)
                self.db.execute('delete from supplier_property where sp_id=%s and name="app_secret"', sp_id)
                self.db.execute('delete from supplier_property where sp_id=%s and name="wx_id"', sp_id)
                # 再插入
                self.db.execute('insert into supplier_property (sp_id, name, value) '
                                'values (%s, "app_id", %s)', sp_id, app_id)
                self.db.execute('insert into supplier_property (sp_id, name, value) '
                                'values (%s, "app_secret", %s)', sp_id, app_secret)
                self.db.execute('insert into supplier_property (sp_id, name, value) '
                                'values (%s, "wx_id", %s)', sp_id, sp_wx_id)
                token = response.access_token
                expire_at = (datetime.now() + timedelta(seconds=(response['expires_in']-300))).strftime('%Y-%m-%d %H:%M:%S')
                logging.info('add sp=%s access_token: %s', sp_id, token)
                # 先删除
                self.db.execute('delete from supplier_property where sp_id=%s and name="token"', sp_id)
                self.db.execute('delete from supplier_property where sp_id=%s and name="token_expire_at"', sp_id)
                self.db.execute('delete from supplier_property where sp_id=%s and name="wx_type"', sp_id)
                self.db.execute('delete from supplier_property where sp_id=%s and name="wx_verified"', sp_id)
                # 再插入
                self.db.execute('insert into supplier_property (sp_id, name, value) '
                                'values (%s, "token", %s)', sp_id, token)
                self.db.execute('insert into supplier_property (sp_id, name, value) '
                                'values (%s, "token_expire_at", %s)', sp_id, expire_at)
                self.db.execute('insert into supplier_property (sp_id, name, value) '
                                'values (%s, "wx_type", %s)', sp_id, wx_type)
                self.db.execute('insert into supplier_property (sp_id, name, value) '
                                'values (%s, "wx_verified", %s)', sp_id, wx_verified)
                # 不同步了，发群组消息，用本地的分组
                # 添加微信已有分组到本地,只有认证的服务好有
                #if wx_type == 'service' and wx_verified == '1':
                #    wx = Weixin(db=self.db, sp_id=sp_id, method='groups/get', body='')
                #    wx.set_app_info(app_id, app_secret)
                #    response = yield wx()
                #    wx.parse_response(response.body)
                #    if wx.is_ok():
                #        for group in wx.message.groups:
                #            if group.id != 0:
                #                # 插入除了 未分组 之外的其他组
                #                self.db.execute('insert into member_category (sp_id, wx_grp_id, name, deleted) '
                #                                'values (%s, %s, %s, 0)', sp_id, group.id, group.name)
                #        self.write({'ok': '接入成功'})
                #        return
                #    else:
                #        self.write({'error': response.errmsg, 'msg': '同步微信分组失败'})
                #        return
                self.write({'ok': '接入成功'})
                return
        else:
            # 先删除
            self.db.execute('delete from supplier_property where sp_id=%s and name="wx_id"', sp_id)
            self.db.execute('delete from supplier_property where sp_id=%s and name="wx_type"', sp_id)
            self.db.execute('delete from supplier_property where sp_id=%s and name="wx_verified"', sp_id)
            # 再插入
            self.db.execute('insert into supplier_property (sp_id, name, value) '
                            'values (%s, "wx_id", %s)', sp_id, sp_wx_id)
            self.db.execute('insert into supplier_property (sp_id, name, value) '
                            'values (%s, "wx_type", %s)', sp_id, wx_type)
            self.db.execute('insert into supplier_property (sp_id, name, value) '
                            'values (%s, "wx_verified", %s)', sp_id, wx_verified)
            self.write({'ok': '接入成功'})
            return

