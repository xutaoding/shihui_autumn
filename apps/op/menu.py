# -*- coding: utf-8 -*-

menu_data = [
    {
        'title': '首页',
        'endpoint': 'welcome',
        'items': [
            {
                'title': '欢迎',
                'endpoint': 'welcome',
            },
            {
                'title': '销售业绩',
                'endpoint': 'report.sales_summary',
            },
        ]
    },
    {
        'title': '合作伙伴',
        'endpoint': 'supplier.show_list',
        'items': [
            {
                'title': '商户列表',
                'endpoint': 'supplier.show_list'
            },
            {
                'title': '代理商列表',
                'endpoint': 'agent.list'
            },
        ]
    },
    {
        'title': '商品',
        'endpoint': 'goods.show_list',
        'items': [
            {
                'title': '商品列表',
                'endpoint': 'goods.show_list'
            },
            {
                'title': '分销商品',
                'endpoint': 'goods.distributor.show_list',
            },
            {
                'title': '商品上架情况',
                'endpoint': 'goods.status.on_sale',
            },
        ]
    },
    {
        'title': '订单',
        'endpoint': 'order.show_list',
        'items': [
            {
                'title': '订单列表',
                'endpoint': 'order.show_list'
            },
        ]
    },
    {
        'title': '电子券',
        'endpoint': 'coupon.show_list',
        'items': [
            {
                'title': '券列表',
                'endpoint': 'coupon.show_list'
            },
            {
                'title': '代理验证',
                'endpoint': 'coupon.verify'
            },
            {
                'title': '标记刷单',
                'endpoint': 'coupon.virtual_verify'
            },
            {
                'title': '电子券退款',
                'endpoint': 'coupon.verified_refund'
            },
            {
                'title': '券冻结',
                'endpoint': 'coupon.freeze'
            },
            {
                'title': '券延期',
                'endpoint': 'coupon.delay'
            },
            {
                'title': '分销券验证',
                'endpoint': 'coupon.distributor_verify'
            },
        ]
    },
    {
        'title': '实物',
        'endpoint': 'real.import_partner_order',
        'items': [
            {
                'title': '渠道订单',
                'endpoint': 'real.import_partner_order'
            },
            {
                'title': '货品列表',
                'endpoint': 'real.show_sku'
            },
            {
                'title': '库存管理',
                'endpoint': 'real.stock_list'
            },
            {
                'title': '订单出库',
                'endpoint': 'real.order_sku_list'
            },
            {
                'title': '退货单',
                'endpoint': 'real.return_list'
            },
        ]
    },
    {
        'title': '财务',
        'endpoint': 'finance.channel_goods_report',
        'items': [
            {
                'title': '商品销售报表',
                'endpoint': 'finance.channel_goods_report'
            },
            {
                'title': '销售业绩',
                'endpoint': 'finance.profit'
            },
            {
                'title': '提现申请',
                'endpoint': 'finance.withdraw'
            },
            {
                'title': '外部资金',
                'endpoint': 'finance.external_money_list'
            },
            {
                'title': '商户资金明细',
                'endpoint': 'finance.supplier_sequence'
            },
            {
                'title': '分销商资金明细',
                'endpoint': 'finance.resale_sequence'
            },
            {
                'title': '微信代理商',
                'endpoint': 'finance.agent_sequence'
            },
            {
                'title': '对账单',
                'endpoint': 'finance.statement'
            },

        ]
    },
    {
        'title': '行政',
        'endpoint': 'admin.notice',
        'items': [
            {
                'title': '通告',
                'endpoint': 'admin.notice'
            }
        ]
    },
    {
        'title': '运营',
        'endpoint': 'seewi.news.show_list',
        'items': [
            {
                'title': '视惠官网新闻',
                'endpoint': 'seewi.news.show_list'
            },
            {
                'title': '一百券推荐商品',
                'endpoint': 'yibaiquan.recommend.list'
            },
            {
                'title': '快递公司',
                'endpoint': 'express.list'
            },
            {
                'title': '商户广播',
                'endpoint': 'notice.send'
            },
        ]
    },
    {
        'title': 'BOSS',
        'endpoint': 'report.index',
        'items': [
            {
                'title': '销售汇总',
                'endpoint': 'report.index'
            },
            {
                'title': '销售排名',
                'endpoint': 'report.ranking'
            },
            {
                'title': '销售趋势',
                'endpoint': 'report.tendency_supplier'
            },
            {
                'title': '预付款',
                'endpoint': 'report.prepayment'
            }
        ]
    },
    {
        'title': '神殿',
        'endpoint': 'distributor.show_list',
        'items': [
            {
                'title': '分销商',
                'endpoint': 'distributor.show_list'
            },
            {
                'title': '分销商店铺',
                'endpoint': 'distributor.show_shop_list'
            },
            {
                'title': '帐号管理',
                'endpoint': 'operator.show_list'
            },
            {
                'title': '导入券',
                'endpoint': 'coupon.imported'
            },
            {
                'title': '导出券',
                'endpoint': 'coupon.export'
            },
            {
                'title': '导入外部订单',
                'endpoint': 'order.imported'
            },
            {
                'title': '微信接入',
                'endpoint': 'temple.wx.setting'
            },
            {
                'title': 'Redis',
                'endpoint': 'temple.redis'
            },
        ]
    },
]