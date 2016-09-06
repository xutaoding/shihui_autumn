# -*- coding: utf-8 -*-
from decimal import Decimal

import torndb
import logging
from datetime import datetime, timedelta
from conf import load_app_options
from tornado.options import options
from tornado.template import Template
from autumn.utils import PropDict

BASE_PRICE = 3888


def gen_account_sequence():
    # 配置连接
    db = torndb.Connection(
        host=options.mysql_host, database=options.mysql_database,
        user=options.mysql_user, password=options.mysql_password)

    agents = db.query('select ag.*, ac.id account_id from agent ag, account ac '
                      'where ag.id=ac.uid and ac.type=3 and ag.type=2 and ag.deleted=0')
    today = datetime.today()
    this_month_start = datetime(today.year, today.month, 1)
    next_month_start = datetime(this_month_start.year if this_month_start.month != 12 else this_month_start.year+1,
                                this_month_start.month if this_month_start.month != 12 else 1, 1)
    previous_month_start = this_month_start + timedelta(days=-1)
    previous_month_start = datetime(previous_month_start.year, previous_month_start.month, 1)
    two_months_ago_start = previous_month_start + timedelta(days=-1)
    two_months_ago_start = datetime(two_months_ago_start.year, two_months_ago_start.month, 1)

    for agent in agents:
        this_month_seq = db.get('select count(1) c from account_sequence s, account a where s.account_id = a.id '
                                'and a.type=3 and a.uid=%s and created_at>=%s and created_at <%s',
                                agent.id, this_month_start, next_month_start)
        if this_month_seq.c > 0:
            logging.info('')
            continue

        # 上月卖出信息
        previous_month_info = db.query(db, agent.id, previous_month_start, this_month_start)
        two_months_ago_info = db.query(db, agent.id, two_months_ago_start, previous_month_start)

        db.execute('insert into account_sequence(type, account_id, created_at, amount, remark, status) '
                   'values (6, %s, NOW(), %s, %s, 1), (6, %s, NOW(), %s, %s, 1)',
                   agent.account_id, previous_month_info.total_amount*Decimal('0.7'),
                   Template("""\
{{info.month_info}} 微信套餐费用共 {{ info.total_amount}} x 0.7 = {{ info.total_amount*Decimal('0.7')}} 元。\
当月共卖出 {{info.count}} 份套餐，相应结算单价为 {{ info.price }} 元， \
{{info.count}} x {{info.price}} = {{info.count*info.price}} 元。 溢价销售 {{ info.premium_amount }} \
元， 溢价部分提 70% 得 {{info.premium_amount*Decimal('0.7')}} 元。""").generate(info=previous_month_info),
                   agent.account_id, two_months_ago_info.total_amount*Decimal('0.3'),
                   Template("""\
{{info.month_info}} 微信套餐费用共 {{ info.total_amount}} x 0.3 = {{ info.total_amount*Decimal('0.3')}} 元。\
当月共卖出 {{info.count}} 份套餐，相应结算单价为 {{ info.price }} 元， \
{{info.count}} x {{info.price}} = {{info.count*info.price}} 元。 溢价销售 {{ info.premium_amount }} \
元， 溢价部分提 70% 得 {{info.premium_amount*Decimal('0.7')}} 元。""").generate(info=two_months_ago_info),
                   )

    db.close()


def cal_money(db, agent_id, start_day, end_day):
    sale_info = db.query("""
        select count(1) `count`, sum(amount) amount
        from external_money em, supplier s
        where em.uid=s.id and em.type=1 and em.source=3
        and s.agent_id=%s and em.created_at >=%s and em.created_at < %s
    """, agent_id, start_day, end_day)

    if sale_info.count < 50:
        price = 2880
    elif sale_info.count < 100:
        price = 2580
    else:
        price = 1980

    result = PropDict({
        'price': price,
        'count': sale_info.count,
        'base_amount': Decimal(BASE_PRICE-price)*sale_info.count,
        'premium_amount': max(sale_info.amount-Decimal(BASE_PRICE)*sale_info.count, Decimal(0)),
        'month_info': start_day.strftime('%Y年%m月')
    })
    result['total_amount'] = result['base_amount']+result['premium_amount']*Decimal('0.7')
    return result


if __name__ == '__main__':
    # 加载配置
    load_app_options()

    # 配置日志
    logging.basicConfig(level=logging.INFO,
                        format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')

    logging.info('start generate agent account_sequence')
    gen_account_sequence()
