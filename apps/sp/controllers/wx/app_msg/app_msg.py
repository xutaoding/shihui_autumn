# -*- coding: utf-8 -*-

from ... import BaseHandler
from ... import require
from tornado.web import HTTPError
from voluptuous import Schema, Length, All, Coerce, Any
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator
from autumn.goods import img_url


class List(BaseHandler):
    @require()
    def get(self):
        sql = """select am.* from wx_app_msg am, supplier sp
                 where am.sp_id=sp.id and sp.id=%s and am.deleted=0 order by am.created_at desc"""
        page = Paginator(self, sql, [self.current_user.supplier_id])
        for item in page.rows:
            item.cover = img_url(item.cover)
        self.render('wx/app_msg/list.html', page=page, img_url=img_url)


add_schema = Schema(
    {
        'title': All(str, Length(min=1)),
        'author': All(str),
        'cover': All(str, Length(min=1)),
        'img_url': All(str, Length(min=1)),
        'summary': All(str),
        'content': All(str, Length(min=1)),
        'action': All(str, Length(min=1)),
        'id': Any(str, Coerce(int)),
    }
)


class Add(BaseHandler):
    @require()
    def get(self):
        form = Form(self.request.arguments, add_schema)
        form.action['value'] = 'add'
        self.render('wx/app_msg/add.html', form=form)

    @require()
    def post(self):
        form = Form(self.request.arguments, add_schema)
        if not form.validate():
            self.render('wx/app_msg/add.html', form=form)
            return
        self.db.execute('insert into wx_app_msg(sp_id, title, author, cover, summary, content, created_at) '
                        'values (%s, %s, %s, %s, %s, %s, NOW())',
                        self.current_user.supplier_id, form.title.value, form.author.value, form.cover.value,
                        form.summary.value, form.content.value)
        self.redirect(self.reverse_url('weixin.app_msg'))


class Del(BaseHandler):
    @require()
    def post(self):
        self.db.execute('update wx_app_msg set deleted=1 where sp_id=%s and id=%s',
                        self.current_user.supplier_id, self.get_argument('msg_id', 0))
        self.redirect(self.reverse_url('weixin.app_msg'))


class Edit(BaseHandler):
    @require()
    def get(self):
        msg_id = self.get_argument('id', 0)
        msg = self.db.get('select * from wx_app_msg where deleted=0 and sp_id=%s and id=%s',
                          self.current_user.supplier_id, msg_id)

        if not msg:
            raise HTTPError(404)

        form = Form(msg, add_schema)
        form.action['value'] = 'edit'
        form.img_url['value'] = img_url(msg.cover)

        self.render('wx/app_msg/add.html', form=form)

    @require()
    def post(self):
        form = Form(self.request.arguments, add_schema)
        if not form.validate():
            print(form.errors)
            self.render('wx/app_msg/add.html', form=form)
            return

        self.db.execute('update wx_app_msg set title=%s, author=%s, cover=%s, summary=%s, content=%s '
                        'where id=%s and sp_id=%s',
                        form.title.value, form.author.value, form.cover.value, form.summary.value, form.content.value,
                        form.id.value, self.current_user.supplier_id)
        self.redirect(self.reverse_url('weixin.app_msg'))


class Detail(BaseHandler):
    @require()
    def get(self, msg_id):
        app_msg = self.db.get('select * from wx_app_msg where id = %s', msg_id)

        self.render('wx/app_msg/detail.html', app_msg=app_msg, img_url=img_url)

