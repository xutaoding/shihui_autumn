# -*- coding: utf-8 -*-

menu_data = [
    {
        'title': '电子券',
        'require': 'coupon',
        'endpoint': 'coupon.verify',
        'icon': '&#xf00b1;',
        'items': [
            {
                'title': '券验证',
                'endpoint': 'coupon.verify',
            },
            {
                'title': '已验证券列表',
                'endpoint': 'coupon.show_list',
            },
        ]
    },
    {
        'title': '实物',
        'require': 'real',
        'endpoint': 'real.show_shipping',
        'icon': '&#xf0134;',
        'items': [
            {
                'title': '下载发货单',
                'endpoint': 'real.show_shipping',
            },
            {
                'title': '上传发货单',
                'endpoint': 'real.import_shipping',
            },
            {
                'title': '退货管理',
                'endpoint': 'real.return_manage',
            },
        ]
    },
    {
        'title': '分销商品',
        'require': 'crm',
        'endpoint': 'goods.list',
        'icon': '&#xf017a;',
        'items': []
    },
    {
        'title': '财务管理',
        'require': '',
        'endpoint': 'finance.sequence',
        'icon': '&#xf0150;',
        'items': [
            {
                'title': '资金明细',
                'endpoint': 'finance.sequence',
            },
            {
                'title': '提现管理',
                'endpoint': 'finance.withdraw',
            },
        ]
    },
    {
        'title': '门店',
        'require': '',
        'endpoint': 'shop.show',
        'icon': '&#xf0135;',
        'items': [
            {
                'title': '门店管理',
                'endpoint': 'shop.show',
            },
            {
                'title': '账号管理',
                'endpoint': 'accounts.show',
            },
            {
                'title': '密码修改',
                'endpoint': 'password',
            }
        ]
    },
    {
        'title': '会员',
        'require': 'crm',
        'endpoint': 'member.list',
        'icon': '&#xf012d;',
        'items': [
            {
                'title': '会员管理',
                'endpoint': 'member.list',
            },
            {
                'title': '会员等级',
                'endpoint': 'wx.member.level'
            }
        ]
    },
    {
        'title': '微信',
        'require': 'weixin',
        'endpoint': 'weixin.app_msg',
        'icon': '&#xf01eb;',
        'items': [
            {
                'title': '图文管理',
                'endpoint': 'weixin.app_msg',
            },
            {
                'title': '关键词应答',
                'endpoint': 'weixin.keyword',
            },
            {
                'title': '自定义菜单',
                'endpoint': 'weixin.menu.show',
            },
            {
                'title': '欢迎信息',
                'endpoint': 'wx.subscribe.feedback',
            },
            {
                'title': '微官网',
                'endpoint': 'wx.site.cover',
            },
            {
                'title': '微商城',
                'endpoint': 'wx.mall.cover',
            },
            {
                'title': '微会员',
                'endpoint': 'wx.mem_cover',
            },
            {
                'title': '微预约',
                'endpoint': 'wx.book.order'
            },
            {
                'title': '微活动',
                'endpoint': 'wx.activity.cover'
            },
            {
                'title': '微酒店',
                'endpoint': ''
            },
            {
                'title': '微餐饮',
                'endpoint': ''
            },
            {
                'title': '消息管理',
                'endpoint': 'wx.msg.show',
            },
            {
                'title': '客户评论',
                'endpoint': 'wx.comment',
            },
            {
                'title': '群发消息',
                'endpoint': 'wx.send_all',
            },
        ]
    },
    {
        'title': 'KTV',
        'require': 'ktv',
        'endpoint': 'ktv.show',
        'icon': '&#xf0147;',
        'items': [
            {
                'title': '淘宝产品管理',
                'endpoint': 'ktv.show',
            },
            {
                'title': '价格策略',
                'endpoint': 'ktv.price.show',
            },
            {
                'title': '每日预订',
                'endpoint': 'ktv.daily.show',
            },
            {
                'title': '已预订券号',
                'endpoint': 'ktv.book_coupon.show',
            },
        ]
    },
    {
        'title': '报表',
        'require': 'crm',
        'endpoint': 'report.sales_report',
        'icon': '&#xf028d;',
        'items': [
            {
                'title': '商品报表',
                'endpoint': 'report.sales_report',
            },
            {
                'title': '门店报表',
                'endpoint': 'report.shop_report',
            },
            {
                'title': '渠道报表',
                'endpoint': 'report.channel_report',
            },
        ]
    },
    {
        'title': '消息',
        'require': '',
        'endpoint': 'message.show',
        'icon': '&#xf00b5;',
        'items': []
    },
]