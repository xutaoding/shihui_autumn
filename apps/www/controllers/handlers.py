# -*- coding: utf-8 -*-
from tornado.web import url
import goods.show

handlers = [
    url(r'/',                               goods.show.List,                    name='goods.show_list'),
    url(r'/p/(\d+)',                        goods.show.Detail,                  name='goods.detail'),
    url(r'/search',                         goods.show.Search,                  name='goods.search'),
    url(r'/goods/more',                     goods.show.GoodsAjax,               name='goods.show.ajax'),
    url(r'/goods/new',                      goods.show.New,                     name='goods.new'),
    url(r'/about',                          goods.About,                        name='goods.about'),
]