# -*- coding: utf-8 -*-

import tornado.web
from .. import BaseHandler
from tornado.web import HTTPError
from autumn.goods import img_url


class Detail(BaseHandler):
    """手机端图文消息详情页面"""
    @tornado.web.authenticated
    def get(self, app_msg_id):
        user = self.current_user
        app_msg = self.db.get('select * from wx_app_msg where id=%s and sp_id=%s and deleted=0',
                              app_msg_id, user.sp_id)
        if not app_msg:
            raise HTTPError(404)
        else:
            self.render('page/app_msg_detail.html', app_msg=app_msg, img_url=img_url)
        pass
