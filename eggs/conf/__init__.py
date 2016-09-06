# -*- coding: utf-8 -*-
from tornado.options import define, options
import os
import os.path
import logging
import logging.handlers


__default_conf = {
    'conf_file':        'dev.conf',
    'app_debug':        False,
    'app_mode':        'dev',
    'cookie_secret':    '~waD*4n+]nI]HnVq)A~p=Z+]<4Uf/&^1G`_8@0Yoz:uW|q&:H?pP2>Kg@/<]Y(Wk',

    'mysql_host':       '192.168.18.244:3306',
    'mysql_database':   'autumn',
    'mysql_user':       'root',
    'mysql_password':   'seewidb',

    'redis_host':       '192.168.18.244',
    'redis_port':       6379,
    'redis_db':         '1',

    # 队列
    'queue_distributor_order':              'q:order:distributor:todo',  # 分销订单等待队列
    'queue_distributor_order_processing':   'q:order:distributor:processing',  # 分销订单处理队列
    'queue_coupon_send':                    'q:coupon:send:todo',  # 券号短信发送等待队列
    'queue_coupon_send_processing':         'q:coupon:send:processing',  # 券号短信发送处理队列
    'queue_coupon_send_emay':               'q:coupon:send:emay',  # 亿美短信发送队列
    'queue_sms_send':                       'q:sms:send:todo',  # 其他短信发送等待队列
    'queue_sms_send_processing':            'q:sms:send:processing',  # 其他短信发送处理队列
    'queue_distributor_failed_order':       'q:order:distributor:fail',  # 记录58 创建一百券订单失败时的分销订单
    'queue_taobao_express':                 'q:taobao:express_number:todo',  # 淘宝订单号自动更新
    'queue_taobao_express_processing':      'q:taobao:express_number:processing',  # 淘宝订单号更新处理队列
    'queue_email':                          'q:email:todo',
    'queue_email_processing':               'q:email:processing',
    'queue_coupon_local_verify':            'q:coupon:local_verify:todo',
    'queue_coupon_local_verify_processing': 'q:coupon:local_verify:processing',
    'queue_vcode':                          'vcode',  # 验证码记录


    # 邮件
    'mail_smtp_host':   'smtp.ym.163.com',
    'mail_smtp_user':   'notify@seewi.com.cn',
    'mail_smtp_pwd':    '1qaz@WSX#EDC',
    'mail_smtp_from':   'notify@seewi.com.cn',
    'mail_smtp_ssl':    True,

    # redis key
    'redis_key_coupon':     'c',
    'redis_key_order':      'o',

    # 域名
    'supplier_domain':      'shangjia.uhuila.com',  # 商户
    'operate_domain':      'op.uhuila.com',  # 运营后台

    # 图片信息
    'cdn_root':             '/nfs/images',
    'upload_img_path':      '/nfs/images/o',
    'custom_img_path':      '/nfs/images/p',
    'upload_img_path_contract': '/nfs/images/contract/o',
    'img_host':             '127.0.0.1:8101',
    #'img_host':             'cdn.uhuila.com',
    #'img_host':             'img0.uhcdn.com',
    'img_key':              'sJ34fds29h@d',

    # 分销商信息
    'distributor_id_taobao': 13,
    'distributor_id_jingdong': 10,
    'distributor_id_yihaodian': 7,
    'distributor_id_wuba': 14,
    'distributor_id_baidu': 47,
    'distributor_id_meituan': 44,
    'distributor_id_dianping': 40,
    'distributor_id_nuomi': 42,
    'distributor_id_wowo': 37,
    'distributor_id_weixin': 50,
    # 分销店铺信息
    'shop_id_taobao':    13,
    'shop_id_dangdang':  9,
    'shop_id_gaopeng':  27,
    'shop_id_tuangouwang':  28,
    'shop_id_liketuan':  29,
    'shop_id_uuwang':  30,
    'shop_id_tmall':     34,
    'shop_id_jingdong':  10,
    'shop_id_jdb':       53,
    'shop_id_yihaodian': 7,
    'shop_id_wuba':      14,
    'shop_id_baidu':     47,
    'shop_id_meituan':   44,
    'shop_id_dianping':  40,
    'shop_id_nuomi':  42,
    'shop_id_wowo':  37,
    'shop_id_jibin':  38,
    'shop_id_yibaiquan': 22,

    # 商品类型
    'goods_type_electronic':  'E',
    'goods_type_real':      'R',

    'taobao_coupon_merchant_id': 1705483381,
    'taobao_coupon_posid': 7517,
    'taobao_coupon_merchant_app_key': '21519243',

    'expiring_contract_receivers': 'dev@uhuila.com,hua.wang@seewi.com.cn',

    # 微商城商品最小费率
    'wx_min_commission': 3,

    # 一号店
    'yhd_gateway_url': 'http://openapi.yhd.com/app/api/rest/router',
    'yhd_app_key':     '10420013092600000243',
    #'yhd_app_session': 'e1e12b8da6526de308cef3332622e5b2',  # 一号店正式店铺quanfx的session
    'yhd_app_session': '2b39ae41815a1a31e41bcdbba004bbd5',  # 一号店测试店铺sbytestshop02的session,店铺密码：sts222
    'yhd_app_secret':  '9a77a026dd55e453f588c3e5b8eddf09',
    'yhd_delivery':     1759,

    # 58 同城
    'wuba_gateway_url':     'http://eapi.test.58v5.cn/api/rest',
    'wuba_app_id':          '100765',
    'wuba_secret_key':      '392fece8',
    #'wuba_secret_key':      '392fece864cb40589146637b69bad616',
    #'wuba_gateway_url':      'http://eapi.58.com/api/rest',  # 正式环境
    #'wuba_app_id':           '333734',  # 正式环境
    #'wuba_secret_key':       '2a6f8f2c',  # 正式环境的key

    # 百度团购
    'baidu_gateway_url':    'http://220.181.163.98:11211/lbs-api/open/deliver/groupon/',
    'baidu_user_name':      '视惠生活',
    'baidu_token':          '83b295f4b17cee3ffac6ab208734c695',

    # 京东
    #'jingdong_vender_id':   '1022',
    #'jingdong_vender_key':  '8ujbgr5tdxswqafr',
    #'jingdong_secret_key':  '7shw6etrgcjs52ga',
    #'jingdong_gateway_url': 'http://gw.tuan.jd.com',

    'jingdong_vender_id':   '7870',
    'jingdong_vender_key':  '9999aaaaAAAA8885',
    'jingdong_secret_key':  '8885aaaa9999bbbb',
    'jingdong_gateway_url': 'http://gw.tuan.jd.net',  #tbsandbox,

    # 京东分销
    'jingdong_fx_vender_id':   '7662',
    'jingdong_fx_vender_key':  '23056134asfhRDAu',
    'jingdong_fx_secret_key':  'luhuishu1234567u',
    'jingdong_fx_gateway_url': 'http://gw.tuan.jd.net',

    # 淘宝
    #'taobao_gateway_url':   'http://gw.api.taobao.com/router/rest',  # 正式环境
    'taobao_gateway_url':   'http://gw.api.tbsandbox.com/router/rest',
    'taobao_kunran_app_key': '21519243',
    'taobao_kunran_id':     '1705483381',

    # 支付宝
    'alipay_verify_url':    'https://www.alipay.com/cooperate/gateway.do?service=notify_verify',
    'alipay_gateway_url':   'https://mapi.alipay.com/gateway.do',
    'alipay_partner':       '2088301101779485',
    'alipay_secret_key':    's45ka6duejz9em93xklwq2fais9h5uf4',
    'alipay_seller_email':  'uhuila@126.com',
    'alipay_input_charset': 'UTF-8',
    'alipay_notify_url':    'http://test.uhuila.com:18801/pay_notify/alipay',
    'alipay_return_url':    'http://test.uhuila.com:18801/order_result/alipay',
    'alipay_wap_notify_url':    'http://api.quanfx.com/api/v1/alipay/notify',
    'alipay_wap_gateway_url':   'http://wappaygw.alipay.com/service/rest.htm',
    'alipay_wap_merchant_url':  '',

    # 助通
    'ztsms_gateway_url':    'http://www.ztsms.cn:8800/sendXSms.do',
    'ztsms_username':       'shihui',
    'ztsms_password':       'shyibaiquan',
    #ztsms_product_id:      '887361',
    'ztsms_product_id':     '191919',

    # 亿美短信通道
    'emay_gateway_url':     'http://sdk4report.eucp.b2m.cn:8080/sdk/SDKService',
    'emay_serial_no':       '6SDK-EMY-6688-KCVUK',
    'emay_key':             'shihui88',  # 自定义的key
    'emay_password':        '465348',  # 仅在注册时需要，调用都用KEY
    'emay_sesson_key':      '',


    # 欢乐谷/玛雅
    'hlg_url':              'http://202.104.133.113:8060/api/send/',
    'hlg_secret_key':       'D7A38EFD', #4E1D4F42B5C198CEF8727022'
    'hlg_distributor_id':   '10001097',
    'hlg_client_id':        'HVC000000065',

    # 微信
    'weixin_token':         'dk8Df8zlmq13aHocQ9',
    'weixin_user_name':     'gh_f498eff53170',
    'weixin_gateway_url':   'https://api.weixin.qq.com/cgi-bin',
    'weixin_file_url':      'http://file.api.weixin.qq.com/cgi-bin/media/upload'
}


def load_default_options():
    for key in __default_conf:
        define(key, __default_conf[key])


def load_app_options():
    load_default_options()
    options.parse_command_line(final=False)  # 读取命令行参数
    options.parse_config_file(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           options.conf_file), final=True)  # 读取文件配置
