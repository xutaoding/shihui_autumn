# -*- coding: utf-8 -*-

from ..import BaseHandler
from ..import require
from autumn.utils import json_dumps


class List(BaseHandler):
    @require('developer')
    def get(self):
        keys = self.redis.keys('q:*')
        keys = dict([(key, self.redis.llen(key)) for key in keys])
        self.render('temple/redis/list.html', keys=keys)


class Execute(BaseHandler):
    @require('developer')
    def post(self, command):
        self.request.arguments.pop('_xsrf', '')
        arg = lambda (k): self.get_argument(str(k))
        args = [arg(k) for k in sorted(map(int, self.request.arguments.keys())) if arg(k)]
        result = self.redis.execute_command(command, *args)
        self.write(json_dumps({'result': result}))
