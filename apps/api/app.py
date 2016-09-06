# -*- coding: utf-8 -*-
import os
import logging
from tornado import ioloop, web, autoreload, httpserver
from tornado.options import options, define
import torndb
import redis
from controllers.handlers import handlers
from conf import load_app_options

if __name__ == '__main__':
    define('app_path', os.path.dirname(os.path.abspath(__file__)))  # app.py所在目录
    define('app_port', 8401)

    load_app_options()  # 加载配置

    settings = {
        'debug': options.app_debug,
        'xsrf_cookies': False,
    }

    application = web.Application(handlers, **settings)
    application.db = torndb.Connection(
        host=options.mysql_host, database=options.mysql_database,
        user=options.mysql_user, password=options.mysql_password)

    application.redis = redis.StrictRedis(host=options.redis_host, port=options.redis_port, db=options.redis_db)

    server = httpserver.HTTPServer(application)
    server.listen(options.app_port)

    # 注册程序退出处理函数
    from autumn.app import register_terminal_handler
    register_terminal_handler(server, application)

    # 注册tornado检测文件变更时，自动重启服务时的处理函数
    def on_reload():
        logging.info('close database connection')
        application.db.close()
    autoreload.add_reload_hook(on_reload)

    logging.info('application started on port:%s', options.app_port)
    ioloop.IOLoop.instance().start()