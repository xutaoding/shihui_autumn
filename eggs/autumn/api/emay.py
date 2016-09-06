# -*- coding: utf-8 -*-

import urllib
from autumn.api import BaseAPI
from tornado.options import options
from tornado.template import Template
import xml.etree.ElementTree as ET


class EMay(BaseAPI):
    """亿美API"""

    def __init__(self, method):
        super(EMay, self).__init__()
        self.method = method

    def http_method(self):
        return 'POST'

    def url(self):
        return options.emay_gateway_url

    def content_type(self):
        return 'text/xml; charset=utf-8'

    def build_body(self):
        return Template(SOAP_TEMPLATE[self.method]).generate(**self._fields)

    def headers(self):
        return {
            'User-Agent': 'Python post',
            'soapaction': '""'
        }

    def parse_response(self, response):
        self.message = ET.fromstring(response)

    def is_ok(self):
        if self.message.findtext('.//return') == '0':
            return True
        return False

SOAP_TEMPLATE = {
    # 发送短信
    'sendSMS': """\
<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <soapenv:Body>
        <sendSMS xmlns="http://sdkhttp.eucp.b2m.cn/">
        <arg0 xmlns="">{{ serial_no }}</arg0>
        <arg1 xmlns="">{{ key }}</arg1>
        <arg2 xmlns="">{{ send_time }}</arg2>
        <arg3 xmlns="">{{ mobiles }}</arg3>
        <arg4 xmlns="">{{ sms_content }}</arg4>
        <arg5 xmlns="">{{ add_serial }}</arg5>
        <arg6 xmlns="">{{ src_charset }}</arg6>
        <arg7 xmlns="">{{ sms_priority }}</arg7>
        <arg8 xmlns="">{{ sms_id }}</arg8>
        </sendSMS>
    </soapenv:Body>
</soapenv:Envelope>
""",
    # 获取短息状态报告
    'getReport': """\
<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <soapenv:Body>
        <getReport xmlns="http://sdkhttp.eucp.b2m.cn/">
        <arg0 xmlns="">{{ serial_no }}</arg0>
        <arg1 xmlns="">{{ key }}</arg1>
        </getReport>
    </soapenv:Body>
</soapenv:Envelope>
""",
    # 注册软件
    'registEx': """\
<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <soapenv:Body>
        <registEx xmlns="http://sdkhttp.eucp.b2m.cn/">
        <arg0 xmlns="">{{ serial_no }}</arg0>
        <arg1 xmlns="">{{ key }}</arg1>
        <arg2 xmlns="">{{ password }}</arg2>
        </registEx>
    </soapenv:Body>
</soapenv:Envelope>
""",
    # 注册企业信息
    'registDetailInfo': """\
<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <soapenv:Body>
        <registDetailInfo xmlns="http://sdkhttp.eucp.b2m.cn/">
        <arg0 xmlns="">{{ serial_no }}</arg0>
        <arg1 xmlns="">{{ key }}</arg1>
        <arg2 xmlns="">{{ ename }}</arg2>
        <arg3 xmlns="">{{ link_man }}</arg3>
        <arg4 xmlns="">{{ phone_number }}</arg4>
        <arg5 xmlns="">{{ mobile }}</arg5>
        <arg6 xmlns="">{{ email }}</arg6>
        <arg7 xmlns="">{{ fax }}</arg7>
        <arg8 xmlns="">{{ address }}</arg8>
        <arg9 xmlns="">{{ postcode }}</arg9>
        </registDetailInfo>
    </soapenv:Body>
</soapenv:Envelope>
""",
    # 注销软件
    'logout':"""\
<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <soapenv:Body>
        <logout xmlns="http://sdkhttp.eucp.b2m.cn/">
        <arg0 xmlns="">{{ serial_no }}</arg0>
        <arg1 xmlns="">{{ key }}</arg1>
        </logout>
    </soapenv:Body>
</soapenv:Envelope>
""",
    # 获取账户余额
    'getBalance': """\
<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <soapenv:Body>
        <getBalance xmlns="http://sdkhttp.eucp.b2m.cn/">
        <arg0 xmlns="">{{ serial_no }}</arg0>
        <arg1 xmlns="">{{ key }}</arg1>
        </getBalance>
    </soapenv:Body>
</soapenv:Envelope>
""",
    # 查询单条短信收费
    'getEachFee': """\
<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <soapenv:Body>
        <getEachFee xmlns="http://sdkhttp.eucp.b2m.cn/">
        <arg0 xmlns="">{{ serial_no }}</arg0>
        <arg1 xmlns="">{{ key }}</arg1>
        </getEachFee>
    </soapenv:Body>
</soapenv:Envelope>
""",
    # 账户充值
    'chargeUp': """\
<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <soapenv:Body>
        <chargeUp xmlns="http://sdkhttp.eucp.b2m.cn/">
        <arg0 xmlns="">{{ serial_no }}</arg0>
        <arg1 xmlns="">{{ key }}</arg1>
        <arg2 xmlns="">{{ card_no }}</arg2>
        <arg3 xmlns="">{{ card_pass }}</arg3>
        </chargeUp>
    </soapenv:Body>
</soapenv:Envelope>
""",
    # 修改密码
    'serialPwdUpd': """\
<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <soapenv:Body>
        <serialPwdUpd xmlns="http://sdkhttp.eucp.b2m.cn/">
        <arg0 xmlns="">{{ serial_no }}</arg0>
        <arg1 xmlns="">{{ key }}</arg1>
        <arg2 xmlns="">{{ serial_pwd }}</arg2>
        <arg3 xmlns="">{{ serial_pwd_new }}</arg3>
        </serialPwdUpd>
    </soapenv:Body>
</soapenv:Envelope>
""",
}

