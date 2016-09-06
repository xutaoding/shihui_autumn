# -*- coding: utf-8 -*-
import os
import redis
import logging
from tornado import ioloop, web, httpserver
from tornado.options import options, define
from conf import load_app_options
from controllers import handlers, MenuModule


if __name__ == '__main__':
    define('app_path', os.path.dirname(os.path.abspath(__file__)))  # app.py所在目录
    define('app_port', 8501)

    load_app_options()  # 加载配置

    settings = {
        'template_path': os.path.join(options.app_path, 'templates'),
        'static_path': os.path.join(options.app_path, 'static'),
        'cookie_secret': options.cookie_secret,
        'debug': options.app_debug,
        'login_url': '/intro',
        'xsrf_cookies': True,
        'ui_modules': {
        'menu': MenuModule,
        },
    }

    application = web.Application(handlers, **settings)
    application.redis = redis.StrictRedis(host=options.redis_host, port=options.redis_port, db=options.redis_db)

    server = httpserver.HTTPServer(application)
    server.listen(options.app_port)

    logging.info('application started on port:%s', options.app_port)
    ioloop.IOLoop.instance().start()
