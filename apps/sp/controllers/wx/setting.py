# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
import hashlib
import json
from tornado.options import options
from tornado.gen import coroutine
from tornado.httpclient import HTTPRequest, AsyncHTTPClient
from datetime import datetime, timedelta
from autumn.utils import json_hook
from autumn.api.weixin import Weixin
import logging


class Config(BaseHandler):
    """商户微信导入"""
    @require()
    def get(self):
        self.render('wx/not_binding.html')
