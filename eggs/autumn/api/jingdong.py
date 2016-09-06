# -*- coding: utf-8 -*-
import base64
from Crypto.Cipher import AES
from autumn.api import BaseAPI
import xml.etree.ElementTree as ET
from tornado.options import options
from tornado.template import Template
from autumn.utils import aes_padding, aes_unpadding
import re
import time


class JdToUs():
    def __init__(self, content):
        content = re.sub(' xmlns="[^"]+"', '', content)  # 忽略 xmlns
        self.xml = ET.fromstring(content)
        self.vender_id = self.xml.findtext('VenderId')

        self.vender_key = None
        self.secret_key = None
        self.message = None

    def set_key(self, vender_key, secret_key):
        self.vender_key = vender_key
        self.secret_key = secret_key

    def parse(self):
        encrypted = self.xml.findtext('Encrypt').lower()
        if encrypted == 'true':
            raw = self.xml.findtext('Data')
            decrypted = re.sub(' xmlns="[^"]+"', '', decrypt(raw, self.secret_key))  # 忽略 xmlns
            self.message = ET.fromstring(decrypted)
        else:
            self.message = self.xml.find('Data/Message')

    def response(self, method, result_code, result_message, **params):
        if result_code == 200:
            data = Template(response_xml[method]).generate(**params)
            data = encrypt(data, self.secret_key)
        else:
            data = ''

        return Template(response_xml['main']).generate(
            version='1.0',
            zip='false',
            encrypt='true',
            vender_id=self.vender_id,
            result_code=result_code,
            result_message=result_message,
            data=data
        )


class Jingdong(BaseAPI):
    def __init__(self, method, vender_id, vender_key, secret_key):
        super(Jingdong, self).__init__()
        self.method = method

        self.vender_id = vender_id
        self.vender_key = vender_key
        self.secret_key = secret_key
        self.message = None
        self.result_code = None

    def http_method(self):
        return 'POST'

    def url(self):
        if self.method in fx_methods:
            return '%s/fenxiao/%s.action' % (options.jingdong_fx_gateway_url, self.method)
        else:
            return '%s/platform/normal/%s.action' % (options.jingdong_gateway_url, self.method)

    def content_type(self):
        return 'text/html; charset=utf-8'

    def build_body(self):
        data = Template(request_xml[self.method]).generate(time=time, **self._fields)
        return Template(request_xml['main']).generate(
            version='1.0',
            vender_id=self.vender_id,
            vender_key=self.vender_key,
            encrypt='true',
            zip='false',
            data=encrypt(data, self.secret_key),
        )

    def parse_response(self, response):
        response = re.sub(' xmlns="[^"]+"', '', response)  # 忽略 xmlns
        xml = ET.fromstring(response)
        encrypted = xml.findtext('Encrypt').lower()
        self.result_code = xml.findtext('ResultCode')
        if encrypted == 'true' and self.result_code == '200':
            raw = xml.findtext('Data')
            decrypted = re.sub(' xmlns="[^"]+"', '', decrypt(raw, self.secret_key))  # 忽略 xmlns
            self.message = ET.fromstring(decrypted)
        else:
            self.message = xml.find('Data/Message')

    def is_ok(self):
        return self.result_code == '200'


def encrypt(content, secret_key):
    return base64.b64encode(AES.new(secret_key).encrypt(aes_padding(content)))


def decrypt(content, secret_key):
    return aes_unpadding(AES.new(secret_key).decrypt(base64.b64decode(content)))


fx_methods = ('getCouponsCount', 'getCouponsList', 'queryCouponStatus')

request_xml = {
    'main': """\
<?xml version="1.0" encoding="utf-8"?>
<Request xmlns="http://tuan.jd.com/Request">
    <Version>{{ version }}</Version>
    <VenderId>{{ vender_id }}</VenderId>
    <VenderKey>{{ vender_key }}</VenderKey>
    <Zip>{{ zip }}</Zip>
    <Encrypt>{{ encrypt }}</Encrypt>
    <Data>{% raw data %}</Data>
</Request>""",

    'cancel': """\
<Message xmlns="http://tuan.jd.com/CancelTeamRequest">
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
</Message>""",

    'couponExtension': """\
<Message xmlns="http://tuan.jd.com/CouponExtensionRequest">
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <ExpireTime>{{ expire_time }}</ExpireTime>
</Message>""",

    'CouponShorten': """\
<Message xmlns="http://tuan.jd.com/CouponShortenRequest">
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <ExpireTime>{{ expire_time }}</ExpireTime>
</Message>""",

    'queryAreaList': """\
<Message xmlns="http://tuan.jd.com/QueryAreaRequest">
    <DistrictId>{{ district_id }}</DistrictId>
</Message>""",

    'queryCategoryList': """\
<Message xmlns="http://tuan.jd.com/QueryCategoryRequest">
     <CategoryId>{{ category_id }}</CategoryId>
</Message>""",

    'queryCityList': """\
<Message xmlns="http://tuan.jd.com/QueryCityRequest">
</Message>""",

    'queryCode': """\
<Message xmlns="http://tuan.jd.com/QueryCouponRequest">
    <JdOrderId>{{ jd_order_id }}</JdOrderId>
    <CouponId>{{ coupon_id }}</CouponId>
    <CouponPwd>{{ coupon_pwd }}</CouponPwd>
</Message>""",

    'queryDistrictList': """\
<Message xmlns="http://tuan.jd.com/QueryDistrictRequest">
    <CityId>{{ city_id }}</CityId>
</Message>""",

    'teamExtension': """\
<Message xmlns="http://tuan.jd.com/TeamExtensionRequest">
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <SaleEndDate>{{ sale_end_date }}</SaleEndDate>
</Message>""",

    'teamRestart': """\
<Message xmlns="http://tuan.jd.com/TeamRestartRequest">
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <BeginTime>{{ int(time.mktime(time.strptime(begin_time, '%Y-%m-%d %H:%M:%S'))) }}</BeginTime>
    <EndTime>{{ int(time.mktime(time.strptime(end_time, '%Y-%m-%d %H:%M:%S'))) }}</EndTime>
</Message>""",

    'teamShorten': """\
<Message xmlns="http://tuan.jd.com/TeamShortenRequest">
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <SaleEndDate>{{ sale_end_date }} 23:59:59</SaleEndDate>
</Message>""",

    'updateBImage': """\
<Message xmlns="http://tuan.jd.com/UpdateBImageRequest">
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
    <GrouponBImg>{{ img_url }}</GrouponBImg>
</Message>""",

    'updateDetail': """\
<Message xmlns="http://tuan.jd.com/UpdateDetailRequest">
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
    <Notes> {% raw notes %} </Notes>
    <TeamDetail>
        <![CDATA[ {% raw team_detail %} ]]>
    </TeamDetail>
</Message>""",

    'updateMaxNumber': """\
<Message xmlns="http://tuan.jd.com/UpdateMaxNumberRequest">
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
    <MaxNumber>{{ max_number }}</MaxNumber>
</Message>""",

    'updateTeamPartner': """\
<Message xmlns="http://tuan.jd.com/UpdateTeamPartnerRequest">
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
    <Partners>
        {% raw partners %}
    </Partners>
</Message>""",

    'updateTitle': """\
<Message xmlns="http://tuan.jd.com/UpdateTitleRequest">
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
    <TeamTitle><![CDATA[ {% raw team_title %}]]></TeamTitle>
</Message>""",

    'verifyCode': """\
<Message xmlns="http://tuan.jd.com/VerifyCouponRequest">
    <VerifyType>0</VerifyType>
    <JdOrderId>{{ jd_order_id }}</JdOrderId>
    <CouponId>{{ coupon_id }}</CouponId>
    <CouponPwd>{{ coupon_pwd }}</CouponPwd>
</Message>""",

    'queryTeamInfo': """\
<Message xmlns="http://tuan.jd.com/QueryTeamInfoRequest">
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
</Message>
    """,

    'uploadTeam': """\
<Message xmlns="http://tuan.jd.com/UploadTeamRequest">
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <TeamTitle><![CDATA[{% raw team_title %}]]></TeamTitle>
    <CityId>{{ city_id }}</CityId>
    <DistrictList>
        {% for district_id in districts %}
        <District>
            <DistrictId>{{ district_id }}</DistrictId>
            <AreaList>
                {% for area_id in districts[district_id] %}
                <AreaId>{{ area_id }}</AreaId>
                {% end %}
            </AreaList>
        </District>
        {% end %}
    </DistrictList>
    <GroupId>{{ group_id }}</GroupId>
    <Group2List>
        {% for group in group2 %}
        <GroupId>{{ group }}</GroupId>
        {% end %}
    </Group2List>
    <Title><![CDATA[{% raw title %}]]></Title>
    <GrouponBImg>{{ groupon_bimg }}</GrouponBImg>
    <MarketPrice>{{ market_price*100 }}</MarketPrice>
    <TeamPrice>{{ team_price*100 }}</TeamPrice>
    <BeginTime>{{ int(time.mktime(time.strptime(begin_time, '%Y-%m-%d %H:%M:%S'))) }}</BeginTime>
    <EndTime>{{ int(time.mktime(time.strptime(end_time, '%Y-%m-%d %H:%M:%S')))  }}</EndTime>
    <CouponExpireTime>{{ int(time.mktime(time.strptime(expire_time, '%Y-%m-%d %H:%M:%S'))) }}</CouponExpireTime>
    <CouponVerifyMode>1</CouponVerifyMode>
    <CouponBindMode>1</CouponBindMode>
    <CouponGrantMode>3</CouponGrantMode>
    <StockMode>0</StockMode>
    <MinNumber>{{ min_number }}</MinNumber>
    <MaxNumber>{{ max_number }}</MaxNumber>
    <PerNumber>{{ per_number }}</PerNumber>
    <Notice><![CDATA[ {% raw notice %} ]]> </Notice>
    <Summary><![CDATA[ {% raw summary %} ]]></Summary>
    <TeamDetail><![CDATA[{% raw team_detail %}]]> </TeamDetail>
    <Partners>
    {% for shop in shops %}
        {% if shop.deleted != 1 %}
        <Partner>
            <Name><![CDATA[{% raw shop.name %}]]></Name>
            <Address><![CDATA[{% raw shop.address %}]]></Address>
            <Map/>
            <Contact/>
            <Tel>{{ shop.phone }}</Tel>
            <Mobile/>
            <Location/>
        </Partner>
        {% end %}
    {% end %}
    </Partners>
</Message>""",

    'getCouponsCount': """\
<Message xmlns="http://gw.tuan.jd.com/fenxiao/GetCouponsCountRequest">
    <JdOrderId>{{order_id}}</JdOrderId>
</Message>""",

    'getCouponsList': """\
<Message xmlns="http://gw.tuan.jd.com/fenxiao/GetCouponsListRequest">
    <JdOrderId>{{order_id}}</JdOrderId>
    <Start>{{start}}</Start>
    <Count>{{count}}</Count>
</Message>""",

    'queryCouponStatus': """\
<Message xmlns="http://gw.tuan.jd.com/fenxiao/QueryCouponStatusRequest">
    <CouponId>{{coupon}}</CouponId>
</Message>""",
}

response_xml = {
    'main': """\
<?xml version="1.0" encoding="utf-8"?>
<Response xmlns="http://tuan.jd.com/Response">
    <Version>{{ version }}</Version>
    <VenderId>{{ vender_id }}</VenderId>
    <Zip>{{ zip }}</Zip>
    <Encrypt>{{ encrypt }}</Encrypt>
    <ResultCode>{{ result_code }}</ResultCode>
    <ResultMessage>{{ result_message }}</ResultMessage>
    {% if result_code == 200 %}
        <Data>{% raw data %}</Data>
    {% else %}
        <Data/>
    {% end %}
</Response>""",

    'send_order': """\
<Message xmlns="http://tuan.jd.com/SendOrderResponse">
    <JdTeamId>{{ jd_team_id }}</JdTeamId>
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <SellCount>{{ sell_count }}</SellCount>
    <VenderOrderId>{{ vender_order_id }}</VenderOrderId>
    <Coupons>
        {% for coupon in coupons %}
        <Coupon>
            <CouponId>{{ coupon }}</CouponId>
            <CouponPwd></CouponPwd>
        </Coupon>
        {% end %}
    </Coupons>
</Message>""",

    'sell_count': """\
<Message xmlns="http://tuan.jd.com/QueryTeamSellCountResponse">
    <VenderTeamId>{{ vender_team_id }}</VenderTeamId>
    <SellCount>{{ sell_count }}</SellCount>
</Message>""",

    'order_refund': """\
<Message xmlns="http://tuan.jd.com/SendOrderRefundResponse">
    <JdOrderId>{{ jd_order_id }}</JdOrderId>
    <VenderOrderId>{{ vender_order_id }}</VenderOrderId>
    <Coupons>
        {% for coupon in coupons %}
        <Coupon>coupon</Coupon>
        {% end %}
    </Coupons>
</Message>""",

    'send_sms': """\
<Message xmlns="http://tuan.jd.com/SendSmsResponse">
    <JdCouponId>{{ jd_coupon_id }}</JdCouponId>
    <VenderCouponId>{{ vender_coupon_id }}</VenderCouponId>
    <Mobile>{{ mobile }}</Mobile>
</Message>""",

    'push_order': """\
<Message xmlns="http://gw.tuan.jd.com/fenxiao/PushOrderResponse">
</Message>""",
}

jd_error = {
    'error_message': {
        -100: '身份验证失败',
        -498: '合作伙伴团购id 过长',
        -499: '合作伙伴团购id 为空',
        -500: '插入外团失败,外团扩展表没有成功插入',
        -501: '团购已经存在',
        -502: '上报的Title 不能正确',
        -503: '上报的市场价不正确',
        -504: '上报的团购价不正确',
        -505: '上报的开始时间不正确',
        -506: '上报的结束时间不正确',
        -507: '上报的券的有效期不正确',
        -508: '上报的最低成团人数不正确',
        -509: '上报的最高成团人数不正确',
        -510: '上报的本单简介不正确',
        -511: '上报的特别提示不正确',
        -512: '上报的每人限购数量不正确',
        -514: 'erp 同步错误',
        -515: '上报异常 ，参数不准确',
        -516: '上报的分类长度不正确',
        -517: '上报的城市ID 长度不正确',
        -518: '上报的标题短名称不正确',
        -519: '主图抓取保存到本地出现异常',
        -520: '上报的团购详情不正确',
        -521: '上报的市场价小于团购价',
        -522: '上报的团购开始时间大于团购结束时间',
        -523: '上报的团购结束时间大于优惠有效期',
        -524: '上传的城市ID 不存在',
        -525: '上传的分类ID 不存在',
        -526: '上报的券号，或者密码长度不正确',
        -527: '上报的图片地址不正确',
        -529: '连锁店名称为空',
        -530: '商家地址不能为空',
        -531: '商家电话不能为空',
        -532: '商家信息不存在',
        -533: '不支持该模式, 优惠券发放模式',
        -535: '此区域ID 下没有这个商圈ID',
        -536: '添加团购区域失败',
        -537: '添加团购商圈失败',
        -538: '团购区域ID 或团购区域商圈为空',
        -539: '此一级分类ID 下没有这个二级分类ID',
        -540: '添加二级分类失',
        -543: '团购的商圈总数量不可以超过20 个',
        -542: '团购区域数量不可以超过20 个',
        -544: '团购一级分类下的二级分类数量不可超过3个',
        -560: '多线程上报异常',
        -561: '上报的PerNumber 不能大于99'
    },

    'teamExtension': {
        -100: '身份验证失败',
        0: '延期失败，出现异常',
        10: '售馨下架（商品卖光）',
        20: '销售截止日期小于当前时间，产品已下架（产品下架）',
        30: '延期日期小于等于销售截止日期',
        70: '延期日期为空',
        40: '产品id 或 外团id 不正确',
        50: '团购项目不存在',
        60: '校验京东团购ID 和外团ID 失败'
    },

    'couponExtension': {
        -100: '身份验证失败',
        -1: '查询团购信息为空',
        50: '京东团购ID 所属项目不存在',
        10: '延期日期小于原截止日期',
        20: '延期日期小于当前日期',
        30: '延期日期为空',
        0: '延期失败，出现异常',
        40: '产品id 或者外团id 不正确'
    },

    'teamRestart': {
        -100: '身份验证失败',
        301: '团购结束时间早于当前时间',
        302: '团购开始时间晚于团购结束时间',
        303: '团购项目不存在',
        304: '团购不是下架的团购'
    },

    'updateDetail': {
        -100: '身份验证失败',
        -535: 'JdTeamId 节点参数不正确',
        -537: 'VenderTeamId 节点参数不正确',
        -538: '根据京东id、外团id 查询是不是有上报过这个团购',
        -300: '团购不存在',
        -510: '更新详情失败',
        -513: '更新详情失败',
        -514: '更新详情失败',
        -500: '内部异常'
    },

    'updateBImage': {
        -100: '身份验证失败',
        300: 'Team is null',
        500: '更新主图失败',
        501: '抓取主图失败',
        502: 'URL 路径不能访问',
        503: 'url 路径为空',
        40: 'TeamId 或venderTeamId 为空'
    },

    'updateTitle': {
        -100: '身份验证失败',
        -300: '不存在此团购项目',
        -500: '程序执行异常',
        -510: '更新团购标题信息出错',
        -535: 'JdTeamId 不是有效数据',
        -537: 'VenderTeamId 不是有效数据',
        -538: '没有上报过这个团购',
        -539: '标题长度>200'
    },

    'updateTeamPartner': {
        -100: '身份验证失败',
        -500: '程序执行异常',
        -535: 'JdTeamId 不是有效数据',
        -537: 'VenderTeamId 不是有效数据',
        -538: '没有上报过这个团购',
        -539: '不存在此团购项目',
        -540: '商家信息列表为空 (至少填写一个商家信息)',
        -541: '商家名称必填',
        -542: '商家名称最长40 个字符',
        -543: '商家地址必填',
        -544: '商家地址最长80 个字符',
        -545: '地图连接超过100 个字符',
        -546: '地图连接必须以http 开头',
        -547: '商家联系人最长30 个字符',
        -548: '商家电话必填',
        -549: '商家电话最长40 个字符',
        -550: '商家手机最长12 个字符',
        -551: '商家手机只能是数字',
        -552: '交通信息最长400 个字符'
    },

    'cancel': {
        -100: '身份验证失败',
        40: '产品id 或者外团id 不正确',
        -1: '接口调用异常',
        -2: '下架团购不存在'
    }
}