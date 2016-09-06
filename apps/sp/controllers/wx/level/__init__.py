# -*- coding: utf-8 -*-

from ... import BaseHandler, require
from autumn.utils import json_hook, json_dumps
import json


class Level(BaseHandler):
    @require()
    def get(self):
        members = self.db.query('select id, name, level, mobile from member where name is not null and sp_id = %s',
                                self.current_user.supplier_id)
        level_dict = self.db.get('select value from supplier_property where name = "wx_level" and sp_id = %s',
                                 self.current_user.supplier_id)

        level_dict = json.loads(level_dict.value, object_hook=json_hook) if level_dict else {}

        self.render('wx/level/show.html', members=members, level_dict=level_dict)

    @require()
    def post(self):
        mem_id = self.get_argument('mem_id', 0)
        level = self.get_argument('level', 1)
        self.set_header('Content-Type', 'application/json; charset=UTF-8')

        level_dict = self.db.get('select value from supplier_property where name = "wx_level" and sp_id = %s',
                                 self.current_user.supplier_id)

        level_dict = json.loads(level_dict.value, object_hook=json_hook) if level_dict else {}
        print level
        if level in level_dict.keys():
            name = level_dict[level]

            self.db.execute('update member set level = %s where id = %s and sp_id = %s',
                            level, mem_id, self.current_user.supplier_id)

            self.write({'ok': True, 'name': name})
        else:
            self.write({'ok': False})


class LevelSetting(BaseHandler):
    @require()
    def get(self):
        level_dict = self.db.get('select value from supplier_property where name = "wx_level" and sp_id = %s',
                                 self.current_user.supplier_id)

        level_dict = json.loads(level_dict.value, object_hook=json_hook) if level_dict else {}

        self.render('wx/level/setting.html', level_dict=level_dict)

    @require()
    def post(self):
        level = self.get_argument('dict')
        level_list = [obj for obj in level.split(',') if obj]
        level_dict = dict([(item.split('-')[0], item.split('-')[1]) for item in level_list])

        self.db.execute('delete from supplier_property where name = "wx_level" and sp_id = %s',
                        self.current_user.supplier_id)
        self.db.execute('insert into supplier_property(sp_id, name, value) values(%s, %s, %s)',
                        self.current_user.supplier_id, "wx_level", json_dumps(level_dict))

        self.redirect(self.reverse_url('wx.member.level'))