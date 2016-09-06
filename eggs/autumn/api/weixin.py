# -*- coding: utf-8 -*-

import hashlib
import urllib2
from tornado.httputil import url_concat
from autumn.api import BaseAPI
from tornado.options import options
from tornado.httpclient import HTTPRequest, AsyncHTTPClient
from tornado.gen import coroutine, Return
from datetime import datetime, timedelta
from autumn.utils import json_hook
import json
import logging
from autumn.utils import json_dumps


class Weixin(BaseAPI):
    def __init__(self, db='', sp_id='', method='', body=''):
        super(Weixin, self).__init__()
        self.db = db
        self.sp_id = sp_id
        self.method = method
        self.body = body
        self.message = None
        self.error = None

    def http_method(self):
        return 'POST'

    def url(self):
        fields = {'access_token': self.token}
        if self.method in get_methods:
            fields.update(self._fields)

        if self.method in file_methods:
            return url_concat(options.weixin_file_url, fields)
        return url_concat('%s/%s' % (options.weixin_gateway_url, self.method), fields)

    def content_type(self):
        if self.method in file_methods:
            return super(Weixin, self).content_type()

        return 'text/html; charset=utf-8'

    def before_request(self):
        """获取access_token"""
        has_token, msg = check_valid_token(self.db, self.sp_id)
        if not has_token:
            token, expire_at = self.fetch_token()
            if msg == 'add':
                logging.info('add sp=%s access_token: %s', self.sp_id, token)
                self.db.execute('insert into supplier_property (sp_id, name, value) '
                                'values (%s, "token", %s)', self.sp_id, token)
                self.db.execute('insert into supplier_property (sp_id, name, value) '
                                'values (%s, "token_expire_at", %s)', self.sp_id, expire_at)
            else:
                logging.info('update sp=%s access_token: %s', self.sp_id, token)
                self.db.execute('update supplier_property set value=%s '
                                'where sp_id=%s and name="token"', token, self.sp_id)
                self.db.execute('update supplier_property set value=%s '
                                'where sp_id=%s and name="token_expire_at"', expire_at, self.sp_id)
        else:
            logging.info('get sp=%s access_token: %s', self.sp_id, msg)
            token = msg
        self.token = token

    def set_app_info(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret

    def build_body(self):
        if not self.body:
            return super(Weixin, self).build_body()
        return self.body

    def parse_response(self, response):
        message = json.loads(response, object_hook=json_hook)
        if 'errmsg' in message:
            if message.errmsg != 'ok':
                self.error = message.errmsg
                self.error_code = message.errcode
                self.message = None
            else:
                self.error = None
                self.message = message.errmsg
        else:
            self.error = None
            self.message = message

    def is_ok(self):
        return self.message is not None

    def fetch_token(self):
        response = urllib2.urlopen('%s/token?grant_type=client_credential&appid=%s&secret=%s' %
                                   (options.weixin_gateway_url, self.app_id, self.app_secret))
        response = json.loads(response.read())
        expire_at = (datetime.now() + timedelta(seconds=(response['expires_in']-300))).strftime('%Y-%m-%d %H:%M:%S')
        return response['access_token'].encode('utf-8'), expire_at


def check_signature(signature, timestamp, nonce, token):
    sha1_signed = make_signature(timestamp, nonce, token)
    return signature.lower() == sha1_signed.lower()


def make_signature(timestamp, nonce, token):
    params = [token, timestamp, nonce]
    params_str = "".join(sorted(params))
    return hashlib.sha1(params_str).hexdigest()


def verify_wx_request(params, token):
    """验证微信发过来的消息的真实性"""
    signature = params.signature
    timestamp = params.timestamp
    nonce = params.nonce
    if signature and timestamp and nonce and check_signature(signature, timestamp, nonce, token):
        return True
    return False


def check_valid_token(db, sp_id):
    """检查access_token"""
    token_expire_at = db.get('select value from supplier_property where sp_id=%s and name="token_expire_at"',
                             sp_id)
    if not token_expire_at:
        return False, 'add'
    elif datetime.strptime(token_expire_at.value, "%Y-%m-%d %H:%M:%S") < datetime.now():
        return False, 'update'
    else:
        token = db.get('select value from supplier_property where sp_id=%s and name="token"', sp_id).value
        return True, token


@coroutine
def upload_pic(db, sp_id, msg_list, app_id, app_secret):
    """图片上传"""
    args = {
        'db': db,
        'sp_id': sp_id
    }

    upload = Weixin(method='upload', **args)
    upload.set_app_info(app_id, app_secret)

    pic_dict = {}
    for item in msg_list:
        pic = db.get('select cover from wx_app_msg where id = %s', item)
        pic_path = '%s%s' % (options.custom_img_path, pic.cover)
        # pic_path = '/nfs/images/p/804/609/359/ba784ce3_2014041111060383079_nw.jpg'
        fo = open(pic_path, 'rb')
        upload.add_file('media', fo.name, fo.read())
        fo.close()

        response = yield upload(type='image')

        upload.parse_response(response.body)
        if upload.is_ok():
            pic_dict.update({item: upload.message.media_id})

    raise Return(pic_dict)


@coroutine
def upload_news(db, pic_dict, app_id, app_secret, sp_id):
    """上传图文信息"""
    msgs = db.query('select id, author, title, content, summary from wx_app_msg where sp_id = %s and id in (%s)' %
                    ('%s', ','.join(['%s'] * len(pic_dict.keys()))), sp_id, *pic_dict.keys())

    upload_dict = {
        "articles": []
    }
    for msg in msgs:
        if pic_dict.get(str(msg.id), ''):
            format_dict = {
                "thumb_media_id": pic_dict.get(str(msg.id)),
                "author": msg.author,
                "title": msg.title,
                "content": msg.content,
                "digest": msg.summary
            }
            upload_dict['articles'].append(format_dict)

    upload = Weixin(method='media/uploadnews', db=db, sp_id=sp_id, body=json.dumps(upload_dict))
    upload.set_app_info(app_id, app_secret)

    response = yield upload()

    upload.parse_response(response.body)
    if upload.is_ok():
        raise Return({'ok': True, 'media': upload.message.media_id})
    else:
        raise Return({'ok': False, 'errmsg': error_list.get(upload.error_code)})


@coroutine
def sent_msg(db, user_list, app_id, app_secret, sp_id, media_id):
    """发送对象列表"""
    body = json_dumps({"touser": user_list, "mpnews": {'media_id': media_id}, "msgtype": "mpnews"})

    upload = Weixin(method='message/mass/send', db=db, sp_id=sp_id, body=body)
    upload.set_app_info(app_id, app_secret)

    response = yield upload()

    upload.parse_response(response.body)

    raise Return({'msg': error_list.get(upload.error_code), 'code': upload.error_code})


get_methods = ['user/get', 'user/info']
file_methods = ['upload']

wx_response = {
    'text': """
<xml>
<ToUserName><![CDATA[{{to_user}}]]></ToUserName>
<FromUserName><![CDATA[{{from_user}}]]></FromUserName>
<CreateTime>{{time}}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{{content}}]]></Content>
</xml> """,
    'news': """
    <xml>
<ToUserName><![CDATA[{{to_user}}]]></ToUserName>
<FromUserName><![CDATA[{{from_user}}]]></FromUserName>
<CreateTime>{{time}}</CreateTime>
<MsgType><![CDATA[news]]></MsgType>
<ArticleCount>{{len(items)}}</ArticleCount>
<Articles>
{% for item in items %}
<item>
<Title><![CDATA[{{item.title}}]]></Title>
<Description><![CDATA[{% raw item.description %}]]></Description>
<PicUrl><![CDATA[{{item.picurl}}]]></PicUrl>
<Url><![CDATA[{{item.url}}]]></Url>
</item>
{% end %}
</Articles>
</xml> """,
    'image': """
<xml>
<ToUserName><![CDATA[{{wx_id}}]]></ToUserName>
<FromUserName><![CDATA[{{sp_wx}}]]></FromUserName>
<CreateTime>{{time}}</CreateTime>
<MsgType><![CDATA[image]]></MsgType>
<Image>
<MediaId><![CDATA[{{media_id}}]]></MediaId>
</Image>
</xml>""",

}

error_list = {
    -1:   '系统繁忙',
    0:    '请求成功',
    40001:    '获取access_token时AppSecret错误，或者access_token无效',
    40002:    '不合法的凭证类型',
    40003:    '不合法的OpenID',
    40004:    '不合法的媒体文件类型',
    40005:    '不合法的文件类型',
    40006:    '不合法的文件大小',
    40007:    '不合法的媒体文件id',
    40008:    '不合法的消息类型',
    40009:    '不合法的图片文件大小',
    40010:    '不合法的语音文件大小',
    40011:    '不合法的视频文件大小',
    40012:    '不合法的缩略图文件大小',
    40013:    '不合法的APPID',
    40014:    '不合法的access_token',
    40015:    '不合法的菜单类型',
    40016:    '不合法的按钮个数',
    40017:    '不合法的按钮个数',
    40018:    '不合法的按钮名字长度',
    40019:    '不合法的按钮KEY长度',
    40020:    '不合法的按钮URL长度',
    40021:    '不合法的菜单版本号',
    40022:    '不合法的子菜单级数',
    40023:    '不合法的子菜单按钮个数',
    40024:    '不合法的子菜单按钮类型',
    40025:    '不合法的子菜单按钮名字长度',
    40026:    '不合法的子菜单按钮KEY长度',
    40027:    '不合法的子菜单按钮URL长度',
    40028:    '不合法的自定义菜单使用用户',
    40029:    '不合法的oauth_code',
    40030:    '不合法的refresh_token',
    40031:    '不合法的openid列表',
    40032:    '不合法的openid列表长度',
    40033:    '不合法的请求字符，不能包含\uxxxx格式的字符',
    40035:    '不合法的参数',
    40038:    '不合法的请求格式',
    40039:    '不合法的URL长度',
    40050:    '不合法的分组id',
    40051:    '分组名字不合法',
    41001:    '缺少access_token参数',
    41002:    '缺少appid参数',
    41003:    '缺少refresh_token参数',
    41004:    '缺少secret参数',
    41005:    '缺少多媒体文件数据',
    41006:    '缺少media_id参数',
    41007:    '缺少子菜单数据',
    41008:    '缺少oauth code',
    41009:    '缺少openid',
    42001:    'access_token超时',
    42002:    'refresh_token超时',
    42003:    'oauth_code超时',
    43001:    '需要GET请求',
    43002:    '需要POST请求',
    43003:    '需要HTTPS请求',
    43004:    '需要接收者关注',
    43005:    '需要好友关系',
    44001:    '多媒体文件为空',
    44002:    'POST的数据包为空',
    44003:    '图文消息内容为空',
    44004:    '文本消息内容为空',
    45001:    '多媒体文件大小超过限制',
    45002:    '消息内容超过限制',
    45003:    '标题字段超过限制',
    45004:    '描述字段超过限制',
    45005:    '链接字段超过限制',
    45006:    '图片链接字段超过限制',
    45007:    '语音播放时间超过限制',
    45008:    '图文消息超过限制',
    45009:    '接口调用超过限制',
    45010:    '创建菜单个数超过限制',
    45015:    '回复时间超过限制',
    45016:    '系统分组，不允许修改',
    45017:    '分组名字过长',
    45018:    '分组数量超过上限',
    46001:    '不存在媒体数据',
    46002:    '不存在的菜单版本',
    46003:    '不存在的菜单数据',
    46004:    '不存在的用户',
    47001:    '解析JSON/XML内容错误',
    48001:    'api功能未授权',
    50001:    '用户未授权该api'
}
