# -*- coding: utf-8 -*-

from tornado.httputil import url_concat
from voluptuous import Schema, Length, Any

from autumn.torn.form import Form
from .. import BaseHandler
from .. import require
from autumn.torn.paginator import Paginator

news_schema = Schema({
    'title': Length(min=1),
    'content': Length(min=1),
    'id': str,
    'action': Any('edit', 'add'),
}, extra=True)


class NewsAdd(BaseHandler):
    @require('operator')
    def get(self):
        form = Form(self.request.arguments, news_schema)
        form.action.value = 'add'

        self.render('seewi/news.html', form=form, error='')

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, news_schema)

        if not form.validate():
            return self.render('seewi/news.html', form=form, error='error')

        self.db.execute('insert into news (title,content,created_at,created_by,deleted) values (%s,%s,now(),%s,0)',
                        form.title.value.strip(), form.content.value.strip(),
                        self.current_user.name)

        self.redirect(url_concat(self.reverse_url('seewi.news.show_list'), {'id': form.id.value.strip()}))


class NewsEdit(BaseHandler):
    @require('operator')
    def get(self):
        news = self.db.get('select id, title,content from news where id = %s', self.get_argument('id'))
        form = Form(news, news_schema)
        form.action.value = 'edit'

        self.render('seewi/news.html', form=form, error='')

    @require('operator')
    def post(self):
        form = Form(self.request.arguments, news_schema)

        if not form.validate():
            return self.render('seewi/news.html', form=form, error='error')

        self.db.execute('update news set  title= %s, content = %s where id = %s',
                        form.title.value.strip(), form.content.value.strip(), form.id.value.strip())

        self.redirect(url_concat(self.reverse_url('seewi.news.show_list'), {'id': form.id.value.strip()}))


class NewsList(BaseHandler):
    @require()
    def get(self):
        sql = """select c.* from news c where deleted=0 and type = 0 """

        form = Form(self.request.arguments, news_schema)
        params = []
        news_id = self.get_argument('id', '')

        if news_id:
            sql += 'and c.id = %s '
            params.append(news_id)

        sql += 'order by c.id desc'
        page = Paginator(self, sql, params)
        self.render('seewi/news_list.html', page=page, form=form)


class NewsDelete(BaseHandler):
    @require('operator')
    def post(self):
        news_id = self.get_argument('id')
        self.db.execute(' update news set deleted = 1 where id = %s', news_id)

        self.redirect(self.reverse_url('seewi.news.show_list'))
