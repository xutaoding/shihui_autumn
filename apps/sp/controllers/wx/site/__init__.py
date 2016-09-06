# -*- coding: utf-8 -*-
from ... import BaseHandler
from ... import require
from tornado.httpclient import HTTPError
from autumn.goods import img_url
import json
from autumn.utils import json_hook, json_dumps, PropDict


class SiteCover(BaseHandler):
    @require()
    def get(self):
        sp_id = self.current_user.supplier_id
        cover = self.db.get('select * from supplier_property where sp_id=%s and name="wx_site_cover"', sp_id)
        if not cover:
            self.redirect(self.reverse_url('wx.site.cover.edit'))
            return
        cover = json.loads(cover.value, object_hook=json_hook)
        self.render('wx/site/cover.html', cover=cover, img_url=img_url)


class SiteCoverEdit(BaseHandler):
    @require()
    def get(self):
        sp_id = self.current_user.supplier_id
        cover = self.db.get('select * from supplier_property where sp_id=%s and name="wx_site_cover"', sp_id)
        if cover:
            cover = json.loads(cover.value, object_hook=json_hook)
            cover = PropDict(cover)
        else:
            cover = PropDict()
        self.render('wx/site/cover_edit.html', cover=cover, img_url=img_url)

    @require()
    def post(self):
        sp_id = self.current_user.supplier_id
        self.db.execute('delete from supplier_property where sp_id=%s and name="wx_site_cover"', sp_id)
        self.db.execute('insert into supplier_property(sp_id, name, value) values (%s, "wx_site_cover", %s)',
                        sp_id, json_dumps({'pic': self.get_argument('pic'),
                                           'title': self.get_argument('title'),
                                           'desc': self.get_argument('desc')}))
        self.redirect(self.reverse_url('wx.site.cover'))


class SiteTpl(BaseHandler):
    @require()
    def get(self):
        sp_id = self.current_user.supplier_id
        templates = self.db.query('select id,name,pic from wx_site_tpl where (sp_id is null) '
                                  'or (sp_id is not null and sp_id=%s)', sp_id)
        cur_tpl = self.db.get('select * from supplier_property where sp_id=%s and name="site_tpl_id"', sp_id)
        self.render('wx/site/tpl.html', templates=templates, cur_tpl=cur_tpl)

    @require()
    def post(self):
        sp_id = self.current_user.supplier_id
        ids = [i.id for i in self.db.query('select id,name,pic from wx_site_tpl where (sp_id is null) '
                                           'or (sp_id is not null and sp_id=%s)', sp_id)]
        tpl_id = int(self.get_argument('id', '0'))
        if tpl_id not in ids:
            raise HTTPError(403)
        self.db.execute('delete from supplier_property where sp_id=%s and name="site_tpl_id"', sp_id)
        self.db.execute('insert into supplier_property(sp_id, name, value) values (%s, "site_tpl_id", %s)',
                        sp_id, tpl_id)
        self.redirect(self.reverse_url('wx.site.tpl'))


class SlideList(BaseHandler):
    @require()
    def get(self):
        sp_id = self.current_user.supplier_id
        slides = self.db.query('select * from wx_site_slide where sp_id=%s and deleted=0 limit 5', sp_id)
        app_msgs = self.db.query('select * from wx_app_msg where sp_id=%s and deleted=0', sp_id)
        self.render('wx/site/slide_list.html', slides=slides, app_msgs=app_msgs, img_url=img_url)


class SlideUpdate(BaseHandler):
    @require()
    def post(self):
        name, display_order, pic, link_type, val, is_show, slide_id, action = \
            map(self.get_argument, ('name', 'display_order', 'pic', 'link_type', 'val', 'is_show', 'id', 'action'))

        if action == 'add':
            slide_id = self.db.execute('insert into wx_site_slide(sp_id, name, display_order, pic, link_type, val, '
                                       'is_show) values(%s, %s, %s, %s, %s, %s, %s)', self.current_user.supplier_id,
                                       name, display_order, pic, link_type, val, is_show)
        elif action == 'edit':
            self.db.execute('update wx_site_slide set name=%s, display_order=%s, pic=%s, link_type=%s, val=%s, '
                            'is_show=%s where sp_id=%s and id=%s',
                            name, display_order, pic, link_type, val, is_show, self.current_user.supplier_id, slide_id)
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write({'ok': True, 'slide_id': slide_id, 'action': action})

links = [
    {'link_type': 0, 'name': '图文消息', 'val': ''},
    {'link_type': 1, 'name': '微会员', 'val': '/member'},
    {'link_type': 2, 'name': '微官网', 'val': '/'},
    {'link_type': 3, 'name': '微预约', 'val': '/book'},
    {'link_type': 4, 'name': '门店', 'val': '/shops'},
]


class ColumnList(BaseHandler):
    @require()
    def get(self):
        sp_id = self.current_user.supplier_id
        columns = self.db.query('select * from wx_site_column where sp_id=%s and deleted=0 limit 9', sp_id)
        app_msgs = self.db.query('select * from wx_app_msg where sp_id=%s and deleted=0', sp_id)
        self.render('wx/site/column_list.html', columns=columns, app_msgs=app_msgs, img_url=img_url, links=links)


class ColumnUpdate(BaseHandler):
    @require()
    def post(self):
        name, display_order, pic, link_type, val,  is_show, slide_id, icon, action = \
            map(self.get_argument, ('name', 'display_order', 'pic', 'link_type', 'val', 'is_show', 'id', 'icon', 'action'))
        if action == 'add':
            self.db.execute('insert into wx_site_column(sp_id, name, display_order, pic, link_type, val, is_show, icon)'
                            ' values(%s, %s, %s, %s, %s, %s, %s, %s)',
                            self.current_user.supplier_id, name, display_order, pic, link_type, val, is_show, icon)
        elif action == 'edit':
            self.db.execute('update wx_site_column set name=%s, display_order=%s, pic=%s, link_type=%s, val=%s,'
                            ' is_show=%s, icon=%s where sp_id=%s and id=%s',
                            name, display_order, pic, link_type, val, is_show, icon,
                            self.current_user.supplier_id, slide_id)
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write({'ok': True})
