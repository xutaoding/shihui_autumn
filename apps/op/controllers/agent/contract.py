# -*- coding: utf-8 -*-

from .. import BaseHandler, require
from autumn.torn.paginator import Paginator
from voluptuous import Schema
from autumn.torn.form import Form
from tornado.httputil import url_concat
from tornado.web import StaticFileHandler
import tornado.web
from autumn.goods import contract_url

schema = Schema({
    'id': str,
    'start_at': str,
    'expire_at': str,
    'remark': str,
    'action': str
})


class List(BaseHandler):
    @require()
    def get(self):
        uid = self.get_argument('agent_id')
        sql = 'select * from contract where deleted = 0 and type = 2 and uid = %s order by created_at desc'
        contracts = Paginator(self, sql, [uid])
        agent = self.db.get('select id, name, short_name from agent where id = %s', uid)

        self.render('agent/contract/list.html', contracts=contracts, agent=agent)


class Detail(BaseHandler):
    @require()
    def get(self, contract_id):
        agent_id = self.get_argument('agent_id')
        agent = self.db.get('select id, name, short_name from agent where id = %s', agent_id)

        contract = self.db.get('select * from contract where id = %s', contract_id)
        if contract.images:
            image_urls = generate_img_url(contract.images)

        self.render('agent/contract/detail.html', agent=agent, image_urls=image_urls, contract=contract)


class Add(BaseHandler):
    @require()
    def get(self):
        form = Form(self.request.arguments, schema)
        form.action.value = 'add'

        agent = self.db.get('select id, name, short_name from agent where id = %s', self.get_argument('agent_id'))
        self.render('agent/contract/contract.html', form=form, agent=agent)

    @require('operator', 'admin')
    def post(self):
        form = Form(self.request.arguments, schema)
        form.action.value = 'add'

        if not form.validate():
            agent = self.db.get('select id, name, short_name from agent where id = %s', self.get_argument('agent_id'))
            self.render('agent/contract/contract.html', form=form, agent=agent)
            return

        contract_id = self.db.execute('insert contract(uid, start_at, expire_at, created_at, remark, type) '
                                      'values(%s, %s, %s, NOW(), %s, 2)', self.get_argument('agent_id'),
                                      form.start_at.value, form.expire_at.value, form.remark.value)

        self.redirect(self.reverse_url('agent.contract.upload', contract_id))


class Edit(BaseHandler):
    @require()
    def get(self, cid):
        contract = self.db.get('select * from contract where id = %s', cid)
        form = Form(contract, schema)
        form.action.value = 'edit'

        agent = self.db.get('select id, name, short_name from agent where id = %s', self.get_argument('agent_id'))

        self.render('agent/contract/contract.html', form=form, agent=agent)

    @require('operator', 'admin')
    def post(self, cid):
        form = Form(self.request.arguments, schema)
        form.action.value = 'edit'

        if not form.validate():
            agent = self.db.get('select id, name, short_name from agent where id = %s', self.get_argument('agent_id'))
            self.render('agent/contract/contract.html', form=form, agent=agent)
            return

        self.db.execute('update contract set start_at = %s, expire_at = %s, remark = %s '
                        'where id = %s and type = 2', form.start_at.value, form.expire_at.value, form.remark.value, cid)

        self.redirect(self.reverse_url('agent.contract.upload', cid))


class Delete(BaseHandler):
    @require('operator', 'admin')
    def post(self):
        contract_id = self.get_argument('contract_id')
        agent_id = self.get_argument('agent_id')

        self.db.execute('update contract set deleted = 1 where id = %s', contract_id)

        self.redirect(url_concat(self.reverse_url('agent.contract'), {'agent_id': agent_id}))


class Upload(BaseHandler):
    """上传合同图片"""
    @require()
    def get(self, contract_id):
        image_urls = []
        sql = """select * from contract where deleted=0 and id=%s"""
        contract = self.db.get(sql, contract_id)
        if contract.images:
            image_urls = generate_img_url(contract.images)

        agent = self.db.get('select * from agent where id=%s', contract.uid)
        self.render('agent/contract/upload.html', contract_id=contract_id, agent=agent, image_urls=image_urls)

    @require('operator', 'admin')
    def post(self, contract_id):
        sql = """update contract set images = %s where id = %s """
        urls = []
        paths = self.get_arguments('image_path')

        for path in paths:
            path = path.split('/')
            # '/contract/o/312/636/29/2014011613053055005.jpg' 只提取 '/312/636/29/2014011613053055005.jpg'存储
            url = '/' + '/'.join(path[3:])
            urls.append(url)
        images = ','.join(urls)
        self.db.execute(sql, images, contract_id)

        agent_id = self.get_argument('agent_id')

        self.redirect(url_concat(self.reverse_url('agent.contract.detail', contract_id), {'agent_id': agent_id}))


class ContractImage(StaticFileHandler):
    """获得合同图片"""
    @require()
    def get(self, path, include_body=True):
        uid = self.get_secure_cookie('_opu')
        if uid and uid.isdigit():
            if not self.application.db.get('select * from operator where id=%s and deleted=0', uid):
                raise tornado.web.HTTPError(403)
        else:
            raise tornado.web.HTTPError(403)

        super(ContractImage, self).get(path, include_body)


def generate_img_url(images):
    """把数据库的图片名如：/27/610/148/231323.jpg
    转化成URL如：http://.../contract/o/27/610/148/231323.jpg"""
    image_urls = []
    image_list = images.split(',')
    for image in image_list:
        image_urls.append(contract_url(image))
    return image_urls
