# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
import urllib
import tornado.gen
from tornado.httpclient import AsyncHTTPClient, HTTPRequest


class Index(BaseHandler):
    @require('developer')
    def get(self):
        self.render('mock/index.html')


class TaobaoCouponAPI(BaseHandler):
    @require('developer')
    @tornado.gen.coroutine
    def post(self):
        http_client = AsyncHTTPClient()

        request = HTTPRequest(
            url='http://127.0.0.1:8401/api/v1/taobao/coupon',
            method='POST',
            body=urllib.urlencode(
                dict([line.strip().split(':', 1) for line in self.get_argument('params').encode('utf-8').splitlines()])
            ))
        response = yield http_client.fetch(request)
        self.write(response.body)

