# -*- coding: utf-8 -*-
from ... import BaseHandler
from ... import require
from tornado.web import HTTPError
from autumn.torn.paginator import Paginator
from voluptuous import Schema, Length, All, Coerce
from autumn.torn.form import Form

add_schema = Schema(
    {
        'title': All(str, Length(min=1)),
        'content': All(str, Length(min=1)),
        'action': All(str, Length(min=1)),
        'id': str,
    }
)


class List(BaseHandler):
    """微信会员消息列表"""
    @require()
    def get(self):
        sql = 'select mm.* from wx_member_msg mm where mm.type=0 and mm.iid=%s order by created_at desc'
        page = Paginator(self, sql, [self.current_user.supplier_id])
        self.render('wx/member/mem_msg/list.html', page=page)


class Add(BaseHandler):
    """新建会员消息"""
    @require()
    def get(self):
        form = Form(self.request.arguments, add_schema)
        form.action['value'] = 'add'
        self.render('wx/member/mem_msg/add.html', form=form)

    @require()
    def post(self):
        # todo 目前只支持群发消息功能
        form = Form(self.request.arguments, add_schema)
        if not form.validate():
            self.render('wx/member/mem_msg/add.html', form=form)
            return
        self.db.execute('insert into wx_member_msg(title, content, created_at, iid, type, to_all) '
                        'values (%s, %s, NOW(), %s, %s, %s)',
                        form.title.value, form.content.value, self.current_user.supplier_id, 0, 0)
        self.redirect(self.reverse_url('wx.mem_msg'))


class Edit(BaseHandler):
    @require()
    def get(self):
        msg_id = self.get_argument('id', 0)
        msg = self.db.get('select * from wx_member_msg where id=%s', msg_id)
        if not msg:
            raise HTTPError(404)

        form = Form(msg, add_schema)
        form.action['value'] = 'edit'

        self.render('wx/member/mem_msg/add.html', form=form)

    @require()
    def post(self):
        form = Form(self.request.arguments, add_schema)
        if not form.validate():
            self.render('wx/member/mem_msg/add.html', form=form)
            return
        try:
            self.db.execute('update wx_member_msg set title=%s, content=%s, created_at=NOW() where id=%s and type=%s and '
                            'iid=%s',
                            form.title.value, form.content.value, form.id.value, 0, self.current_user.supplier_id)
        except Exception:
            self.redirect(self.reverse_url('wx.mem_msg'))
        self.redirect(self.reverse_url('wx.mem_msg'))