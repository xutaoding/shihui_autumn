# -*- coding: utf-8 -*-

from ... import BaseHandler
from ... import require
import logging
import random
import string
from autumn.torn.paginator import Paginator
from autumn.utils import PropDict, json_dumps, mix_str
from voluptuous import Schema, All, Coerce, Length, Any, Range
from autumn.torn.form import Form, EmptyList, Decode, Datetime, EmptyNone, Unique, ListCoerce
from autumn.utils.dt import ceiling
import json
from autumn.goods import img_url
from autumn.utils import json_hook

act_dict = PropDict({
    1: "刮刮乐",
    2: "大转盘"
})


class List(BaseHandler):
    """微活动列表"""
    @require()
    def get(self):
        acts = self.db.query('select * from wx_activity where sp_id = %s and deleted=0 order by id desc',
                             self.current_user.supplier_id)
        self.render('wx/activity/list.html', acts=acts, act_dict=act_dict)


class Add(BaseHandler):
    """新增微活动"""
    @require()
    def get(self):
        form = Form(self.request.arguments, add_schema)
        self.render('wx/activity/edit.html', form=form, error='', action='add', rewards=[],
                    act_id='', json_dumps=json_dumps)

    @require()
    def post(self):
        form = Form(self.request.arguments, add_schema)
        if not form.validate():
            logging.error(form.errors)
            self.render('wx/activity/edit.html', form=form, error='参数不正确', action='add')
            return

        # 添加新的微活动
        fields = ('type', 'name', 'start_at', 'expire_at', 'detail', 'win_desc', 'lose_desc', 'due_desc', 'max_try',
                  'daily_try', 'rewards_possibility')
        sql = """insert into wx_activity (%s,  sp_id, created_at, deleted) values  (%s, %%s, NOW(), 0)"""\
              % (','.join(fields), ','.join(['%s']*len(fields)))

        form.expire_at['value'] = ceiling(form.expire_at.value, today=True) if form.expire_at.value else None
        params = [form.arguments[field]['value'] for field in fields]
        params.extend([self.current_user.supplier_id])
        activity_id = self.db.execute(sql, *params)

        # 添加相关的奖品信息
        r_types = self.get_arguments('rewards_type')
        r_names = self.get_arguments('rewards_name')
        r_nums = [int(i) for i in self.get_arguments('rewards_num')]
        for i in range(len(r_types)):
            rewards_id = self.db.execute('insert into wx_activity_rewards (act_id, type, name, num) values '
                                         '(%s, %s, %s, %s)', activity_id, r_types[i], r_names[i], r_nums[i])
            # 产生兑奖SN码
            generate_sn(self.db, rewards_id, r_nums[i])

        self.redirect(self.reverse_url('wx.activity.list'))


class Edit(BaseHandler):
    """微活动编辑"""
    def get(self):
        act_id = self.get_argument('act_id', -1)
        activity = self.db.get('select * from wx_activity where deleted=0 and id=%s', act_id)
        if not activity:
            self.redirect(self.reverse_url('wx.activity.list'))
            return
        rewards = self.db.query('select * from wx_activity_rewards where act_id=%s', act_id)
        form = Form(activity, add_schema)
        self.render('wx/activity/edit.html', form=form, rewards=rewards, error='',
                    action='edit', json_dumps=json_dumps, act_id=act_id)

    def post(self):
        form = Form(self.request.arguments, add_schema)
        if not form.validate():
            logging.error(form.errors)
            self.render('wx/activity/edit.html', form=form, error='参数不正确', action='add')
            return
        act_id = self.get_argument('act_id')
        # 更新微活动
        fields = ('type', 'name', 'start_at', 'expire_at', 'detail', 'win_desc', 'lose_desc', 'due_desc', 'max_try',
                  'daily_try', 'rewards_possibility')
        sql = """update wx_activity set %s where id=%%s""" \
              % ','.join([field + '=%s' for field in fields])
        params = [form.arguments[field]['value'] for field in fields]
        params.extend([act_id])
        self.db.execute(sql, *params)

        # 更新奖品设置
        r_ids = self.get_arguments('rewards_id')
        r_prev_num = self.get_arguments('rewards_prev_num')
        r_types = self.get_arguments('rewards_type')
        r_names = self.get_arguments('rewards_name')
        r_nums = self.get_arguments('rewards_num')
        prev_len = len(r_ids)  # 记录原来的奖品条数
        for i in range(len(r_types)):
            if i < prev_len:
                # 更新原来的奖品设置
                self.db.execute('update wx_activity_rewards set type=%s, name=%s, num=%s where id=%s',
                                r_types[i], r_names[i], r_nums[i], r_ids[i])
                # 如果奖品数量增加，生成新的SN码
                diff_num = int(r_nums[i]) - int(r_prev_num[i])
                if diff_num > 0:
                    generate_sn(self.db, r_ids[i], diff_num)
            else:
                # 插入新添加的奖品设置
                rewards_id = self.db.execute('insert into wx_activity_rewards (act_id, type, name, num) values '
                                             '(%s, %s, %s, %s)', act_id, r_types[i], r_names[i], r_nums[i])
                generate_sn(self.db, rewards_id, int(r_nums[i]))

        self.redirect(self.reverse_url('wx.activity.list'))


class Delete(BaseHandler):
    """删除微活动"""
    def post(self):
        act_id = self.get_argument('act_id', 0)
        self.db.execute('update wx_activity set deleted=1 where id=%s', act_id)
        self.redirect(self.reverse_url('wx.activity.list'))


class SetActive(BaseHandler):
    """开始微活动"""
    def post(self):
        operator = self.get_argument('operator', '-1')
        act_id = self.get_argument('act_id', '-1')

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        if operator not in ['0', '1']:
            self.write({'is_ok': False})
            return

        self.db.execute('update wx_activity set is_active=%s where id=%s',
                        operator, act_id)
        self.write({'is_ok': True})


class SnList(BaseHandler):
    """兑换码管理"""
    def get(self):
        form = Form(self.request.arguments, sn_schema)
        act_id = self.get_argument('act_id', 0)
        sql = 'select r.*, s.*, s.id sid, m.id mid, m.mobile from wx_activity_rewards r join wx_activity_sn s ' \
              'left join member m on s.mem_id=m.id where r.id=s.rewards_id ' \
              'and r.act_id=%s '
        params = [act_id]

        if form.sn.value:
            sql += ' and s.sn=%s '
            params.append(form.sn.value)
        if form.mobile.value:
            sql += ' and m.mobile=%s '
            params.append(form.mobile.value)
        if form.status.value:
            sql += ' and s.status=%s '
            params.append(form.status.value)
        if form.type.value:
            sql += ' and r.type like %s '
            params.append('%'+form.type.value+'%')
        if form.name.value:
            sql += ' and r.name like %s '
            params.append('%'+form.name.value+'%')

        page = Paginator(self, sql, params)
        self.render('wx/activity/sn_list.html', page=page, form=form, act_id=act_id)


class SnUse(BaseHandler):
    """使用SN请求"""
    def post(self):
        sid = self.get_argument('sid', '0')
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        # 检查SN 状态
        if not self.db.get('select * from wx_activity_sn where id=%s and status=2', sid):
            self.write({'ok': False, 'msg': '未发放 或 冻结 的SN不能使用'})
            return
        try:
            self.db.execute('update wx_activity_sn set status=3, used_at=NOW() where id=%s and status=2', sid)
            self.write({'ok': True})
            return
        except Exception as e:
            self.write({'ok': False, 'msg': '操作失败,请重试或联系视惠客服'})
            return


def generate_sn(db, rewards_id, num):
    """根据奖品产生SN码"""
    for i in range(num):
        while True:
            sn = ''.join([random.choice(string.digits) for z in range(16)])
            # 没有重复，停止
            if not db.get('select id from wx_activity_sn where sn=%s', sn):
                break
        db.execute('insert into wx_activity_sn set rewards_id=%s, sn=%s', rewards_id, sn)

sn_schema = Schema({
    'sn': str,
    'mobile': str,
    'type': str,
    'name': str,
    'status': str
}, extra=True)

add_schema = Schema({
    'type':             Any('1', '2'),
    'name':             All(Decode(), Length(min=1, max=60)),
    'start_at':         Datetime('%Y-%m-%d %H:%M:%S'),
    'expire_at':        Datetime('%Y-%m-%d %H:%M:%S'),
    'detail':           str,
    'win_desc':         str,
    'lose_desc':        str,
    'due_desc':         str,
    'max_try':          Coerce(int),
    'daily_try':        Coerce(int),
    'rewards_type':     All(Decode()),
    'rewards_name':     All(Decode()),
    'rewards_num':      All(Coerce(int), Range(min=1)),
    'rewards_possibility':     All(Coerce(int), Range(min=1, max=100)),
}, extra=True)


class Show(BaseHandler):
    @require()
    def get(self):
        cover = self.db.get('select * from supplier_property where name = "wx_activity_cover" and sp_id = %s',
                            self.current_user.supplier_id)
        if cover:
            cover = json.loads(cover.value, object_hook=json_hook)
        else:
            cover = PropDict()

        self.render('wx/activity/show.html', cover=cover, img_url=img_url)


class Cover(BaseHandler):
    @require()
    def get(self):
        cover = self.db.get('select * from supplier_property where name = "wx_activity_cover" and sp_id = %s',
                            self.current_user.supplier_id)
        if cover:
            cover = json.loads(cover.value, object_hook=json_hook)
        else:
            cover = PropDict()

        self.render('wx/activity/cover.html', cover=cover, img_url=img_url)

    @require()
    def post(self):
        sp_id = self.current_user.supplier_id
        self.db.execute('delete from supplier_property where sp_id=%s and name="wx_activity_cover"', sp_id)
        self.db.execute('insert into supplier_property(sp_id, name, value) values (%s, "wx_activity_cover", %s)',
                        sp_id, json_dumps({'pic': self.get_argument('pic'),
                                           'title': self.get_argument('title'),
                                           'desc': self.get_argument('desc')}))

        self.redirect(self.reverse_url('wx.activity.cover'))
