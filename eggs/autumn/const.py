# -*- coding: utf-8 -*-
from autumn.utils import PropDict

# account sequence type
seq = PropDict({
    'USED':             1,  # 券验证，实物发货(利润)
    'REFUND':           2,  # 退款
    'CHEAT_ORDER':      3,  # 刷单
    'PRE_PAYMENT':      4,  # 预付款
    'DEPOSIT':          5,  # 保证金
    'WX':               6   # 微信服务费
})

# item status type
status = PropDict({
    'BUY':              1, # 购买（电子券未消费/实物未发货）
    'USED':             2, # 电子券已消费/实物已发货
    'REFUND':           3, # 退款/退货
    'WAIT_TO_SEND':     4, # 实物待打包，待发货
    'UPLOADED':         5, # 已上传
    'FROZEN':           6, # 冻结
    'RETURNING':        7, # 退货中
})