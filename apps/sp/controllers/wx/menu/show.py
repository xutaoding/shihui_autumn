# -*- coding: utf-8 -*-

from ... import BaseHandler, require
import tornado.web


class Show(BaseHandler):
    @require()
    @tornado.web.authenticated
    def get(self):
        main_menu = self.db.query('select * from wx_menu where sp_id = %s and parent_id is null order by id ',
                                  self.current_user.supplier_id)
        #自定义菜单的一级菜单最少为2个，否则转到编辑页面
        if len(main_menu) == 0:
            self.render('wx/menu/preview.html', bingo=0)
            return
        elif len(main_menu) < 2:
            self.render('wx/menu/preview.html', bingo=1)
            return
        else:
            pass

        sub_menu = self.db.query('select * from wx_menu where sp_id = %s and parent_id is not null order by id ',
                                 self.current_user.supplier_id)

        pictures = self.db.query('select * from wx_app_msg where deleted = 0 and sp_id = %s',
                                 self.current_user.supplier_id)
        picture_groups = self.db.query('select * from wx_app_msg_gp where deleted = 0 and sp_id = %s',
                                       self.current_user.supplier_id)

        action_type = {
            1: '官网',
            2: '自定义URL',
            3: '图文信息',
            4: '图文信息组',
            5: '文字信息',
            6: '会员'
        }

        params = {
            'bingo': 2,
            'main_menu': main_menu,
            'sub_menu': sub_menu,
            'pictures': pictures,
            'picture_groups': picture_groups,
            'action_type': action_type
        }

        self.render('wx/menu/preview.html', **params)
