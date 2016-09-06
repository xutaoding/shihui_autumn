# -*- coding: utf-8 -*-
from tornado.httputil import url_concat
from tornado.template import Template


class Paginator():
    """ 分页器 """
    def __init__(self, handler, sql, args, page_size=20):
        assert page_size > 1
        self.path = handler.request.path
        self.args = dict([(key, handler.request.arguments[key][0]) for key in handler.request.arguments])

        # 当前页
        self.current_page = int(self.args.pop('page', 1))
        assert self.current_page > 0

        # 数据
        sql = '%s limit %s,%s' % (sql, page_size*(self.current_page-1), page_size+1)
        self.rows = handler.application.db.query(sql, *args)

        # 上一页
        self.has_prev_page = self.current_page > 1

        # 下一页
        self.has_next_page = (len(self.rows) == page_size+1)
        if self.has_next_page:
            self.rows = self.rows[:-1]

    def gen_html(self, name):
        return Template(templates[name]).generate(p=self)

    def gen_link(self, page):
        return url_concat(self.path, dict(self.args, page=page))

    def agent_links(self):
        """ 代理商后台分页 """
        return self.gen_html('agent')

    def boot_links(self):
        """ 微信前端分页"""
        return self.gen_html('wx')

    def links(self):
        """ 分页 HTML 链接 """
        return self.gen_html('alice')


templates = {
    'agent': """
        <div class="clearfix">
            <ul class="pagination no-margin">
                <li class="{{ '' if p.has_prev_page else 'disabled' }}">
                    <a href="{{ p.gen_link(p.current_page-1) if p.has_prev_page else 'javascript:;' }}">上一页</a>
                </li>
                <li><a href="javascript:;"> 第 {{ p.current_page }} 页 </a></li>
                <li class="{{ '' if p.has_next_page else 'disabled' }}">
                    <a href="{{ p.gen_link(p.current_page+1) if p.has_next_page else 'javascript:;' }}">下一页</a>
                </li>
            </ul>
        </div>
    """,

    'wx': """
        <ul class="pager">
        {% if p.has_prev_page %}
            <li><a href="{{ p.gen_link(p.current_page-1) }}">上一页</a></li>
        {% end %}
        {% if p.has_next_page %}
            <li><a href="{{ p.gen_link(p.current_page+1) }}">下一页</a></li>
        {% end %}
        </ul>
    """,

    'alice': """
        <div style="margin-top:20px;">
            <a href="{{ p.gen_link(p.current_page-1) if p.has_prev_page else 'javascript:;' }}"
               class="ui-button {{'ui-button-sorange' if p.has_prev_page else 'ui-button-sdisable'}}">上一页</a>

            <span class="ui-paging-info">第<span class="ui-paging-bold">{{p.current_page}}</span>页</span>

            <a href="{{ p.gen_link(p.current_page+1) if p.has_next_page else 'javascript:;' }}"
               class="ui-button {{'ui-button-sorange' if p.has_next_page else 'ui-button-sdisable'}}">下一页</a>

            <form method="get" action="{{p.path}}" style="display: inline">
            {% for key in p.args %}
                <input type="hidden" name="{{key}}" value="{{p.args[key]}}"/>
            {% end %}
                <button type="submit" class="ui-paging-info ui-paging-goto"
                        style="line-height:initial">跳转到第</button>
                <span class="ui-paging-which"><input name="page" type="text" value="{{p.current_page}}">页</span>
            </form>
        </div>
    """,
}
