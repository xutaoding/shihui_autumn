# -*- coding: utf-8 -*-

from ... import BaseHandler, require
from autumn.api.weixin import upload_news, sent_msg, upload_pic
from tornado.gen import coroutine
from autumn.utils import json_dumps


class Send(BaseHandler):
    @require()
    def get(self):
        user = self.current_user
        wx_type = self.db.get('select value from supplier_property where name="wx_type" and sp_id = %s',
                              user.supplier_id)
        wx_verified = self.db.get('select value from supplier_property where name="wx_verified" and sp_id = %s',
                                  user.supplier_id)
        if wx_type.value == 'subscribe' or wx_verified.value == '0':
            self.render('wx/send_message/send.html', error=True)
            pass
        group = self.db.query('select id, name from member_category where deleted = 0 and sp_id = %s', user.supplier_id)

        app_msg = self.db.query('select id, title from wx_app_msg where sp_id = %s and deleted = 0', user.supplier_id)

        self.render('wx/send_message/send.html', error=False, group=group, app_msg=app_msg)

    @require()
    @coroutine
    def post(self):
        msg_type = self.get_argument('msg-type')
        msg_id = self.get_argument('msg-id')
        group_id = self.get_argument('group-id')

        sp_id = self.current_user.supplier_id
        if msg_type == '0':
            msg_list = [msg_id]
        else:
            msg_gp = self.db.get('select app_msgs from wx_app_msg_gp where id = %s and sp_id = %s', msg_id, sp_id)
            if msg_gp:
                msg_list = msg_gp.app_msgs.split(',')
            else:
                msg_list = []

        app_id = self.db.get('select * from supplier_property where name = "app_id" and sp_id = %s', sp_id)['value']
        app_secret = self.db.get('select * from supplier_property where name = "app_secret" and sp_id = %s', sp_id)['value']

        pic_dict = yield upload_pic(self.db, sp_id, msg_list, app_id, app_secret)

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        if pic_dict:
            upload_news_load = yield upload_news(self.db, pic_dict, app_id, app_secret, sp_id)
            if upload_news_load['ok']:
                users = self.db.query('select wx_id from member where sp_id = %s and category_id = %s',
                                      sp_id, group_id)
                user_list = [user.wx_id for user in users]
                send = yield sent_msg(self.db, user_list, app_id, app_secret, sp_id, upload_news_load['media'])
                if send['code'] == 0:
                    self.write({'ok': True, 'errmsg': '发送消息成功'})
                    return
                else:
                    self.write({'ok': False, 'errmsg': send['msg']})
                    return
            else:
                self.write({'ok': False, 'errmsg': upload_news_load['errmsg']})
                return
        else:
            self.write({'ok': False, 'errmsg': '上传图文信息图片失败'})
            return


class MsgAjax(BaseHandler):
    @require()
    def get(self):
        msg_type = self.get_argument('msg_type')

        if msg_type == '0':
            msgs = self.db.query('select id, title name from wx_app_msg where deleted = 0 and sp_id = %s',
                                 self.current_user.supplier_id)
        elif msg_type == '1':
            msgs = self.db.query('select id, name from wx_app_msg_gp where deleted = 0 and sp_id = %s',
                                 self.current_user.supplier_id)
        else:
            msgs = []

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps(msgs))