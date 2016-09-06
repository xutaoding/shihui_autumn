#-*- coding: utf-8 -*-
from tornado.httputil import url_concat
from voluptuous import Schema, Length, Any

from autumn.torn.form import Form
from .. import BaseHandler
from .. import require
from autumn.torn.paginator import Paginator

notice_schema = Schema({
    'title': Length(min=1),
    'content': Length(min=1),
    'id': str,
    'action': Any('edit', 'add'),
}, extra=True)


class Show(BaseHandler):
    def get(self):
        form = Form(self.request.arguments, notice_schema)
        sql = 'select * from news where deleted = 0 and type = 1 order by created_at desc'
        params = []
        page = Paginator(self, sql, params)

        self.render('admin/notice_list.html', form=form, page=page)


class Add(BaseHandler):
    @require('admin')
    def get(self):
        form = Form(self.request.arguments, notice_schema)
        form.action.value = 'add'

        self.render('admin/notice.html', form=form, error='')

    @require('admin')
    def post(self):
        form = Form(self.request.arguments, notice_schema)

        if not form.validate():
            return self.render('admin/notice.html', form=form, error='error')

        self.db.execute('insert into news (title,content,created_at,created_by,deleted, type) '
                        'values (%s,%s,now(),%s,0, 1)', form.title.value.strip(), form.content.value.strip(),
                        self.current_user.name)

        self.redirect(self.reverse_url('admin.notice'))


class Edit(BaseHandler):
    @require('admin')
    def get(self, nid):
        news = self.db.get('select id, title, content from news where id = %s and type=1 order by created_at desc', nid)
        form = Form(news, notice_schema)
        form.action.value = 'edit'

        self.render('admin/notice.html', form=form, error='')

    @require('admin')
    def post(self, nid):
        form = Form(self.request.arguments, notice_schema)

        if not form.validate():
            return self.render('admin/notice.html', form=form, error='error')

        self.db.execute('update news set  title= %s, content = %s, created_at = %s where id = %s and type=1',
                        form.title.value.strip(), form.content.value.strip(), nid)

        self.redirect(self.reverse_url('admin.notice'))


class Delete(BaseHandler):
    @require('admin')
    def post(self):
        news_id = self.get_argument('id')
        self.db.execute(' update news set deleted = 1 where id = %s and type=1', news_id)

        self.redirect(self.reverse_url('admin.notice'))


class Detail(BaseHandler):
    @require()
    def get(self, nid):
        notice = self.db.get('select * from news where id = %s and type=1', nid)
        self.render('admin/notice_detail.html', notice=notice)