# -*- coding: utf-8 -*-

from ... import BaseHandler, require
from autumn.goods import img_url
import itertools


class List(BaseHandler):
    @require()
    def get(self):
        groups = self.db.query('select * from wx_app_msg_gp where deleted = 0 and sp_id = %s order by created_at desc',
                               self.current_user.supplier_id)
        if groups:
            app_msg_id_set = set(itertools.chain(*[gp.app_msgs.split(',') for gp in groups]))
            app_msgs = self.db.query('select * from wx_app_msg where id in ('
                                     + ','.join(['%s']*len(app_msg_id_set)) + ')', *list(app_msg_id_set))
            app_msg_dict = dict([(msg.id, msg) for msg in app_msgs])
            for group in groups:
                group['app_msg_list'] = [app_msg_dict[int(i)] for i in group.app_msgs.split(',')]

        self.render('wx/app_msg/group_list.html', groups=groups, img_url=img_url)


class Add(BaseHandler):
    @require()
    def get(self):
        msg = self.db.query('select id, title from wx_app_msg where deleted = 0 and sp_id = %s',
                            self.current_user.supplier_id)

        self.render('wx/app_msg/group.html', action='add', msg=msg)

    @require()
    def post(self):
        name = self.get_argument('name', '')
        app_msgs = self.get_argument('msg_group', '')
        app_msgs = app_msgs[:len(app_msgs) - 1]

        self.db.execute('insert into wx_app_msg_gp(sp_id, name, app_msgs, created_at) values(%s, %s, %s, NOW())',
                        self.current_user.supplier_id, name, app_msgs)

        self.redirect(self.reverse_url('weixin.app_msg.group'))


class Edit(BaseHandler):
    @require()
    def get(self):
        gp_id = self.get_argument('gp_id', 0)
        msg = self.db.query('select id, title from wx_app_msg where deleted = 0 and sp_id = %s',
                            self.current_user.supplier_id)

        msg_gp = self.db.get('select * from wx_app_msg_gp where id = %s', gp_id)
        msg_list = []

        for msg_id in msg_gp.app_msgs.split(','):
            for msg_content in msg:
                if int(msg_id) == msg_content.id:
                    msg_list.append(msg_content)

        params = {
            'action': 'edit',
            'msg': msg,
            'msg_gp': msg_gp,
            'msg_list': msg_list,
            'msg_group': msg_gp.app_msgs
        }

        self.render('wx/app_msg/group.html', **params)

    @require()
    def post(self):
        gp_id = self.get_argument('msg_gp', 0)
        app_msgs = self.get_argument('msg_group', '')
        app_msgs = app_msgs[:len(app_msgs) - 1]
        name = self.get_argument('name', '')

        self.db.execute('update wx_app_msg_gp set name = %s, app_msgs = %s, created_at = NOW() '
                        'where id = %s and sp_id=%s ', name, app_msgs, gp_id, self.current_user.supplier_id)

        self.redirect(self.reverse_url('weixin.app_msg.group'))


class Delete(BaseHandler):
    @require()
    def post(self):
        msg_gp_id = self.get_argument('id', 0)

        self.db.execute('update wx_app_msg_gp set deleted = 1 where id = %s and sp_id=%s',
                        msg_gp_id, self.current_user.supplier_id)

        self.redirect(self.reverse_url('weixin.app_msg.group'))


class Detail(BaseHandler):
    @require()
    def get(self):
        gp_id = self.get_argument('gp_id', 0)
        group = self.db.get('select * from wx_app_msg_gp where id = %s', gp_id)

        msg_list = map(int, group.app_msgs.split(','))

        msg_sort_set = []
        msg_set = self.db.query('select * from wx_app_msg where id in (%s)' % ','.join(['%s'] * len(msg_list)), *msg_list)

        for msg_id in msg_list:
            for msg_content in msg_set:
                if msg_id == msg_content.id:
                    msg_content.cover = img_url(msg_content.cover)
                    msg_sort_set.append(msg_content)
                    break

        self.render('wx/app_msg/group_detail.html', msg_sort_set=msg_sort_set)