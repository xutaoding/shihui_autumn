# -*- coding: utf-8 -*-
from tornado.web import url
import auth
import auth.password
import coupon.verify
import finance.sequence
import finance.withdraw
import real.order_shipping
import real.return_manage
import shop
import shop.shop
import shop.accounts
import wx.member.show
import report
import report.stats
import message.message
import ktv.manage
import ktv.price
import ktv.order
import goods.goods
import common
import wx.menu.custom
import wx.menu.show
import wx.app_msg.app_msg
import wx.site
import wx.member.mem_msg
import wx.app_msg.group
import wx.msg
import wx.keyword
import wx.setting
import wx.comment
import wx.book
import wx.book.order
import wx.level
import wx.subscribe
import wx.member.attention
import wx.mall
import wx.activity
import welcome
import wx.send_all

handlers = [
    url(r'/',                               auth.Login,                         name='index'),
    url(r'/login',                          auth.Login,                         name='login'),
    url(r'/logout',                         auth.Logout,                        name='logout'),
    url(r'/older-ie',                       welcome.OlderIE,                    name='older_ie'),

    #密码修改
    url(r'/password',                       auth.password.Password,             name='password'),
    #电子券
    url(r'/coupon/verify',                  coupon.verify.Verify,               name='coupon.verify'),
    url(r'/coupon/show',                    coupon.verify.ShowList,             name='coupon.show_list'),

    # 商品
    url(r'/goods',                          goods.goods.List,                   name='goods.list'),
    url(r'/goods/(\d+)',                    goods.goods.GoodsDetail,            name='goods.detail'),
    url(r'/goods/add',                      goods.goods.Add,                    name='goods.add'),
    url(r'/goods/edit',                     goods.goods.Edit,                   name='goods.edit'),
    url(r'/goods/delete',                   goods.goods.Delete,                 name='goods.delete'),
    url(r'/goods/approve',                  goods.goods.Apply,                  name='goods.apply'),

    #财务
    url(r'/sequence',                       finance.sequence.List,              name='finance.sequence'),
    url(r'/withdraw',                       finance.withdraw.List,              name='finance.withdraw'),
    url(r'/withdraw/preview',               finance.withdraw.Preview,           name='finance.withdraw.preview'),
    url(r'/withdraw/apply',                 finance.withdraw.Apply,             name='finance.withdraw.apply'),
    url(r'/withdraw/detail',                finance.withdraw.Detail,            name='finance.withdraw.detail'),
    url(r'/withdraw/query-amount',          finance.withdraw.QueryAmount,       name='finance.withdraw.query'),

    #实物
    url(r'/shipping/show',                  real.order_shipping.ShowShipping,   name='real.show_shipping'),
    url(r'/shipping/download',              real.order_shipping.DownloadShipping,   name='real.download_shipping'),
    url(r'/shipping/import',                real.order_shipping.ImportShipping, name='real.import_shipping'),
    url(r'/shipping/create',                real.order_shipping.CreateShipping, name='real.create_shipping'),
    url(r'/shipping/return',                real.return_manage.ReturnManage,    name='real.return_manage'),

    #门店管理
    url(r'/shop/show',                      shop.Show,                          name='shop.show'),
    url(r'/shop/add',                       shop.shop.Add,                      name='shop.add'),
    url(r'/shop/edit/(\d+)',                shop.shop.Edit,                     name='shop.edit'),
    url(r'/shop/delete',                    shop.shop.Delete,                   name='shop.delete'),
    url(r'/shop/district-ajax',             shop.shop.DistrictAjax,             name='shop.district_ajax'),
    url(r'/shop/area-ajax',                 shop.shop.AreaAjax,                 name='shop.area_ajax'),

    url(r'/accounts/show',                  shop.accounts.Show,                 name='accounts.show'),
    url(r'/accounts/add',                   shop.accounts.Add,                  name='accounts.add'),
    url(r'/accounts/edit/(\d+)',            shop.accounts.Edit,                 name='accounts.edit'),
    url(r'/accounts/delete/',               shop.accounts.Delete,               name='accounts.delete'),

    #会员管理
    url(r'/member/show',                    wx.member.show.List,                name='member.list'),
    url(r'/member/detail/(\d+)',            wx.member.show.Detail,              name='member.detail'),
    url(r'/member/change-category',         wx.member.show.ChangeCategory,      name='member.change_category'),
    url(r'/member/add-category',            wx.member.show.AddCategory,         name='member.add_category'),
    url(r'/member/delete-category',         wx.member.show.DeleteCategory,      name='member.delete_category'),
    url(r'/member/consume-level-show',      wx.member.show.ConsumeLevelList,    name='member.consume_level_list'),
    url(r'/member/consume-action-show',     wx.member.show.ConsumeActionList,   name='member.consume_action_list'),

    #ktv产品管理
    url(r'/ktv/show',                       ktv.manage.Show,                    name='ktv.show'),
    url(r'/ktv/publish',                    ktv.manage.Publish,                 name='ktv.publish'),
    url(r'/ktv/delete',                     ktv.manage.Delete,                  name='ktv.delete'),

    #ktv价格策略
    url(r'/ktv/price-schedule/show',        ktv.price.Show,                     name='ktv.price.show'),
    url(r'/ktv/price-schedule/add',         ktv.price.Add,                      name='ktv.price.add'),
    url(r'/ktv/price-schedule/(\d+)/edit',  ktv.price.Edit,                     name='ktv.price.edit'),

    #报表
    url(r'/report/sales-report',            report.stats.SalesReport,           name='report.sales_report'),
    url(r'/report/shop-report',             report.stats.ShopReport,            name='report.shop_report'),
    url(r'/report/channel-report',          report.stats.ChannelReport,         name='report.channel_report'),
    url(r'/report/get-sales-data',          report.stats.GetData,               name='report.get_data'),

    #消息信息
    url(r'/message/show',                   message.message.Message,            name='message.show'),
    url(r'/message/mark',                   message.message.UpdateID,           name='message.mark'),
    url(r'/message/unread',                 message.message.Unread,             name='message.unread'),
    url(r'/message/early',                  message.message.Early,              name='message.early'),

    #ktv已预订
    url(r'/ktv/daily-schedule/show',        ktv.order.OrderList,                name='ktv.daily.show'),
    url(r'/ktv/book-coupons/show',          ktv.order.CouponList,               name='ktv.book_coupon.show'),

    # 开通微信服务
    url(r'/setting/wx',                     wx.setting.Config,                  name='wx.setting'),

    #微信自定义菜单
    url(r'/wx/menu',                        wx.menu.show.Show,                  name='weixin.menu.show'),
    url(r'/wx/menu/edit',                   wx.menu.custom.Custom,              name='weixin.menu.edit'),

    #微信图文消息
    url(r'/wx/app-msg',                     wx.app_msg.app_msg.List,            name='weixin.app_msg'),
    url(r'/wx/app-msg/add',                 wx.app_msg.app_msg.Add,             name='weixin.app_msg.add'),
    url(r'/wx/app-msg/delete',              wx.app_msg.app_msg.Del,             name='weixin.app_msg.delete'),
    url(r'/wx/app-msg/edit',                wx.app_msg.app_msg.Edit,            name='weixin.app_msg.edit'),
    url(r'/wx/app-msg/(\d+)',               wx.app_msg.app_msg.Detail,          name='weixin.app_msg.detail'),
    url(r'/wx/app-msg/group',               wx.app_msg.group.List,              name='weixin.app_msg.group'),
    url(r'/wx/app-msg/group/add',           wx.app_msg.group.Add,               name='weixin.app_msg.group.add'),
    url(r'/wx/app-msg/group/edit',          wx.app_msg.group.Edit,              name='weixin.app_msg.group.edit'),
    url(r'/wx/app-msg/group/deleted',       wx.app_msg.group.Delete,            name='weixin.app_msg.group.deleted'),
    url(r'/wx/app-msg/group/detail',        wx.app_msg.group.Detail,            name='weixin.app_msg.group.detail'),

    # 微会员
    url(r'/wx/mem/cover',                   wx.member.MemCover,                 name='wx.mem_cover'),
    url(r'/wx/mem/cover/edit',              wx.member.MemCoverEdit,             name='wx.mem_cover.edit'),
    url(r'/wx/mem/block',                   wx.member.MemBlock,                 name='wx.mem_block'),
    url(r'/wx/mem/block/edit',              wx.member.MemBlockEdit,             name='wx.mem_block.edit'),
    url(r'/wx/mem-msg',                     wx.member.mem_msg.List,             name='wx.mem_msg'),
    url(r'/wx/mem-msg/add',                 wx.member.mem_msg.Add,              name='wx.mem_msg.add'),
    url(r'/wx/mem-msg/edit',                wx.member.mem_msg.Edit,             name='wx.mem_msg.edit'),
    url(r'/wx/attention/pull',              wx.member.attention.Pull,           name='wx.attention.pull'),

    #微信关键词应答
    url(r'/wx/keyword',                     wx.keyword.List,                   name='weixin.keyword'),
    url(r'/wx/keyword/add',                 wx.keyword.Add,                    name='weixin.keyword.add'),
    url(r'/wx/keyword/edit',                wx.keyword.Edit,                   name='weixin.keyword.edit'),
    url(r'/wx/keyword/delete',              wx.keyword.Delete,                 name='weixin.keyword.delete'),

    # 消息管理
    url(r'/wx/msg',                         wx.msg.Show,                        name='wx.msg.show'),

    # 微信关注后反馈消息
    url(r'/wx/feedback',                    wx.subscribe.Feedback,              name='wx.subscribe.feedback'),

    #微信客户评论
    url(r'/wx/comment',                     wx.comment.List,                    name='wx.comment'),

    #微信向会员发送消息
    url(r'/wx/send-message',                wx.send_all.Send,                   name='wx.send_all'),
    url(r'/wx/send-message/msg/ajax',       wx.send_all.MsgAjax,                name='wx.send_all.msg.ajax'),

    #微信官网
    url(r'/wx/site/cover',                  wx.site.SiteCover,                  name='wx.site.cover'),
    url(r'/wx/site/cover/edit',             wx.site.SiteCoverEdit,              name='wx.site.cover.edit'),
    url(r'/wx/site/tpl',                    wx.site.SiteTpl,                    name='wx.site.tpl'),
    url(r'/wx/site/slide',                  wx.site.SlideList,                  name='wx.site.slide'),
    url(r'/wx/site/slide/update',           wx.site.SlideUpdate,                name='wx.site.slide.update'),
    url(r'/wx/site/column',                 wx.site.ColumnList,                 name='wx.site.column'),
    url(r'/wx/site/column/update',          wx.site.ColumnUpdate,               name='wx.site.column.update'),

    #微信预约管理
    url(r'/wx/book',                        wx.book.List,                       name='wx.book'),
    url(r'/wx/book/edit',                   wx.book.Edit,                       name='wx.book.edit'),
    url(r'/wx/book/add',                    wx.book.Add,                        name='wx.book.add'),
    url(r'/wx/book/delete',                 wx.book.Delete,                     name='wx.book.delete'),
    url(r'/wx/book/order',                  wx.book.order.List,                 name='wx.book.order'),
    url(r'/wx/book/status',                 wx.book.order.Handle,               name='wx.book.status'),
    url(r'/wx/book/detail',                 wx.book.Detail,                     name='wx.book.detail'),

    #微信会员等级
    url(r'/wx/member/level',                wx.level.Level,                     name='wx.member.level'),
    url(r'/wx/member/level/setting',        wx.level.LevelSetting,              name='wx.member.level.setting'),

    #微信商城
    url(r'/wx/mall/cover',                  wx.mall.Cover,                      name='wx.mall.cover'),
    url(r'/wx/mall/cover/edit',             wx.mall.Edit,                       name='wx.mall.cover.edit'),
    url(r'/wx/goods/list',                  wx.mall.WxGoods,                    name='wx.goods.list'),
    url(r'/wx/goods/(\d+)',                 wx.mall.WxGoodsDetail,              name='wx.goods.detail'),
    url(r'/wx/goods/add',                   wx.mall.WxGoodsAdd,                 name='wx.goods.add'),
    url(r'/wx/goods/edit',                  wx.mall.WxGoodsEdit,                name='wx.goods.edit'),
    url(r'/wx/goods/delete',                wx.mall.WxGoodsDelete,              name='wx.goods.delete'),
    url(r'/wx/goods/on-sale',               wx.mall.WxGoodsOnSale,              name='wx.goods_on_sale.ajax'),
    url(r'/wx/goods/rank',                  wx.mall.WxGoodsRank,                name='wx.goods.rank'),

    #微活动
    url(r'/wx/activity/list',               wx.activity.List,                   name='wx.activity.list'),
    url(r'/wx/activity/add',                wx.activity.Add,                    name='wx.activity.add'),
    url(r'/wx/activity/edit',               wx.activity.Edit,                   name='wx.activity.edit'),
    url(r'/wx/activity/delete',             wx.activity.Delete,                 name='wx.activity.delete'),
    url(r'/wx/activity/cover',              wx.activity.Show,                   name='wx.activity.cover'),
    url(r'/wx/activity/cover/edit',         wx.activity.Cover,                  name='wx.activity.cover.edit'),
    url(r'/wx/activity/set-active',         wx.activity.SetActive,              name='wx.activity.set_active'),
    url(r'/wx/activity/sn',                 wx.activity.SnList,                 name='wx.activity.sn'),
    url(r'/wx/activity/sn/use',             wx.activity.SnUse,                  name='wx.activity.sn_use'),

    #通用
    url(r'/common/goods/categories',        common.GoodsCategories,             name='common.goods.categories'),
    url(r'/common/ke/upload-img',           common.KindEditorUploadImage,       name='common.ke.upload_img'),
    url(r'/common/supplier/shop',           common.SupplierShops,               name='common.supplier.shop'),
]
