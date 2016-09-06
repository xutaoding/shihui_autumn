# -*- coding: utf-8 -*-

import json
from ... import BaseHandler
from ... import require
from autumn.utils import PropDict, json_dumps, json_hook
from autumn.goods import img_url


class MemCover(BaseHandler):
    """微会员入口首页"""
    @require()
    def get(self):
        user = self.current_user
        if 'wx_mem_cover' in user.sp_props:
            cover = json.loads(user.sp_props.wx_mem_cover, object_hook=json_hook)
            self.render('wx/member/cover.html', cover=cover, img_url=img_url)
        else:
            self.redirect(self.reverse_url('wx.mem_cover.edit'))


class MemCoverEdit(BaseHandler):
    """会员卡入口编辑"""
    @require()
    def get(self):
        user = self.current_user
        if 'wx_mem_cover' in user.sp_props:
            cover = json.loads(user.sp_props.wx_mem_cover, object_hook=json_hook)
        else:
            cover = PropDict()
        self.render('wx/member/cover_edit.html', cover=cover, img_url=img_url)

    @require()
    def post(self):
        sp_id = self.current_user.supplier_id
        self.db.execute('delete from supplier_property where sp_id=%s and name="wx_mem_cover"', sp_id)
        self.db.execute('insert into supplier_property(sp_id, name, value) values (%s, "wx_mem_cover", %s)',
                        sp_id, json_dumps({'pic': self.get_argument('pic'),
                                           'title': self.get_argument('title'),
                                           'desc': self.get_argument('desc')}))
        self.redirect(self.reverse_url('wx.mem_cover'))


default_block = [
    PropDict({'icon': '&#xf00b0;', 'name': '会员特权', 'group': 1, 'display_order': 1, 'link_type': 1,
              'deleted': '0',  'key': 'tq', 'value': ''}),
    PropDict({'icon': '&#xf0104;', 'name': '会员广播', 'group': 1, 'display_order': 2, 'link_type': 0,
              'deleted': '0',  'key': 'gb', 'value': '/member/msg'}),
    PropDict({'icon': '&#xf012d;', 'name': '完善会员资料', 'group': 2, 'display_order': 9, 'link_type': 0,
              'deleted': '0',  'key': 'zl', 'value': '/member/info'}),
    PropDict({'icon': '&#xf01f7;', 'name': '适用门店', 'group': 2, 'display_order': 10, 'link_type': 0,
              'deleted': '0',  'key': 'md', 'value': '/shops'})
]

# 自定义模块，用于前台添加，以后可以继续扩展
extend_block_name = [
    {'link_type': 0, 'value': '/member/sign', 'pos': '1', 'name': '积分签到', 'key': 'jf'},
    {'link_type': 0, 'value': '/', 'pos': '2', 'name': '微官网', 'key': 'gw'},
    {'link_type': 0, 'value': '/book', 'pos': '3', 'name': '微预约', 'key': 'yy'},
    {'link_type': 0, 'value': '/comment', 'pos': '4', 'name': '微评论', 'key': 'pl'},
    {'link_type': 0, 'value': '/mall/goods', 'pos': '5', 'name': '微商城', 'key': 'sc'},
    {'link_type': 0, 'value': '/activity/list', 'pos': '6', 'name': '微活动', 'key': 'hd'}
]

# 所有模块的说明
desc = {
    'tq': '会员卡当前所拥有的权限做文字说明',
    'gb': '会员消息群发功能',
    'zl': '用户完善资料时供用户填写',
    'md': '所有门店信息展示，包括电话，地址。支持一键拨号，手机地图导航',
    'dj': '设置会员等级及对应特权',
    'jf': '设置积分规则',
    'gw': '官网主页链接',
    'yy': '门店或服务预约功能，请先在预约管理中设置',
    'pl': '用户评论模块',
    'sc': '微信商城模块链接',
    'hd': '微信会员活动模块链接, 具体的活动详情可以去“微活动”设置',
}


class MemBlock(BaseHandler):
    """会员模块"""
    @require()
    def get(self):
        user = self.current_user
        blocks = self.db.query('select * from wx_mem_block where sp_id=%s and deleted=0 order by display_order asc',
                               user.supplier_id)
        # 还没设置模块，跳转到编辑页面
        if not blocks:
            self.render('wx/member/block_edit.html', added_blocks=default_block, desc=json_dumps(desc), blocks=json_dumps(blocks),
                        extend_block_name=json_dumps(extend_block_name), json_loads=json.loads)
        # 设置过模块，跳转到预览页面
        else:
            first = []
            second = []
            for b in blocks:
                if b.group == 1:
                    first.append(b)
                else:
                    second.append(b)
            self.render('wx/member/block.html', first=first, second=second)


class MemBlockEdit(BaseHandler):
    """编辑会员模块"""
    @require()
    def get(self):
        sp_id = self.current_user.supplier_id
        # 获得所有模块
        added_blocks = self.db.query('select * from wx_mem_block where sp_id=%s and deleted=0', sp_id)
        # 获得自定义模块的name，用来除重
        blocks = [b.name for b in added_blocks if b.is_default != '1']
        self.render('wx/member/block_edit.html', added_blocks=added_blocks, desc=json_dumps(desc), blocks=json_dumps(blocks),
                    extend_block_name=json_dumps(extend_block_name), json_loads=json.loads)

    @require()
    def post(self):
        sp_id = self.current_user.supplier_id
        params = []
        length = 0
        u = lambda k: k.encode('utf-8')
        # 获取默认模块值
        for b in default_block:
            length += 1
            key = b.key
            temp = ['1', key]
            temp.extend(map(u, map(self.get_argument, (key+'-icon', key+'-name', key+'-group', key+'-display_order',
                        key+'-link_type', key+'-value'))))
            params.extend(temp)
        # 获取自定义模块值
        for b in extend_block_name:
            key = b['key']
            if self.get_argument(key+'-icon', ''):
                temp = ['0', key]
                temp.extend(map(u, map(self.get_argument, [key+'-icon', key+'-name', key+'-group', key+'-display_order',
                                                           key+'-link_type', key+'-value'], ['']*6)))
                length += 1
                params.extend(temp)

        # 删除已经存在的
        self.db.execute('delete from wx_mem_block where sp_id=%s', sp_id)
        #插入新数据
        values = ','.join(['('+str(sp_id)+',0,%s,%s,%s,%s,%s,%s,%s,%s)']*length)
        self.db.execute('insert into wx_mem_block (sp_id, deleted, is_default, `key`, icon, `name`, `group`, '
                        'display_order, link_type, value) values %s' % values, *params)
        self.redirect(self.reverse_url('wx.mem_block'))

