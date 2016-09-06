# -*- coding: utf-8 -*-
from .. import BaseHandler
from tornado.httputil import url_concat
from tornado.web import HTTPError
from autumn.torn.paginator import Paginator
from autumn.utils import PropDict, json_dumps
from random import shuffle, randint
from tornado.web import authenticated


class List(BaseHandler):
    """所有微活动列表"""
    @authenticated
    def get(self):
        user = self.current_user
        sql = 'select * from wx_activity where sp_id=%s and is_active=1 and start_at < NOW() and expire_at > NOW()' \
              ' and deleted=0'

        page = Paginator(self, sql, [user.sp_id], page_size=5)
        self.render('activity/list.html', page=page)
        pass


class Show(BaseHandler):
    """微活动页面"""
    @authenticated
    def get(self, act_id):
        user = self.current_user
        if user.level == 0:
            # 不是会员，先跳转到加入会员页面
            self.redirect(url_concat(self.reverse_url('member_join'), {'wx_id': user.wx_id}))
        else:
            activity = self.db.get('select * from wx_activity where id=%s and sp_id=%s and deleted=0 and is_active=1 '
                                   'and start_at < NOW() and expire_at > NOW() ',
                                   act_id, user.sp_id)
            if not activity:
                raise HTTPError(404)
            else:
                act_mem = self.db.get('select * from wx_activity_mem where act_id = %s and mem_id = %s',
                                      act_id, user.id)
                act_pass = False if act_mem and (act_mem.today_count >= activity.daily_try or act_mem.count >= activity.max_try) else True
                day_remain_num = activity.daily_try if not act_mem else activity.daily_try - act_mem.today_count
                all_remain_num = activity.max_try if not act_mem else activity.max_try - act_mem.count
                if day_remain_num > all_remain_num:
                    day_remain_num = all_remain_num

                rewards = self.db.query('select id, type, name from wx_activity_rewards where act_id=%s '
                                        'order by id asc', act_id)
                if activity.type == 1:
                    self.render('activity/scratch_off.html', act_pass=act_pass, activity=activity, rewards=rewards,
                                day_remain_num=day_remain_num, all_remain_num=all_remain_num)
                elif activity.type == 2:
                    win_rewards = [r for r in rewards]  # 用来记录奖项
                    rewards_num = len(rewards)
                    # 补起12个转盘格子
                    rewards.extend([PropDict({'type': '未中奖', 'id': -1}) for i in range(12-rewards_num)])
                    # 打乱顺序
                    shuffle(rewards)
                    # 添加转盘角度
                    default_degree = 17
                    for i in range(len(rewards)):
                        rewards[i].update({'deg': default_degree+i*30})

                    self.render('activity/wheel.html', activity=activity, win_rewards=win_rewards, rewards=rewards,
                                act_id=act_id, json_dumps=json_dumps, day_remain_num=day_remain_num,
                                all_remain_num=all_remain_num)


class Result(BaseHandler):
    """抽奖请求"""
    @authenticated
    def post(self, act_id):
        self.set_header('Content-Type', 'application/json;charset=UTF-8')
        user = self.current_user

        act = self.db.get('select * from wx_activity where sp_id = %s and id = %s and deleted = 0',
                          user.sp_id, act_id)
        act_mem = self.db.get('select * from wx_activity_mem where mem_id = %s and act_id = %s',
                              user.id, act_id)
        if act_mem:
            self.db.execute('update wx_activity_mem set today_count = today_count + 1, count = count + 1 '
                            'where act_id = %s and mem_id = %s', act_id, user.id)
        else:
            self.db.execute('insert into wx_activity_mem(act_id, mem_id, today_count, count) values(%s, %s, 1, 1)',
                            act_id, user.id)
        # （潜规则）该活动已经中奖的，不可以再中奖
        is_rewarded = self.db.query('select * from wx_activity_rewards r, wx_activity_sn s where r.id=s.rewards_id '
                                    'and r.act_id=%s and mem_id=%s', act_id, user.id)
        if is_rewarded:
            self.write({'result': False, 'reward': '未中奖'})
            return

        reward_result = reward(self.db, user, act)
        if reward_result['result']:
            self.write({'result': True, 'reward': reward_result['reward'].type, 'name': reward_result['reward'].name})
        else:
            self.write({'result': False, 'reward': '未中奖'})


class Check(BaseHandler):
    """检测用户是否可以参加该活动"""
    @authenticated
    def post(self, act_id):
        self.set_header('Content-Type', 'application/json;charset=UTF-8')
        user = self.current_user
        activity = self.db.get('select * from wx_activity where id=%s and sp_id=%s and deleted=0',
                               act_id, user.sp_id)
        act_mem = self.db.get('select * from wx_activity_mem where act_id = %s and mem_id = %s',
                              act_id, user.id)
        valid = False if act_mem and (act_mem.today_count >= activity.daily_try or act_mem.count >= activity.max_try) \
            else True
        self.write({'pass': valid})


class SnList(BaseHandler):
    """微活动SN列表"""
    @authenticated
    def get(self):
        user = self.current_user
        list_type = self.get_argument('type', 'unused')
        sql = 'select * from wx_activity_rewards r, wx_activity_sn s where r.id=s.rewards_id and s.mem_id=%s '
        if list_type == 'unused':
            sql += ' and s.status = 2 '
        else:
            sql += ' and s.status = 3 '
        rewards = Paginator(self, sql, [user.id], page_size=10)
        self.render('activity/sn_list.html', rewards=rewards, type=list_type)


def reward(db, user, act):
    """活动中奖判断"""
    if randint(0, 100) < act.rewards_possibility:
        test_reward = db.get('select was.*, war.type, war.name from wx_activity_sn was, wx_activity_rewards war '
                             'where was.rewards_id = war.id and was.win_at is null and war.act_id = %s '
                             'ORDER BY RAND() LIMIT 0,1;', act.id)
        if test_reward:
            db.execute('update wx_activity_sn set win_at = NOW(), mem_id = %s, status=2 where id = %s',
                       user.id, test_reward.id)
            return {'result': True, 'reward': test_reward}
        else:
            return {'result': False}
    else:
        return {'result': False}
