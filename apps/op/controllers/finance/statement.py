# -*- coding: utf-8 -*-
from .. import BaseHandler
from .. import require
import StringIO
from xlwt import Workbook
from autumn.api.wuba import Wuba
from tornado.gen import coroutine
from autumn.utils import json_dumps, PropDict
from autumn.torn.form import Form, Date
from voluptuous import Schema
from datetime import datetime, timedelta
import logging


list_schema = Schema({
    'start_date': Date('%Y-%m-%d'),
    'end_date': Date('%Y-%m-%d'),
}, extra=True)


class Show(BaseHandler):
    """对账单首页"""
    @require()
    def get(self):
        form = Form(self.request.arguments, list_schema)
        self.render('finance/statement.html', form=form, error=None)

    @require('finance')
    @coroutine
    def post(self):
        form = Form(self.request.arguments, list_schema)

        start = form.start_date.value
        end = form.end_date.value
        if not start or not end:
            self.render('finance/statement.html', form=form, error='请输入查询日期')
            return
        start_date = datetime.strptime(start, '%Y-%m-%d')
        end_date = datetime.strptime(end, '%Y-%m-%d')
        durations = (end_date - start_date).days
        if durations > 60:
            self.render('finance/statement.html', form=form, error='最大支持60天查询，建议缩小查询区间，提高数据生成速度')
            return

        result = []
        goods_link_ids = []
        # 包含首尾
        for i in range(durations+1):
            attempts = 0
            # 一个请求重试3次
            while attempts < 3:
                wb = Wuba('queryjiesuan')
                d = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
                request_params = {'jiesuantime': d}
                response = yield wb(**request_params)
                wb.parse_response(response.body)
                if wb.is_ok():
                    if wb.message.data.jiesuanDetails:
                        for item in wb.message.data.jiesuanDetails:
                            item.update({'jiesuandate': d})
                            result.append(item)
                            goods_link_ids.append(str(item.get('groupid3')))
                    break
                else:
                    attempts += 1
                if attempts == 3:
                    result.append({'jiesuandate': d, 'orderid58': '当日查询结果异常，建议单独重新查询', 'groupprice': '',
                                   'commission': '', 'jiesuanmoney': '', 'usetime': ''})
        if result and goods_link_ids:
            # 下载
            title = [u'结算日期', u'外部订单号', u'验证/发货日期', u'商品名称', u'业务发生金额', u'佣金', u'实际结算金额']
            self.set_header('Content-type', 'application/excel')
            self.set_header('Content-Disposition', u'attachment; filename='+u'58对账单' + start + u'到' + end + u'.xls')
            wuba_excel = Workbook(encoding='utf-8')
            write_wuba_excel = wuba_excel.add_sheet('0')

            for index, content in enumerate(title):
                write_wuba_excel.write(0, index, content)

            range_list = ['jiesuandate', 'orderid58', 'usetime', 'goods_name', 'groupprice', 'commission', 'jiesuanmoney']
            goods_names = self.db.query('select goods_link_id glid, short_name name '
                                        'from goods g, goods_distributor_shop gds '
                                        'where g.id=gds.goods_id and gds.goods_link_id in '
                                        '(' + ','.join(set(goods_link_ids)) + ')')

            name_dict = PropDict([(i.glid, i.name) for i in goods_names])

            for i, item in enumerate(result):
                for j, content in enumerate(range_list):
                    v = item.get(content, '')
                    v = v if v else ''
                    if content == 'usetime':
                        v = str(v)
                    elif content == 'commission':
                        if not v:
                            v = 0
                    elif content == 'orderid58':
                        v = str(v)
                    elif content == 'goods_name':
                        v = name_dict.get(item.get('groupid3'))

                    write_wuba_excel.write(i + 1, j, v)

            stream = StringIO.StringIO()
            wuba_excel.save(stream)
            self.write(stream.getvalue())
        else:
            self.render('finance/statement.html', form=form, error='该期间没有结算数据')


