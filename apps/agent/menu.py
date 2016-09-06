# -*- coding: utf-8 -*-

menu_data = [
    {
        'title': '首页',
        'endpoint': 'welcome.index',
        'icon': 'icon-dashboard',
        'require_agent_type': [],
        'items': []
    },
    {
        'title': '签约商户',
        'endpoint': 'supplier.list',
        'icon': 'icon-sitemap',
        'require_agent_type': [],
        'items': [
            {
                'title': '商户列表',
                'endpoint': 'supplier.list',
                'require_agent_type': [],
            },
            {
                'title': '商户产品',
                'endpoint': 'supplier.goods',
                'require_agent_type': [],
            },
            {
                'title': '商户流水',
                'endpoint': 'supplier.sequence',
                'require_agent_type': [],
            },
        ]
    },
    {
        'title':'商户池子',
        'endpoint':'supplier.pool.list',
        'icon':'glyphicon glyphicon-cloud',
        'require_agent_type':[],
        'items':[
            {
                'title':'所有商户',
                'endpoint':'supplier.pool.list',
                'require_agent_type':[],
            },
            {
                'title':'我的商户',
                'endpoint':'supplier.marked.list',
                'require_agent_type':[],
            },
            {
               'title':'申请进度',
                'endpoint':'supplier.submitted.list',
                'require_agent_type':[],
            }
        ]
    },
    {
        'title': '财务管理',
        'endpoint': 'finance.sequence',
        'icon': 'icon-credit-card',
        'require_agent_type': [],
        'items': [
            {
                'title': '商户打款',
                'endpoint': 'finance.supplier.money',
                'require_agent_type': [],
                },
            {
                'title': '财务明细',
                'endpoint': 'finance.sequence',
                'require_agent_type': [1],
            },
            {
                'title': '提现记录',
                'endpoint': 'finance.withdraw.list',
                'require_agent_type': [],
            },
#            {
#                'title': '申请提现',
#                'endpoint': 'finance.withdraw.apply',
#                'require_agent_type': [],
#            },
        ]
    },
]