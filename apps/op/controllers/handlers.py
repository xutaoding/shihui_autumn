# -*- coding: utf-8 -*-
from . import PageNotFoundHandler
from tornado.web import url
from tornado.options import options
import auth
import coupon.show
import coupon.verify
import coupon.refund
import coupon.freeze
import coupon.imported
import coupon.export
import order.show
import order.imported
import coupon.delay
import goods.goods
import goods.distributor
import goods.yihaodian
import goods.jd
import goods.taobao
import goods.wuba
import goods.status
import welcome
import supplier.admin
import supplier.fee
import supplier.shop
import supplier.user
import supplier.bank
import supplier.ktv
import supplier.contract
import distributor.admin
import distributor.shop
import real.stock
import real.order
import common
import real.sku
import real.order_shipping
import real.sku_take_out
import real.stock_batch
import real.return_entry
import real.trackno
import report.sales_personal
import report.index
import seewi.news
import seewi.recommend
import seewi.express
import seewi.freight
import seewi.notice
import finance.external_money
import finance.withdraw
import finance.profit
import finance.goods_report
import finance.sequence
import finance.agent
import operator.admin
import mock
import admin.notice
import finance.statement
import temple.redis_mgr
import agent
import agent.contract
import temple.wx

handlers = [
    url(r'/login',                          auth.Login,                         name='login'),
    url(r'/logout',                         auth.Logout,                        name='logout'),
    url(r'/',                               welcome.Welcome,                    name='welcome'),
    url(r'/quick-search',                   welcome.QuickSearch,                name='quick_search'),

    # 电子券
    url(r'/coupon',                         coupon.show.CouponList,             name='coupon.show_list'),
    url(r'/coupon/(\d+)',                   coupon.show.CouponDetail,           name='coupon.show_detail'),
    url(r'/coupon/verify',                  coupon.verify.CouponVerify,         name='coupon.verify'),
    url(r'/coupon/verify-query',            coupon.verify.CouponVerifyQuery,    name='coupon.verify_query'),
    url(r'/coupon/virtual-verify',          coupon.verify.VirtualVerify,        name='coupon.virtual_verify'),
    url(r'/coupon/coupon-refund',           coupon.refund.Unconsumed,           name='coupon.unconsumed_refund'),
    url(r'/coupon/verified-coupon-refund',  coupon.refund.VerifiedRefund,       name='coupon.verified_refund'),
    url(r'/coupon/refund-query',            coupon.refund.RefundQuery,          name='coupon.refund_query'),
    url(r'/coupon/freeze',                  coupon.freeze.CouponFreeze,         name='coupon.freeze'),
    url(r'/coupon/imported',                coupon.imported.Import,             name='coupon.imported'),
    url(r'/coupon/imported/(\d+)',          coupon.imported.ImportCoupon,       name='coupon.import_coupon'),
    url(r'/coupon/imported/jd',             coupon.imported.JDImportCoupon,     name='coupon.imported_jd'),
    url(r'/coupon/delay',                   coupon.delay.DelayList,             name='coupon.delay'),
    url(r'/coupon/export',                  coupon.export.SelectDistributor,    name='coupon.export'),
    url(r'/coupon/export/download',         coupon.export.Download,             name='coupon.download'),
    url(r'/coupon/journal',                 coupon.show.Journal,                name='coupon.journal'),
    url(r'/coupon/resend',                  coupon.show.ResendSn,               name='coupon.resend'),
    url(r'/coupon/distributor-verify',      coupon.verify.DistributorVerify,    name='coupon.distributor_verify'),

    # 分销商

    url(r'/distributor',                    distributor.admin.List,             name='distributor.show_list'),
    url(r'/distributor/add',                distributor.admin.Add,              name='distributor.add'),
    url(r'/distributor/edit',               distributor.admin.Edit,             name='distributor.edit'),
    url(r'/distributor/shop',               distributor.shop.List,              name='distributor.show_shop_list'),
    url(r'/distributor/shop/add',           distributor.shop.Add,               name='distributor.shop_add'),
    url(r'/distributor/shop/edit',          distributor.shop.Edit,              name='distributor.shop_edit'),

    # 代理商
    url(r'/agent',                          agent.List,                         name='agent.list'),
    url(r'/agent/add',                      agent.Add,                          name='agent.add'),
    url(r'/agent/(\d+)/edit',               agent.Edit,                         name='agent.edit'),
    url(r'/agent/delete',                   agent.Delete,                       name='agent.delete'),
    url(r'/agent/(\d+)/detail',             agent.Detail,                       name='agent.detail'),
    url(r'/agent/contract',                 agent.contract.List,                name='agent.contract'),
    url(r'/agent/contract/add',             agent.contract.Add,                 name='agent.contract.add'),
    url(r'/agent/contract/(\d+)/edit',      agent.contract.Edit,                name='agent.contract.edit'),
    url(r'/agent/contract/delete',          agent.contract.Delete,              name='agent.contract.delete'),
    url(r'/agent/contract/upload/(\d+)',    agent.contract.Upload,              name='agent.contract.upload'),
    url(r'/agent/contract/(\d+)/detail',    agent.contract.Detail,              name='agent.contract.detail'),

    #运营
    url(r'/operator',                       operator.admin.List,                name='operator.show_list'),
    url(r'/operator/add',                   operator.admin.Add,                 name='operator.add_user'),
    url(r'/operator/edit',                  operator.admin.Edit,                name='operator.edit_user'),
    url(r'/operator/delete',                operator.admin.Delete,              name='operator.delete'),

    # 商户

    url(r'/supplier',                       supplier.admin.List,                name='supplier.show_list'),
    url(r'/supplier/(\d+)',                 supplier.admin.Detail,              name='supplier.detail'),
    url(r'/supplier/add',                   supplier.admin.Add,                 name='supplier.add'),
    url(r'/supplier/edit',                  supplier.admin.Edit,                name='supplier.edit'),
    url(r'/supplier/delete',                supplier.admin.Delete,              name='supplier.delete'),
    url(r'/supplier/max_withdraw/edit',     supplier.admin.MaxWithdrawEdit,     name='supplier.max_withdraw.edit'),
    url(r'/supplier/wx/commission',         supplier.admin.WeixinCommission,    name='supplier.wx.commission'),
    url(r'/supplier/wx/shop',               supplier.admin.WeixinShopMax,       name='supplier.wx.shop'),

    url(r'/supplier/ads-fee',               supplier.fee.FeeList,               name='supplier.show_ads_fee'),
    url(r'/supplier/ads-fee/delete',        supplier.fee.FeeDelete,             name='supplier.delete_ads_fee'),
    url(r'/supplier/ads-fee/add',           supplier.fee.FeeAdd,                name='supplier.add_ads_fee'),

    url(r'/supplier/(\d+)/shop',            supplier.shop.List,                 name='supplier.shop'),
    url(r'/supplier/shop/add',              supplier.shop.Add,                  name='supplier.shop.add'),
    url(r'/supplier/shop/edit',             supplier.shop.Edit,                 name='supplier.shop.edit'),
    url(r'/supplier/shop/delete',           supplier.shop.Delete,               name='supplier.shop.delete'),
    url(r'/supplier/shop/(\d+)',            supplier.shop.Detail,               name='supplier.shop.detail'),

    url(r'/supplier/(\d+)/user',            supplier.user.List,                 name='supplier.user'),
    url(r'/supplier/user/add',              supplier.user.Add,                  name='supplier.user.add'),
    url(r'/supplier/user/edit',             supplier.user.Edit,                 name='supplier.user.edit'),
    url(r'/supplier/user/delete',           supplier.user.Delete,               name='supplier.user.delete'),
    url(r'/supplier/user/reset-pwd',        supplier.user.ResetPwd,             name='supplier.user.reset_pwd'),

    url(r'/supplier/(\d+)/bank',            supplier.bank.List,                 name='supplier.bank'),
    url(r'/supplier/bank/add',              supplier.bank.Add,                  name='supplier.bank_add'),
    url(r'/supplier/bank/edit',             supplier.bank.Edit,                 name='supplier.bank_edit'),
    url(r'/supplier/bank/delete',           supplier.bank.Delete,               name='supplier.bank_delete'),

    url(r'/supplier/(\d+)/ktv',             supplier.ktv.Show,                  name='supplier.ktv'),
    url(r'/supplier/ktv/add',               supplier.ktv.Add,                   name='supplier.add_ktv'),
    url(r'/supplier/ktv/(\d+)/edit',        supplier.ktv.Edit,                  name='supplier.edit_ktv'),
    url(r'/supplier/ktv/delete',            supplier.ktv.Delete,                name='supplier.delete_ktv'),

    url(r'/supplier/(\d+)/contract',        supplier.contract.List,             name='supplier.contract'),
    url(r'/supplier/contract/add',          supplier.contract.Add,              name='supplier.contract_add'),
    url(r'/supplier/contract/upload/(\d+)', supplier.contract.Upload,           name='supplier.contract_upload'),
    url(r'/supplier/contract/edit',         supplier.contract.Edit,             name='supplier.contract_edit'),
    url(r'/supplier/contract/detail/(\d+)', supplier.contract.Detail,           name='supplier.contract_detail'),
    url(r'/supplier/contract/delete',       supplier.contract.Delete,           name='supplier.contract_delete'),
    url(r'/contract/o/(.*)',                supplier.contract.ContractImage,    name='supplier.contract_image',
        kwargs={'path': options.upload_img_path_contract}),

    url(r'/supplier/(\d+)/manual',          supplier.admin.Manual,              name='supplier.manual'),

    # 商品

    url(r'/goods',                          goods.goods.GoodsList,              name='goods.show_list'),
    url(r'/goods/(\d+)',                    goods.goods.GoodsDetail,            name='goods.show_detail'),
    url(r'/goods/copy',                     goods.goods.GoodsCopy,              name='goods.copy'),
    url(r'/goods/add',                      goods.goods.GoodsAdd,               name='goods.add'),
    url(r'/goods/edit',                     goods.goods.GoodsEdit,              name='goods.edit'),
    url(r'/goods/delete',                   goods.goods.GoodsDelete,            name='goods.delete'),
    url(r'/goods/(\d+)/history',            goods.goods.GoodsHistory,           name='goods.history'),
    url(r'/goods/(\d+)/history/detail',     goods.goods.HistoryDetail,          name='goods.history.detail'),
    url(r'/goods/distributor',              goods.distributor.ShowList,         name='goods.distributor.show_list'),
    url(r'/goods/distributor/products',     goods.distributor.ShowProducts,     name='goods.distributor.show_products'),
    url(r'/goods/distributor/del',          goods.distributor.Hide,             name='goods.distributor.hide'),
    url(r'/goods/distributor/relation',     goods.distributor.RelationProduct,  name='goods.distributor.relation'),
    url(r'/goods/approve',                  goods.goods.Approve,                name='goods.approve'),
    url(r'/goods/status/on-sale',           goods.status.OnSale,                name='goods.status.on_sale'),

    #       一号店推送
    url(r'/goods/push/yhd/(\d+)',           goods.yihaodian.ShowCategory,       name='goods.yhd.show_category'),
    url(r'/goods/push/yhd/edit',            goods.yihaodian.Edit,               name='goods.yhd.edit'),
    url(r'/goods/push/yhd',                 goods.yihaodian.Push,               name='goods.yhd.push'),
    url(r'/goods/push/yhd/img',             goods.yihaodian.UploadImg,          name='goods.yhd.push.img'),
    url(r'/goods/push/yhd/category',        goods.yihaodian.CategoryAjax,       name='goods.yhd.category.ajax'),
    url(r'/goods/push/yhd/mcategory',       goods.yihaodian.MerchantCategory,   name='goods.yhd.category.merchant'),

    #       京东推送
    url(r'/goods/push/jdb/(\d+)',           goods.jd.Push,                      name='goods.jd.jdb.push'),
    url(r'/goods/push/jd/(\d+)',            goods.jd.Push,                      name='goods.jd.push'),
    url(r'/goods/push/jd/city',             goods.jd.CityAjax,                  name='goods.jd.city.ajax'),
    url(r'/goods/push/jd/category',         goods.jd.CategoryAjax,              name='goods.jd.category.ajax'),
    url(r'/goods/push/jd/edit',             goods.jd.Edit,                      name='goods.jd.edit'),

    #       淘宝推送
    url(r'/goods/push/tb/(\d+)',            goods.taobao.ShowCategory,          name='goods.taobao.category'),
    url(r'/goods/push/tm/(\d+)',            goods.taobao.ShowCategory,          name='goods.taobao.category.tmall'),
    url(r'/goods/push/tb/edit',             goods.taobao.TBEdit,                name='goods.taobao.edit_taobao'),
    url(r'/goods/push/tm/edit',             goods.taobao.TMEdit,                name='goods.taobao.edit_tmall'),
    url(r'/goods/push',                     goods.taobao.Push,                  name='goods.taobao.push'),
    url(r'/goods/push/tb/upload-img',       goods.taobao.UploadMajorImage,      name='goods.taobao.upload_img'),
    url(r'/goods/push/tb/upload-detail-img',goods.taobao.UploadTaobaoImage,     name='goods.taobao.upload_detail_img'),
    url(r'/goods/push/tb/category',         goods.taobao.CategoryAjax,          name='goods.taobao.category.ajax'),
    url(r'/goods/push/picture',             goods.taobao.PictureReplace,        name='goods.taobao.picture.replace'),

    #       wuba推送
    url(r'/goods/push/wb/(\d+)',            goods.wuba.Show,                    name='goods.wb.show'),
    url(r'/goods/push/wb',                  goods.wuba.Push,                    name='goods.wb.push'),
    url(r'/goods/push/wb/category',         goods.wuba.CategoryAjax,            name='goods.wb.category.ajax'),
    url(r'/goods/push/wb/edit',             goods.wuba.Edit,                    name='goods.wb.edit'),

    # 实物

    url(r'/real/sku',                       real.sku.SkuList,                   name='real.show_sku'),
    url(r'/real/sku/add',                   real.sku.SkuAdd,                    name='real.add_sku'),
    url(r'/real/sku/edit',                  real.sku.SkuEdit,                   name='real.edit_sku'),
    url(r'/real/sku/delete',                real.sku.SkuDelete,                 name='real.delete_sku'),
    url(r'/real/stock/in',                  real.stock.StockIn,                 name='real.stock_in'),
    url(r'/real/stock/out',                 real.stock.StockOut,                name='real.stock_out'),
    url(r'/real/stock',                     real.stock.StockList,               name='real.stock_list'),
    url(r'/real/import-partner-order',      real.order.ImportPartnerOrder,      name='real.import_partner_order'),
    url(r'/real/auto-import-tb-order',      real.order.TbAutoImportOrder,       name='real.auto_import_tb_order'),
    url(r'/order-shipping',                 real.order_shipping.Show,           name='real.show_order_shipping'),
    url(r'/order-shipping/download',        real.order_shipping.Download,       name='real.download_order_shipping'),
    url(r'/order-shipping/import',          real.order_shipping.Import,         name='real.import_order_shipping'),
    url(r'/sku-take-out',                   real.sku_take_out.OrderSkuList,     name='real.order_sku_list'),
    url(r'/stock-batch',                    real.stock_batch.StockBatchList,    name='real.stock_batch_list'),
    url(r'/stock-batch/(\d+)',              real.stock_batch.StockBatchDetail,  name='real.stock_batch_detail'),
    url(r'/stock-batch-confirm',            real.stock_batch.StockBatchConfirm, name='real.stock_batch_confirm'),
    url(r'/real/return-entry',              real.return_entry.ReturnList,       name='real.return_list'),
    url(r'/real/return-entry/confirm',      real.return_entry.ReturnConfirm,    name='real.return_confirm'),
    url(r'/real/order-refund',              real.return_entry.RealGoodsRefundHandler, name='real.order_refund'),
    url(r'/real/track-no',                  real.trackno.Show,                  name='real.show_track_no'),
    url(r'/real/track-no/download',         real.trackno.Download,              name='real.download_track_no'),
    url(r'/real/return-entry/un_return',    real.return_entry.UnReturn,         name='real.un_return'),

    # 订单
    url(r'/order',                          order.show.OrderList,               name='order.show_list'),
    url(r'/order/(\d+)',                    order.show.OrderDetail,             name='order.show_detail'),
    url(r'/order/huanlegu',                 welcome.Welcome,                    name='order.hlg_entrance'),
    url(r'/order/express',                  order.show.ExpressEdit,             name='order.express_edit'),
    url(r'/order/imported',                 order.imported.OuterOrder,          name='order.imported'),


    # 财务
    url(r'/sequence/supplier',              finance.sequence.SupplierSequence,  name='finance.supplier_sequence'),
    url(r'/sequence/resale',                finance.sequence.ResaleSequence,    name='finance.resale_sequence'),
    url(r'/sequence/agent',                 finance.agent.AgentSequence,        name='finance.agent_sequence'),
    url(r'/agent/pay-list',                 finance.agent.PayList,              name='finance.agent_pay_list'),
    url(r'/agent/credit',                   finance.agent.Credit,               name='finance.agent_credit'),
    url(r'/agent/deposit',                  finance.agent.Deposit,              name='finance.agent_deposit'),
    url(r'/agent/deposit-check',            finance.agent.DepositCheck,         name='finance.agent_deposit_check'),
    url(r'/agent/add-supplier',             finance.agent.AddSupplier,          name='finance.agent_add_supplier'),
    url(r'/agent/supplier-check',           finance.agent.SupplierCheck,        name='finance.agent_supplier_check'),
    url(r'/external-money',                 finance.external_money.List,        name='finance.external_money_list'),
    url(r'/external-money/add',             finance.external_money.Add,         name='finance.add_external_money'),
    url(r'/external-money/edit',            finance.external_money.Edit,        name='finance.edit_external_money'),
    url(r'/external-money/delete',          finance.external_money.Delete,      name='finance.delete_external_money'),
    url(r'/withdraw/approval',              finance.withdraw.WithdrawApproval,  name='finance.withdraw'),
    url(r'/withdraw/download',              finance.withdraw.Download,          name='finance.withdraw.download'),
    url(r'/withdraw/(\d+)',                 finance.withdraw.Detail,            name='finance.detail'),
    url(r'/profit',                         finance.profit.Profit,              name='finance.profit'),
    url(r'/channel-goods-report',           finance.goods_report.ChannelGoods,  name='finance.channel_goods_report'),
    url(r'/statement',                      finance.statement.Show,             name='finance.statement'),

    # 报表
    url(r'/report/index',                   report.index.Show,                  name='report.index'),
    url(r'/report/tendency/supplier',       report.index.SupplierTendency,      name='report.tendency_supplier'),
    url(r'/report/tendency/goods',          report.index.GoodsTendency,         name='report.tendency_goods'),
    url(r'/report/ranking',                 report.index.Ranking,               name='report.ranking'),
    url(r'/report/prepayment',              report.index.Prepayment,            name='report.prepayment'),
    url(r'/report/sales-personal-summary',  report.sales_personal.Summary,      name='report.sales_summary'),
    url(r'/report/sales-personal-supplier', report.sales_personal.SupplierSide, name='report.sales_supplier_side'),
    url(r'/report/sales-personal-channel',  report.sales_personal.ChannelSide,  name='report.sales_channel_side'),

    # seewi
    url(r'/seewi-news',                     seewi.news.NewsList,                name='seewi.news.show_list'),
    url(r'/seewi-news/add',                 seewi.news.NewsAdd,                 name='seewi.news.add'),
    url(r'/seewi-news/edit',                seewi.news.NewsEdit,                name='seewi.news.edit'),
    url(r'/seewi-news/delete',              seewi.news.NewsDelete,              name='seewi.news.delete'),

    #一百券商品推荐
    url(r'/yibaiquan-recommend',            seewi.recommend.RecommendList,      name='yibaiquan.recommend.list'),
    url(r'/yibaiquan-recommend/add',        seewi.recommend.AddRecommend,       name='yibaiquan.recommend.add'),
    url(r'/yibaiquan-recommend/cancel',     seewi.recommend.CancelRecommend,    name='yibaiquan.recommend.cancel'),

    #向商户发送信息
    url(r'/notice/send',                    seewi.notice.Notice,                name='notice.send'),

    #快递公司
    url(r'/express',                        seewi.express.ExpressShow,          name='express.list'),
    url(r'/express/add',                    seewi.express.ExpressAdd,           name='express.add'),
    url(r'/express/(\d+)/edit',             seewi.express.ExpressEdit,          name='express.edit'),
    url(r'/express/delete',                 seewi.express.ExpressDelete,        name='express.delete'),
    url(r'/express/(\d+)/freight',          seewi.freight.Show,                 name='freight.list'),
    url(r'/express/(\d+)/freight/add',      seewi.freight.Add,                  name='freight.add'),
    url(r'/express/(\d+)/freight/(\d+)/edit',seewi.freight.Edit,                name='freight.edit'),
    url(r'/express/(\d+)/freight/delete',   seewi.freight.Delete,               name='freight.delete'),

    #行政
    url(r'/admin/notice',                   admin.notice.Show,                  name='admin.notice'),
    url(r'/admin/notice/add',               admin.notice.Add,                   name='admin.notice.add'),
    url(r'/admin/notice/(\d+)/edit',        admin.notice.Edit,                  name='admin.notice.edit'),
    url(r'/admin/notice/delete',            admin.notice.Delete,                name='admin.notice.delete'),
    url(r'/admin/notice/(\d+)/detail',      admin.notice.Detail,                name='admin.notice.detail'),

    # 通用
    url(r'/common/autocomplete/supplier',   common.AutocompleteSupplier,        name='common.autocomplete.supplier'),
    url(r'/common/autocomplete/agent',      common.AutocompleteAgent,           name='common.autocomplete.agent'),
    url(r'/common/autocomplete/sku',        common.AutocompleteSku,             name='common.autocomplete.sku'),
    url(r'/common/autocomplete/operator',   common.AutocompleteOperator,        name='common.autocomplete.operator'),
    url(r'/common/supplier/shop',           common.SupplierShops,               name='common.supplier.shop'),
    url(r'/common/goods/categories',        common.GoodsCategories,             name='common.goods.categories'),
    url(r'/common/supplier/goods',          common.SupplierGoods,               name='common.supplier.goods'),
    url(r'/common/areas',                   common.Areas,                       name='common.areas'),
    url(r'/common/ke/upload-img',           common.KindEditorUploadImage,       name='common.ke.upload_img'),

    # 模拟环境
    url(r'/mock',                           mock.Index,                         name='mock.index'),
    url(r'/mock/taobao-coupon',             mock.TaobaoCouponAPI,               name='mock.taobao_coupon'),

    # 神殿
    url(r'/temple/redis',                   temple.redis_mgr.List,              name='temple.redis'),
    url(r'/temple/redis/execute/(.+)',      temple.redis_mgr.Execute,           name='temple.redis.execute'),
    url(r'/temple/wx/setting',              temple.wx.SupplierSetting,          name='temple.wx.setting'),
    url(r'/temple/wx/binding',              temple.wx.Binding,                  name='temple.wx.binding'),

    # 404
    url(r'.*',                              PageNotFoundHandler,                name='not_found')
]
