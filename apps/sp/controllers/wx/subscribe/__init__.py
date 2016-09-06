# -*- coding: utf-8 -*-

from ... import BaseHandler, require
from autumn.goods import img_url


class Feedback(BaseHandler):
    """用户关注公众号后反馈的消息"""
    @require()
    def get(self):
        msgs = self.db.query('select * from wx_app_msg where deleted = 0 and sp_id = %s', self.current_user.supplier_id)
        choice = self.db.get('select wam.* '
                             'from supplier_property sp join wx_app_msg wam on sp.value = wam.id '
                             'where sp.name="wx_sub_msg" and sp.sp_id = %s', self.current_user.supplier_id)

        self.render('wx/subscribe/feedback.html', msgs=msgs, choice=choice, img_url=img_url)

    @require()
    def post(self):
        msg_id = self.get_argument('msgs')
        supplier_id = self.current_user.supplier_id
        msg = self.db.get('select id from wx_app_msg where sp_id = %s and id = %s',
                          supplier_id, msg_id)
        if msg:
            self.db.execute('delete from supplier_property where sp_id = %s and name="wx_sub_msg"', supplier_id)
            self.db.execute('insert into supplier_property(sp_id, name, value) values(%s, "wx_sub_msg", %s)',
                            supplier_id, msg_id)

        self.redirect(self.reverse_url('wx.subscribe.feedback'))
