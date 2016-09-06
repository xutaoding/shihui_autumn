# -*- coding: utf-8 -*-

from ... import BaseHandler
from ... import require
from datetime import datetime, timedelta
from tornado.web import HTTPError
from autumn.torn.paginator import Paginator
from autumn.torn.form import Form
from autumn.utils import json_dumps, PropDict
from voluptuous import Schema
from autumn.api.weixin import Weixin
from tornado.gen import coroutine
from autumn.utils import json_hook
import json
import logging
from datetime import date, timedelta

list_schema = Schema({
    'mobile': str,
    'keyword': str,
    'gender': str,
    'level': str,
    'cate': str,
    'id': str,
    'area': str,
}, extra=True)

level_schema = Schema({
    'point': str,
    'level': str,
    'attention': str
}, extra=True)


class List(BaseHandler):
    """会员列表"""
    @require()
    def get(self):
        form = Form(self.request.arguments, list_schema)
        sp_id = self.current_user.supplier_id
        params = [sp_id]
        # 获取商户的用户分组
        cates = self.db.query('select id, name from member_category where sp_id=%s and deleted=0', sp_id)
        levels = self.db.get('select value from supplier_property where sp_id=%s and name="wx_level" ', sp_id)
        verify = self.db.get('select * from supplier_property where sp_id = %s and name = "wx_verified" and value = "1"',
                             sp_id)
        if levels:
            levels = json.loads(levels.value, object_hook=json_hook)
        else:
            levels = {}

        sql = 'select m.id mid, m.name, m.gender, m.mobile, m.last_active, mc.name as cate, wx_follow_at, '\
              'mc.id cid, m.wx_from, m.source, m.wx_name, m.created_at, m.points, m.level, m.head_img ' \
              'from member m, member_category mc ' \
              'where mc.sp_id=m.sp_id and m.category_id = mc.id and mc.sp_id=%s'
        if form.keyword.value:
            sql += ' and (m.name like %s or m.wx_name like %s)  '
            params.append('%'+form.keyword.value+'%')
            params.append('%'+form.keyword.value+'%')
        if form.mobile.value:
            sql += ' and m.mobile=%s '
            params.append(form.mobile.value)
        if form.gender.value:
            sql += ' and m.gender=%s '
            params.append(form.gender.value)
        if form.cate.value:
            sql += ' and m.category_id=%s '
            params.append(form.cate.value)
        if form.id.value:
            sql += ' and m.id=%s '
            params.append(form.id.value)
        if form.level.value:
            sql += ' and m.level=%s '
            params.append(form.level.value)
        if form.area.value:
            provinces = (','.join(['"'+i+'"' for i in (','.join(form.area.value)).split(',')]))
            sql += ' and m.province in (' + provinces + ') '

        sql += ' order by m.last_active desc '
        page = Paginator(self, sql, params)
        self.render('wx/member/list.html', form=form, page=page, cates=cates, levels=levels, verify=verify)


class Detail(BaseHandler):
    """会员详情页面"""
    @require()
    def get(self, mem_id):
        sp_id = self.current_user.supplier_id
        mem = self.db.get('select * from member where sp_id=%s and id=%s', sp_id, mem_id)
        if not mem:
            self.redirect(self.reverse_url('member.list'))
            return
        # 查询消费订单记录
        page = PropDict({'rows': []})
        if mem.mobile:
            # todo 考虑不给商家看未消费的
            sql = """select i.*, ss.name sname, ds.name dname
            from item i, orders o, supplier_shop ss, distributor_shop ds
            where  o.mobile=%s and i.order_id=o.id and i.sp_shop_id=ss.id and i.distr_shop_id=ds.id and i.status=2
            order by i.used_at desc"""
            page = Paginator(self, sql, [mem.mobile])

        self.render('wx/member/detail.html', page=page, mem=mem)


class ChangeCategory(BaseHandler):
    """改变指定用户的分组"""
    @require('manager')
    @coroutine
    def post(self):
        sp_id = self.current_user.supplier_id
        cate_id = self.get_argument('cate_id', '')  # 新cate id
        mem_id = self.get_argument('mem_id', '')
        try:
            map(int, mem_id.split(','))
        except:
            raise HTTPError(500)
        # 更新微信服务器
        if self.current_user.sp_props.wx_type == 'service' and self.current_user.sp_props.wx_verified == '1':
            members = self.db.query('select wx_id from member where sp_id=%s and id in (' + mem_id + ')', sp_id)
            wx_cate_id = self.db.get('select wx_grp_id from member_category where id=%s', cate_id).wx_grp_id
            app_id = self.current_user.sp_props.app_id
            app_secret = self.current_user.sp_props.app_secret
            for mem in members:
                body = {"openid": mem.wx_id, "to_groupid": int(wx_cate_id)}
                wx = Weixin(db=self.db, sp_id=sp_id, method='groups/members/update', body=json_dumps(body))
                wx.set_app_info(app_id, app_secret)
                res = yield wx.fetch()
                wx.parse_response(res.body)
                if not wx.is_ok():
                    logging.error('wx error: %s' % wx.error)
        # 更新本地信息
        if mem_id and cate_id:
            sql = 'update member set category_id=%s where sp_id=%s and id in (' + mem_id + ')'
            self.db.execute(sql, cate_id, sp_id)


class AddCategory(BaseHandler):
    """添加用户分组"""
    @require('manager')
    @coroutine
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        sp_id = self.current_user.supplier_id
        cate_name = self.get_argument('name', '').encode('utf-8')
        # 检查是否重复
        exist = self.db.query('select * from member_category where sp_id=%s and name=%s and deleted=0', sp_id, cate_name)
        # 重复组名,返回
        if exist:
            self.write(json_dumps({'ok': False, 'error': '分组名称已经存在'}))
            return
        # 更新微信分组
        if self.current_user.sp_props.wx_type == 'service' and self.current_user.sp_props.wx_verified == '1':
            body = json_dumps({"group": {"name": cate_name}})
            wx = Weixin(db=self.db, sp_id=sp_id, method='groups/create', body=body)
            wx.set_app_info(self.current_user.sp_props.app_id, self.current_user.sp_props.app_secret)
            res = yield wx.fetch()
            wx.parse_response(res.body)
            if wx.is_ok():
                # 更新本地数据库
                last_id = self.db.execute('insert into member_category (sp_id, name, deleted, wx_grp_id) '
                                          'values (%s, %s, 0, %s)', sp_id, cate_name, wx.message.group.id)
                self.write(json_dumps({'ok': True, 'cate_id': last_id, 'cate_name': cate_name}))
            else:
                logging.error('wx error: %s' % wx.error)
                self.write(json_dumps({'ok': False, 'error': '添加失败，%s' % wx.error}))
        else:
            # 更新本地数据库
            last_id = self.db.execute('insert into member_category (sp_id, name, deleted) '
                                      'values (%s, %s, 0)', sp_id, cate_name)
            self.write(json_dumps({'ok': True, 'cate_id': last_id, 'cate_name': cate_name}))


class DeleteCategory(BaseHandler):
    """删除用户分组"""
    @require('manager')
    @coroutine
    def post(self):
        sp_id = self.current_user.supplier_id
        cate_id = self.get_argument('cate_id', '')
        # 查出默认的分组ID
        default_cate_id = self.db.get('select id from member_category where sp_id=%s and name="未分组"', sp_id).id
        # 微信服务器分组放到0
        if self.current_user.sp_props.wx_type == 'service' and self.current_user.sp_props.wx_verified == '1':
            members = self.db.query('select wx_id from member where sp_id=%s and category_id=%s', sp_id, cate_id)
            app_id = self.current_user.sp_props.app_id
            app_secret = self.current_user.sp_props.app_secret
            for mem in members:
                body = {"openid": mem.wx_id, "to_groupid": 0}
                wx = Weixin(db=self.db, sp_id=sp_id, method='groups/members/update', body=json_dumps(body))
                wx.set_app_info(app_id, app_secret)
                res = yield wx.fetch()
                wx.parse_response(res.body)
                if not wx.is_ok():
                    logging.error('wx error: %s' % wx.error)
        # 把要删除组的会员合并入默认分组
        self.db.execute('update member set category_id=%s where sp_id=%s and category_id=%s',
                        default_cate_id, sp_id, cate_id)
        # 删除分组
        self.db.execute('update member_category set deleted=1 where id=%s', cate_id)
        # 返回
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json_dumps({'ok': True}))


class ConsumeLevelList(BaseHandler):
    """按消费等级分类"""
    @require('manager')
    @coroutine
    def get(self):
        form = Form(self.request.arguments, level_schema)

        sp_id = self.current_user.supplier_id
        verify = self.db.get('select * from supplier_property where sp_id = %s and name = "wx_verified" and value = "1"',
                             sp_id)
        levels = self.db.get('select value from supplier_property where sp_id = %s and name="wx_level" ', sp_id)
        if levels:
            levels = json.loads(levels.value)
        else:
            levels = {}
        cates = self.db.query('select id, name from member_category where sp_id=%s and deleted=0', sp_id)

        sql = """select m.id mid, m.name, m.gender, m.mobile, m.last_active, mc.name as cate, wx_follow_at,
                 mc.id cid, m.wx_from, m.source, m.wx_name, m.created_at, m.points, m.level, m.head_img
                 from member m, member_category mc
                 where mc.sp_id=m.sp_id and m.category_id = mc.id and mc.sp_id=%s """
        params = [sp_id]

        if form.point.value and form.point.value != '0-0':
            points = form.point.value.split('-')
            min_point = points[0]
            max_point = points[1]
            sql += 'and m.points >= %s and m.points < %s '
            params.extend([min_point, max_point])

        if form.level.value:
            sql += 'and m.level = %s '
            params.append(form.level.value)

        if form.attention.value:
            today = date.today()

            if form.attention.value not in ['0', '7']:
                sql += 'and m.wx_follow_at > %s '
                if form.attention.value == '1':
                    params.append(today + timedelta(-7))
                elif form.attention.value == '2':
                    params.append(today + timedelta(-14))
                elif form.attention.value == '3':
                    params.append(today + timedelta(-30))
                elif form.attention.value == '4':
                    params.append(today + timedelta(-60))
                elif form.attention.value == '5':
                    params.append(today + timedelta(-90))
                elif form.attention.value == '6':
                    params.append(today + timedelta(-180))
                else:
                    pass
            else:
                if form.attention.value == '7':
                    sql += 'and m.wx_follow_at < %s '
                    params.append(today + timedelta(-180))

        page = Paginator(self, sql, params)

        args = {
            'page': page,
            'verify': verify,
            'cates': cates,
            'levels': levels,
            'form': form
        }
        self.render('wx/member/consume_level_list.html', **args)


action_schema = Schema({
    'shopping_count_1': str,
    'shopping_count_2': str,
    'avg_price_1': str,
    'avg_price_2': str,
    'last_shopping': str,
    'freq': str
}, extra=True)


class ConsumeActionList(BaseHandler):
    """按消费行为分类"""
    @require('manager')
    @coroutine
    def get(self):
        form = Form(self.request.arguments, action_schema)

        sp_id = self.current_user.supplier_id
        verify = self.db.get('select * from supplier_property where sp_id = %s and name = "wx_verified" and value = "1"',
                             sp_id)
        levels = self.db.get('select value from supplier_property where sp_id = %s and name="wx_level" ', sp_id)
        cates = self.db.query('select id, name from member_category where sp_id=%s and deleted=0', sp_id)
        if levels:
            levels = json.loads(levels.value)
        else:
            levels = {}
        params = [sp_id]
        sql = 'select m.id mid, m.name, m.gender, m.mobile, m.last_active, mc.name as cate, wx_follow_at, ' \
              'mc.id cid, m.wx_from, m.source, m.wx_name, m.created_at, m.points, m.level, m.head_img ' \
              'from member m join member_category mc left join (select mobile, sum(payment)/count(id) avg_price from ' \
              'orders group by mobile) o on m.mobile=o.mobile ' \
              'where mc.sp_id=m.sp_id and m.category_id = mc.id and mc.sp_id=%s '

        if form.shopping_count_1.value:
            sql += ' and m.shopping_count >= %s '
            params.append(form.shopping_count_1.value)
        if form.shopping_count_2.value:
            sql += ' and m.shopping_count <= %s '
            params.append(form.shopping_count_2.value)
        if form.avg_price_1.value:
            sql += ' and avg_price >= %s'
            params.append(form.avg_price_1.value)
        if form.avg_price_2.value:
            sql += ' and avg_price <= %s'
            params.append(form.avg_price_2.value)
        if form.last_shopping.value:
            if form.last_shopping.value == '7':
                sql += ' and m.last_shopping <= %s '
                last = datetime.now() - timedelta(days=7*26)
                params.append(last)
            else:
                sql += ' and m.last_shopping >= %s '
                last = datetime.now() - timedelta(days=7*int(form.last_shopping.value))
                params.append(last)

        page = Paginator(self, sql, params)
        self.render('wx/member/consume_action_list.html', verify=verify, form=form, page=page, levels=levels,
                    cates=cates)
