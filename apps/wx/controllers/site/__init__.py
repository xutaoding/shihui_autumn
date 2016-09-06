# -*- coding: utf-8 -*-
from ..import BaseHandler
from tornado.web import authenticated
from tornado.template import Template
from autumn.goods import img_url
from tornado.httputil import url_concat


class Index(BaseHandler):
    @authenticated
    def get(self):
        sp_id = self.current_user.sp_id
        sp_name = self.current_user.sp_name
        site_tpl = self.db.get('select wst.* from wx_site_tpl wst, supplier_property sp where sp.sp_id=%s '
                               'and sp.name="site_tpl_id" and cast(sp.value as unsigned)=wst.id', sp_id)
        slides = self.db.query('select * from wx_site_slide where sp_id=%s '
                               ' and is_show="1" order by display_order', sp_id)
        columns = self.db.query('select * from wx_site_column where sp_id=%s '
                                'and is_show="1" order by display_order', sp_id)
        body = Template(site_tpl.content).generate(title=sp_name, slides=slides, columns=columns,
                                                   img_url=img_url, handler=self, url_concat=url_concat)
        self.write(body)
