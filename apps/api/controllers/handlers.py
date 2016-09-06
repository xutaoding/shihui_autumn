# -*- coding: utf-8 -*-
import taobao
import jingdong
import weixin
import wuba
import telephone
import alipay

handlers = [
    # 淘宝电子凭证
    (r'/api/v1/taobao/coupon',                  taobao.CouponAPI),  # 信任卖家
    (r'/api/v1/taobao/code-merchant',           taobao.CouponAPI),  # 码商(kunranma)

    # 京东
    (r'/api/v1/jd/gb/send-order',               jingdong.SendOrder),    # 订单通知
    (r'/api/v1/jd/gb/query-team-sell-count',    jingdong.SellCount),    # 查询订单销量
    (r'/api/v1/jd/gb/send-order-refund',        jingdong.OrderRefund),  # 退款
    (r'/api/v1/jd/gb/send-sms',                 jingdong.SendSms),      # 发送短信

    # 京东分销
    (r'/api/v1/jd/gb/push-order',               jingdong.PushOrder),      # 接收分销订单通知

    # 微信
    (r'/api/v1/wx/message/(\d+)',               weixin.WeixinAPI),

    #支付宝
    (r'/api/v1/alipay/notify',                  alipay.Notify),  # 接受手机支付宝返回的信息

    # 58 API
    (r'/api/v1/58/gb/order-add',                wuba.NewOrder),     # 新订单通知
    (r'/api/v1/58/gb/refund',                   wuba.Refund),       # 退款
    (r'/api/v1/58/gb/coupon-info',              wuba.Coupon),       # 查询券信息

    # 电话验证
    (r'/tel-verify2',                           telephone.Verify),
]
