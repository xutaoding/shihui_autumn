# -*- coding: utf-8 -*-

import common
import logging
from autumn.api.weixin import Weixin, error_list
from datetime import datetime
from tornado.gen import coroutine
from tornado.ioloop import IOLoop


@coroutine
def main_loop():
    redis = common.redis_client()
    db = common.db_client()
    args = {
        'db': db,
        'body': ''
    }

    while common.running():
        sp_id = redis.brpop('q:wx:mem:update')[1]

        args['sp_id'] = sp_id
        app_id = db.get('select * from supplier_property where name="app_id" and sp_id = %s', sp_id)['value']
        app_secret = db.get('select * from supplier_property where name="app_secret" and sp_id = %s', sp_id)['value']

        wx = Weixin(method='user/get', **args)
        wx.set_app_info(app_id, app_secret)

        info = Weixin(method='user/info', **args)
        info.set_app_info(app_id, app_secret)

        next_openid = ''
        while True:
            result = yield wx(next_openid=next_openid)
            wx.parse_response(result.body)

            if wx.is_ok() and 'data' in wx.message.keys():
                count = wx.message.count
                total = wx.message.total
                customs = wx.message.data.openid
                for custom in customs:
                    response = yield info(openid=custom, lang='zh_CN')
                    info.parse_response(response.body)
                    if info.is_ok():
                        nickname = info.message.nickname

                        # 暂时数据库未升级至可以存储emoji字符，故使用以下代码，升级数据库后可删除
                        import re
                        try:
                            # UCS-4
                            highpoints = re.compile(u'[\U00010000-\U0010ffff]')
                        except re.error:
                            # UCS-2
                            highpoints = re.compile(u'[\uD800-\uDBFF][\uDC00-\uDFFF]')
                        nickname = highpoints.sub(u'', nickname)
                        # todo =========================未升级前的替代方案===================

                        sex = {0: '未知', 1: '男', 2: '女'}.get(info.message.sex)
                        follow_at = datetime.fromtimestamp(info.message.subscribe_time)
                        openid = info.message.openid
                        head_img = info.message.headimgurl

                        mid = db.query('select * from member where wx_id = %s and sp_id = %s',
                                       custom, sp_id)

                        if mid:
                            db.execute('update member set wx_name = %s, gender = %s,'
                                       'head_img = %s, wx_follow_at = %s, country = %s, province = %s, city = %s '
                                       'where wx_id = %s and sp_id = %s',
                                       nickname, sex, head_img, follow_at, info.message.country,
                                       info.message.province, info.message.city,
                                       custom, sp_id)
                        else:
                            cid = db.query('select * from member_category where sp_id = %s and name = "未分组" ',
                                           sp_id)[0].id
                            db.execute('insert into member set sp_id = %s, wx_id = %s, wx_name = %s, gender = %s,'
                                       'head_img = %s, wx_follow_at = %s, created_at = NOW(),'
                                       'category_id = %s, country = %s, province = %s, city = %s, '
                                       'source = "微信导入"',
                                       sp_id, openid, nickname, sex, head_img, follow_at, cid, info.message.country,
                                       info.message.province, info.message.city)
                        logging.info('会员 %s 更新信息成功', custom.encode('utf-8'))
                    else:
                        logging.error('获取 %s 信息失败。失败原因 %s', custom.encode('utf-8'), error_list.get(info.error_code, ''))

                if count < 10000 or count == total:
                    break
                else:
                    next_openid = wx.message.next_openid
            else:
                logging.error('获取关注者失败.商户 %s, 错误原因 %s', sp_id, error_list.get(wx.error_code, ''))
                break

if __name__ == '__main__':
    common.set_up()

IOLoop.instance().run_sync(main_loop)

