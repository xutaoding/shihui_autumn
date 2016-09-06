# -*- coding: utf-8 -*-
from tornado.web import url
import auth
import welcome
import supplier
import finance
import marked_supplier
import submitted_supplier
import supplier_pool
from tornado.options import options

handlers = [
    url(r'/',                               welcome.Index,                      name='welcome.index'),

    url(r'/login',                          auth.Login,                         name='login'),
    url(r'/logout',                         auth.Logout,                        name='logout'),

    url(r'/supplier',                       supplier.List,                      name='supplier.list'),
    url(r'/supplier/goods',                 supplier.Goods,                     name='supplier.goods'),
    url(r'/supplier/sequence',              supplier.Sequence,                  name='supplier.sequence'),
    url(r'/supplier/(\d+)/detail',          supplier.Detail,                    name='supplier.detail'),

    url(r'/supplier/marked/list',           marked_supplier.List,               name='supplier.marked.list'),
    url(r'/supplier/marked/edit',           marked_supplier.Edit,               name='supplier.marked.edit'),
    url(r'/supplier/marked/delete',         marked_supplier.Delete,             name='supplier.marked.delete'),
    url(r'/supplier/marked/add',            marked_supplier.Add,                name='supplier.marked.add'),

    url(r'/supplier/submitted/list',        submitted_supplier.List,            name='supplier.submitted.list'),
    url(r'/supplier/submitted/edit',        submitted_supplier.Edit,            name='supplier.submitted.edit'),
    url(r'/supplier/submitted/detail',      submitted_supplier.Detail,          name='supplier.submitted.detail'),
    url(r'/supplier/submitted/add',         submitted_supplier.Add,             name='supplier.submitted.add'),
    url(r'/supplier/submitted/upload',      submitted_supplier.Upload,          name='supplier.submitted.upload'),
    url(r'/contract/o/(.*)',                submitted_supplier.ContractImage,   name='supplier.contract_image',
        kwargs={'path': options.upload_img_path_contract}),

    url(r'/supplier/pool/list',             supplier_pool.List,                 name='supplier.pool.list'),

    url(r'/finance/supplier-money',         finance.SupplierMoney,              name='finance.supplier.money'),
    url(r'/finance/sequence',               finance.Sequence,                   name='finance.sequence'),
    url(r'/finance/withdraw',               finance.WithdrawList,               name='finance.withdraw.list'),
    url(r'/finance/withdraw/apply',         finance.WithdrawApply,              name='finance.withdraw.apply'),
]

