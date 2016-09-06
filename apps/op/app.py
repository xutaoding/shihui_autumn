# -*- coding: utf-8 -*-
import os
import logging
from tornado import ioloop, web, httpserver
from tornado.options import options, define
import torndb
import ui_modules
import redis
from conf import load_app_options
from tornado import autoreload


if __name__ == '__main__':
    define('app_path', os.path.dirname(os.path.abspath(__file__)))  # app.py所在目录
    define('app_port', 8201)

    load_app_options()  # 加载配置

    settings = {
        'template_path': os.path.join(options.app_path, 'templates'),
        'static_path': os.path.join(options.app_path, 'static'),
        'cookie_secret': options.cookie_secret,
        'debug': options.app_debug,
        'login_url': '/login',
        'xsrf_cookies': True,
        'ui_modules': {
            'menu': ui_modules.MenuModule,
            'supplier_select': ui_modules.SupplierSelect,
            'supplier_menu': ui_modules.SupplierMenu,
            'coupon_delay': ui_modules.CouponDelay,
        },
    }

    from controllers.handlers import handlers
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
