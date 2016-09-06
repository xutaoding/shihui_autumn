# -*- coding: utf-8 -*-
import tornado.web
from menu import menu_data


class MenuModule(tornado.web.UIModule):
    def render(self, menu_key):
        return self.render_string('ui_modules/menu.html', menu_data=menu_data, menu_key=menu_key)



