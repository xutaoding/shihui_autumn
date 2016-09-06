# -*- coding: utf-8 -*-
from tornado.web import url
from . import PageNotFoundHandler, Unauthorized
import comment
import member
import member.sign
import site
import page
import book
import pay
import mall
import oauth_access
import mall.order
import coupon
import activity


handlers = [
    url(r'/',                               site.Index,                         name='site.index'),
    url(r'/comment',                        comment.Comment,                    name='comment'),

    # 微信会员页面
    url(r'/member',                         member.UserInfo,                    name='member_index'),
    url(r'/member/join',                    member.Join,                        name='member_join'),
    url(r'/member/info',                    member.ChangeInfo,                  name='member_info'),
    url(r'/member/msg',                     member.ReadMeg,                     name='member_msg'),
    url(r'/member/send-vcode',              member.SendVCode,                   name='member_vcode'),
    url(r'/member/sign',                    member.sign.Sign,                   name='member.sign'),

    # 页面
    url(r'/app_msg/(\d+)',                  page.Detail,                        name='app_msg.detail'),
    url(r'/shops',                          member.Shops,                       name='member_shops'),

    # 预约
    url(r'/book',                           book.List,                          name='book_list'),
    url(r'/book/(\d+)',                     book.Info,                          name='book'),
    url(r'/book/orders',                    book.Orders,                        name='book.orders'),
    url(r'/book/orders/cancel',             book.Cancel,                        name='book.orders.cancel'),

    # 付款
    url(r'/pay',                            pay.Pay,                            name='pay'),

    # 获取wx_id
    url(r'/oauth',                          oauth_access.Oauth,                 name='oauth'),

    # 商城
    url(r'/mall/goods',                     mall.List,                          name='mall.goods'),
    url(r'/mall/goods/(\d+)',               mall.GoodsDetail,                   name='mall.goods_detail'),
    url(r'/mall/order-info',                mall.OrderInfo,                     name='mall.order_info'),
    url(r'/mall/pay',                       mall.OrderPay,                      name='mall.pay'),
    url(r'/mall/pay/fail',                  mall.Failed,                        name='mall.pay.fail'),

    #订单
    url(r'/order',                          mall.order.List,                    name='order'),
    url(r'/order/detail',                   mall.order.Detail,                  name='order.detail'),

    #券
    url(r'/coupon',                         coupon.List,                        name='coupon'),
    url(r'/coupon/detail',                  coupon.Detail,                      name='coupon.detail'),

    # 活动
    url(r'/activity/(\d+)',                 activity.Show,                      name='activity'),
    url(r'/activity/list',                  activity.List,                      name='activity.list'),
    url(r'/activity/result/(\d+)',          activity.Result,                    name='activity.result'),
    url(r'/activity/check/(\d+)',           activity.Check,                     name='activity.check'),
    url(r'/activity/sn_list',               activity.SnList,                    name='activity.sn_list'),

    # 404
    url(r'/unauthorized',                   Unauthorized,                       name='unauthorized'),
    url(r'.*',                              PageNotFoundHandler,                name='not_found')
]