# -*- coding: utf-8 -*-
from .. import BaseHandler
from .. import require
from datetime import datetime
from autumn.torn.form import Form, Datetime
from voluptuous import Schema, Any
from autumn.utils.dt import ceiling
from autumn.torn.paginator import Paginator
from autumn.goods import contract_url
from tornado.options import options
import os
from tornado.web import StaticFileHandler
import tornado.web

supplier_schema = Schema({
    'supplier_name': str,
    'supplier_id': str,
    'action': Any('edit', 'add'),
    'start_at': Datetime(),
    'expire_at': Datetime(),
    'remark': str,
    'id': str,
    'image_path': str,
}, extra=True)


class List(BaseHandler):
    """显示所有有合同列表"""
    @require()
    def get(self, supplier_id):
        sql = """select s.name, s.short_name, c.* from supplier s, contract c
                 where c.deleted=0 and s.id = c.uid and c.uid=%s and c.type=1"""
        params = [supplier_id]
        page = Paginator(self, sql, params)

        supplier = self.db.get('select * from supplier where id=%s', supplier_id)

        self.render('supplier/contract/list.html', page=page, supplier=supplier)


class Add(BaseHandler):
    """显示合同添加页面, 处理合同添加请求"""
    @require('operator', 'admin')
    def get(self):
        form = Form(self.request.arguments, supplier_schema)
        supplier = self.db.get('select * from supplier where id=%s', form.supplier_id.value)
        self.render('supplier/contract/add.html', action='add', form=form, supplier=supplier)

    @require('operator', 'admin')
    def post(self):
        sql = """insert into contract (uid, start_at, expire_at, created_at, deleted, remark, type)
        values (%s, %s, %s, now(), 0, %s, 1)"""
        form = Form(self.request.arguments, supplier_schema)
        expire_at = datetime.strptime(str(form.expire_at.value), '%Y-%m-%d')

        #插入数据
        contract_id = self.db.execute(sql, form.supplier_id.value, form.start_at.value,
                                      ceiling(expire_at, today=True), form.remark.value)

        self.redirect(self.reverse_url('supplier.contract_upload', contract_id))


class Upload(BaseHandler):
    """上传合同图片"""
    @require('operator', 'admin')
    def get(self, contract_id):
        image_urls = []
        sql = """select * from contract where deleted=0 and id=%s"""
        contract = self.db.get(sql, contract_id)
        if contract.images:
            image_urls = generate_img_url(contract.images)

        supplier = self.db.get('select * from supplier where id=%s', contract.uid)
        self.render('supplier/contract/upload.html', contract_id=contract_id, supplier=supplier, image_urls=image_urls)

    @require('operator', 'admin')
    def post(self, contract_id):
        sql = """update contract set images=%s where id=%s"""
        urls = []
        paths = self.get_arguments('image_path')

        for path in paths:
            path = path.split('/')
            # '/contract/o/312/636/29/2014011613053055005.jpg' 只提取 '/312/636/29/2014011613053055005.jpg'存储
            url = '/' + '/'.join(path[3:])
            urls.append(url)
        images = ','.join(urls)
        self.db.execute(sql, images, contract_id)
        self.redirect(self.reverse_url('supplier.contract_detail', contract_id))


class Edit(BaseHandler):
    """编辑合同"""
    @require('operator', 'admin')
    def get(self):
        contract_id = self.get_argument('id')
        sql = """select s.short_name, c.* from supplier s, contract c
                 where c.deleted=0 and s.id=c.uid and c.id=%s"""
        contract = self.db.get(sql, contract_id)
        form = Form(contract, supplier_schema)
        supplier = self.db.get('select * from supplier where id=%s', contract.uid)

        self.render('supplier/contract/add.html', action='edit', form=form, supplier=supplier)

    @require('operator', 'admin')
    def post(self):
        sql = """update contract set start_at=%s, expire_at=%s, remark=%s where id=%s"""
        form = Form(self.request.arguments, supplier_schema)
        expire_at = datetime.strptime(str(form.expire_at.value), '%Y-%m-%d')

        #插入数据
        self.db.execute(sql, form.start_at.value, ceiling(expire_at, today=True), form.remark.value, form.id.value)
        contract_id = form.id.value

        self.redirect(self.reverse_url('supplier.contract_upload', contract_id))


class Detail(BaseHandler):
    """查看合同"""
    @require()
    def get(self, contract_id):
        image_urls = []
        sql = """select s.short_name, c.id, c.uid, c.start_at, c.expire_at, c.remark, c.images from supplier s,
        contract c where c.deleted=0 and s.id=c.uid and c.id=%s"""
        contract = self.db.get(sql, contract_id)
        if contract.images:
            image_urls = generate_img_url(contract.images)
        supplier = self.db.get('select * from supplier where id=%s', contract.uid)

        self.render('supplier/contract/detail.html', contract=contract, image_urls=image_urls, supplier=supplier)


class Delete(BaseHandler):
    """删除合同（数据库标记为删除）"""
    @require('operator', 'admin')
    def post(self):
        contract_id = self.get_argument("contract_id")
        # 标记删除合同
        sql = """update contract set deleted=1 where id=%s"""
        self.db.execute(sql, contract_id)
        supplier_id = self.db.get('select uid from contract where id=%s', contract_id).uid

        self.redirect(self.reverse_url('supplier.contract', supplier_id))


class ContractImage(StaticFileHandler):
    """获得合同图片"""
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
