# -*- coding: utf-8 -*-
import urllib
import urllib2
import itertools
import mimetools
import mimetypes
import logging
import os.path
import contextlib
from autumn.utils import json_dumps
from tornado import httputil
from tornado.httpclient import HTTPRequest, AsyncHTTPClient


class BaseAPI(object):
    def __init__(self):
        self._files = []
        self._fields = {}

        self._boundary = None

    def __call__(self, **kwargs):
        return self.fetch(**kwargs)

    def fetch(self, **kwargs):
        """ 利用 tornado 的 IOLoop 发起异步请求，用于 yield SomeAPI().fetch() """
        self._fields.update(kwargs)
        self.before_request()

        body = self.build_body()
        headers = httputil.HTTPHeaders(self.headers())
        if self.http_method() == 'POST':
            headers.add('Content-type', self.content_type())
            headers.add('Content-length', len(body))

        http_client = AsyncHTTPClient()
        request = HTTPRequest(url=self.url(), method=self.http_method(),
                              body=body, headers=headers)
        if not self._files:
            logging.info(json_dumps({'url': request.url, 'method': request.method,
                                     'headers': request.headers, 'body': request.body}))
        return http_client.fetch(request)

    def sync_fetch(self, **kwargs):
        """ 利用 urllib2 发起同步请求，一般用于本地测试，或者其他无需异步请求的情况. """
        self._fields.update(kwargs)
        self.before_request()

        request = urllib2.Request(self.url())

        body = self.build_body()
        headers = self.headers()

        for name in headers:
            request.add_header(name, headers[name])
        if self.http_method() == 'POST':
            request.add_header('Content-type', self.content_type())
            request.add_header('Content-length', len(body))
            request.add_data(body)

        if not self._files:
            logging.info(json_dumps({'url': request.get_full_url(), 'method': self.http_method(),
                                      'headers': request.headers, 'body': request.data}))
        with contextlib.closing(urllib2.urlopen(request)) as resp:
            return resp.read()

    def http_method(self):
        """ 请求方法. """
        raise NotImplementedError

    def url(self):
        """ 实际请求的 URL.  """
        raise NotImplementedError

    def headers(self):
        """ 请求头信息. """
        return {}

    def before_request(self):
        """ 在请求之前，可以做添加系统默认参数、添加签名等操作. """
        pass

    def parse_response(self, response):
        """ 解析 HTTP 返回值. """
        return response

    def content_type(self):
        if self.http_method() == 'GET':
            return None
        if self._files:
            return 'multipart/form-data; boundary=%s' % self.boundary()
        return 'application/x-www-form-urlencoded; charset=UTF-8'

    def boundary(self):
        if not self._boundary:
            self._boundary = mimetools.choose_boundary()
        return self._boundary

    def add_field(self, name, value):
        self._fields[name] = value

    def get_field(self, name):
        return self._fields[name]

    def add_fields(self, **kwargs):
        self._fields.update(kwargs)

    def add_file(self, field_name, file_name, body, mime_type=None):
        """ 添加需要上传的文件. """
        file_name = os.path.basename(file_name)
        file_name = file_name.encode('utf-8') if isinstance(file_name, unicode) else file_name
        if mime_type is None:
            mime_type = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
        self._files.append((field_name, file_name, mime_type, body))

    def build_body(self):
        """ 生成 HTTP 请求 body. """
        if self.http_method() == 'GET':
            return None

        if not self._files:
            return urllib.urlencode(self._fields)

        # Build a list of lists, each containing "lines" of the
        # request.  Each part is separated by a boundary string.
        # Once the list is built, return a string where each
        # line is separated by '\r\n'.
        parts = []
        part_boundary = '--' + self.boundary()

        # Add the form fields
        parts.extend(
            [
                part_boundary,
                'Content-Disposition: form-data; name="%s"' % name,
                '',
                self._fields[name],
            ] for name in self._fields
        )

        # Add the files to upload
        parts.extend(
            [
                part_boundary,
                'Content-Disposition: file; name="%s"; filename="%s"' % (field_name, filename),
                'Content-Type: %s' % mime_type,
                '',
                body
            ] for field_name, filename, mime_type, body in self._files
        )

        # Flatten the list and add closing boundary marker,
        # then return CR+LF separated data
        flattened = list(itertools.chain(*parts))
        flattened.append('--' + self.boundary() + '--')
        flattened.append('')
        return '\r\n'.join(flattened)

from alipay import AlipayNotify
from baidu import Baidu
from huanlegu import Huanlegu
from jingdong import Jingdong
from taobao import Taobao
from wuba import Wuba
from yihaodian import Yihaodian
from zhutong import Zhutong
from nuomi import NuomiBrowser
from dianping import DianpingBrowser
from meituan import MeituanBrowser
from lashou import LashouBrowser
