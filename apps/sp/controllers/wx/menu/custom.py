# -*- coding: utf-8 -*-

from ... import BaseHandler
import tornado.web
from ... import require
import tornado.gen
from autumn.api.weixin import Weixin
from autumn.utils import json_dumps
import logging
import json
import hashlib

type_list = {
    1: '固定的,如官网等',
    2: '类型为view的,如自定义url',
    3: '文字信息',
    4: '图文信息',
    5: '图文信息组',
    6: '预约信息'
}

action_type = {
    1: ['官网', 1],
    2: ['自定义URL', 2],
    3: ['图文信息', 4],
    4: ['图文信息组', 5],
    5: ['文字信息', 3],
    6: ['会员', 1],
    7: ['预订', 6],
    8: ['商城', 1],
    9: ['活动', 1]
}
action_type_wx_menu = {
    1: 'website',
    2: 'url',
    3: 'app_msg',
    4: 'app_msg_group',
    5: 'text',
    6: 'member',
    7: 'book',
    8: 'mall',
    9: 'activity'
}


class Custom(BaseHandler):
    @require()
    @tornado.web.authenticated
    def get(self):
        main_menu = self.db.query('select * from wx_menu where sp_id = %s and parent_id is null order by id ',
                                  self.current_user.supplier_id)
        sub_menu = self.db.query('select * from wx_menu where sp_id = %s and parent_id is not null order by id ',
                                 self.current_user.supplier_id)

        pictures = self.db.query('select * from wx_app_msg where sp_id = %s and deleted = 0', self.current_user.supplier_id)
        picture_groups = self.db.query('select * from wx_app_msg_gp where sp_id = %s and deleted = 0', self.current_user.supplier_id)
        appointments = self.db.query('select * from wx_booking_setting where sp_id = %s and deleted = 0', self.current_user.supplier_id)
        for appointment in appointments:
            appointment.info = json.loads(appointment.info)

        params = {
            'main_menu': main_menu,
            'sub_menu': sub_menu,
            'pictures': pictures,
            'picture_groups': picture_groups,
            'appointments': appointments,
            'action_type': action_type,
            'fix_list': ['1', '6', '8', '9']  # 所有type_list为1的action_type值
        }
        self.render('wx/menu/custom.html', **params)

    @require()
    @tornado.gen.coroutine
    def post(self):
        params = dict([(name, self.get_argument(name).encode('utf-8')) for name in self.request.arguments
                       if name.startswith('s_menu_item') or name.startswith('m_menu_title')])

        main_pos_list = []
        main_content_list = []
        menu_pos_list = []
        menu_content_list = []
        for name, content in params.iteritems():
            # 只有那些有值的父菜单才能有机会插进数据库
            # 循环找到正确的顺序位置，数据库能准确按顺序插入
            if name.startswith('m_menu_title') and content.split('--')[0]:
                name_list = name.split('--')
                main_temp = (name_list[1], content)
                if not main_pos_list:
                    main_pos_list.append(name_list[1])
                    main_content_list.append(main_temp)
                else:
                    is_insert = False
                    for index, number in enumerate(main_pos_list):
                        if name_list[1] < number:
                            main_pos_list.insert(index, name_list[1])
                            main_content_list.insert(index, main_temp)
                            is_insert = True
                            break
                    if not is_insert:
                        main_pos_list.append(name_list[1])
                        main_content_list.append(main_temp)

            elif name.startswith('s_menu_item'):
                # 如果二级菜单名为空，则取消增加该行
                is_name = content.split('--')[0]
                if not is_name.strip():
                    continue

                menu_list = name.split('--')
                position = int(menu_list[1]) * 10 + int(menu_list[2])
                content_temp = (menu_list[1], content)
                if not menu_pos_list:
                    menu_pos_list.append(position)
                    menu_content_list.append(content_temp)
                else:
                    is_insert = False
                    for index, number in enumerate(menu_pos_list):
                        if position < number:
                            menu_pos_list.insert(index, position)
                            menu_content_list.insert(index, content_temp)
                            is_insert = True
                            break
                    if not is_insert:
                        menu_pos_list.append(position)
                        menu_content_list.append(content_temp)
            else:
                pass

        # 以下代码用做后端检验数据的正确性
        # is_true = False
        # for item in menu_content_list:
        #
        #     pass
        # if not is_true:
        #     self.redirect(self.reverse_url('menu'))

        sp_id = self.current_user.supplier_id
        self.db.execute('delete from wx_menu where sp_id = %s and parent_id is not null', sp_id)
        self.db.execute('delete from wx_menu where sp_id = %s ', sp_id)

        menu_data = {'button': []}
        for main_item in main_content_list:
            print main_content_list
            m_list = main_item[1].split('--')
            if len(m_list) == 3:
                if m_list[1] == '5':
                    md5_content = hashlib.md5(m_list[2]).hexdigest()
                    m_list[2] = md5_content[:12] + m_list[2]
                self.db.execute('insert into wx_menu(sp_id, name, action_type, action) values(%s, %s, %s, %s)',
                                sp_id, m_list[0], m_list[1], m_list[2])

                if m_list[1] == '2':
                    # view
                    m_button = {
                        'type': 'view',
                        'name': m_list[0],
                        'url': m_list[2]
                    }
                elif m_list[1] == '5':
                    m_button = {
                        'type': 'click',
                        'name': m_list[0],
                        'key': action_type_wx_menu[int(m_list[1])] + ':' + md5_content[:12]
                    }
                else:
                    # click
                    m_button = {
                        'type': 'click',
                        'name': m_list[0],
                        'key': action_type_wx_menu[int(m_list[1])] + ':' + m_list[2]
                    }

                menu_data['button'].append(m_button)

            elif len(m_list) == 1:
                pid = self.db.execute('insert into wx_menu(sp_id, name) values(%s, %s)', sp_id, m_list[0])
                sub_buttons = []
                menu_data['button'].append({'name': m_list[0], 'sub_button': sub_buttons})
                for menu_item in menu_content_list:
                    if menu_item[0] == main_item[0]:
                        me_list = menu_item[1].split('--')
                        if me_list[1] == '5':
                            md5_content = hashlib.md5(me_list[2]).hexdigest()
                            me_list[2] = md5_content[:12] + me_list[2]

                        self.db.execute('insert into wx_menu(sp_id, name, action_type, action, parent_id) '
                                        'values(%s, %s, %s, %s, %s)', sp_id, me_list[0], me_list[1], me_list[2], pid)

                        if me_list[1] == '5':
                            sub_button = {
                                'type': 'click',
                                'name': me_list[0],
                                'key': action_type_wx_menu[int(me_list[1])] + ':' + md5_content[:12]
                            }
                        elif me_list[1] != '2':
                            # click
                            sub_button = {
                                'type': 'click',
                                'name': me_list[0],
                                'key': action_type_wx_menu[int(me_list[1])] + ':' + me_list[2]
                            }
                        else:
                            # view
                            sub_button = {
                                'type': 'view',
                                'name': me_list[0],
                                'url': me_list[2]
                            }

                        sub_buttons.append(sub_button)
            else:
                pass

        # 如果一级菜单不是直接点击，且它没有对应的二级菜单，则删除
        main_menu = self.db.query('select id from wx_menu where sp_id = %s and parent_id is null '
                                  'and (action_type = " " or action_type is null)', sp_id)
        for item in main_menu:
            if not self.db.query('select id from wx_menu where sp_id = %s and parent_id = %s', sp_id, item.id):
                self.db.execute('delete from wx_menu where id = %s and sp_id = %s', item.id, sp_id)

        #如果类型为图文信息或者图文信息组的时候，且图文信息没有值就删除
        check_type = [3, 4, 7]
        self.db.execute('delete from wx_menu where sp_id = %%s and action_type in (%s) and action = "null"' %
                        ','.join(['%s'] * len(check_type)), sp_id, *check_type)
        wx = Weixin(db=self.db, sp_id=sp_id, method="menu/create", body=json_dumps(menu_data))
        app_id = self.current_user.sp_props.app_id
        app_secret = self.current_user.sp_props.app_secret
        wx.set_app_info(app_id, app_secret)
        result = yield wx()
        wx.parse_response(result.body)

        logging.info(json_dumps(menu_data))
        if wx.is_ok():
            logging.info('push menu to weixin sucessfully: %s', wx.message)
        else:
            logging.error('push menu to weixin fail: %s', wx.message)
        self.redirect(self.reverse_url('weixin.menu.show'))

