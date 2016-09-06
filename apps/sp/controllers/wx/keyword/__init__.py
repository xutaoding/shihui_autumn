# -*- coding: utf-8 -*-

from ... import BaseHandler, require


class List(BaseHandler):
    @require()
    def get(self):
        sp_id = self.current_user.supplier_id
        key_maps = self.db.query('select * from wx_keyword where deleted = 0 and sp_id = %s',
                                 sp_id)

        self.render('wx/keyword/list.html', key_maps=key_maps)


class Add(BaseHandler):
    @require()
    def get(self):
        pictures = self.db.query('select am.id, am.title from wx_app_msg am '
                                 ' where am.sp_id = %s and am.deleted = 0',
                                 self.current_user.supplier_id)
        groups = self.db.query('select g.id, g.name from wx_app_msg_gp g '
                               'where g.sp_id = %s and g.deleted = 0', self.current_user.supplier_id)

        self.render('wx/keyword/add.html', pictures=pictures, groups=groups, action='add')

    @require()
    def post(self):
        keyword = self.get_argument('key', '')
        key_type = 1 if self.get_argument('key_type', 'off') == 'on' else 2

        response = self.get_argument('response', '')
        response_type = self.get_argument('option')

        self.db.execute('insert into wx_keyword(keyword, key_type, response_type, sp_id, response) '
                        'values(%s, %s, %s, %s, %s)',
                        keyword, key_type, response_type, self.current_user.supplier_id, response)

        self.redirect(self.reverse_url('weixin.keyword'))


class Edit(BaseHandler):
    @require()
    def get(self):
        sp_id = self.current_user.supplier_id
        key_id = self.get_argument('key_id', 0)

        pictures = self.db.query('select m.id, m.title from wx_app_msg m '
                                 'where m.deleted = 0 and m.sp_id = %s', sp_id)
        groups = self.db.query('select g.id, g.name from wx_app_msg_gp g '
                               'where g.deleted = 0 and g.sp_id = %s', sp_id)

        key_map = self.db.get('select * from wx_keyword where id = %s', key_id)

        params = {
            'pictures': pictures,
            'groups': groups,
            'key_map': key_map,
            'action': 'edit'
        }
        self.render('wx/keyword/add.html', **params)

    @require()
    def post(self):
        key_id = self.get_argument('key_id', 0)

        keyword = self.get_argument('key', '')
        key_type = self.get_argument('key_type', 2)

        response = self.get_argument('response', '')
        response_type = self.get_argument('option')

        self.db.execute('update wx_keyword set keyword=%s, key_type=%s, response=%s, response_type=%s where id=%s',
                        keyword, key_type, response, response_type, key_id)

        self.redirect(self.reverse_url('weixin.keyword'))


class Delete(BaseHandler):
    @require()
    def post(self):
        key_id = self.get_argument('key_id', 0)

        self.db.execute('update wx_keyword set deleted = 1 where id = %s', key_id)

        self.redirect(self.reverse_url('weixin.keyword'))