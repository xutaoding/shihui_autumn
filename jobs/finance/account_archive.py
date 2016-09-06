# -*- coding: utf-8 -*-
import sys
from autumn import const
import torndb
from conf import load_app_options
from tornado.options import options
import datetime


def do_job(today, yestoday):
    db = torndb.Connection(
        host=options.mysql_host, database=options.mysql_database,
        user=options.mysql_user, password=options.mysql_password)

    # 取得所有的结算商户帐号
    accounts = db.query('select * from account where account_type=%s or account_type=%s', 'SUPPLIER', 'SUPPLIER_SHOP')
    #查询所有今天之前的的account_sequence，按照类型(除了提现)进行归档
    for account in accounts:
        account_sequences = db.query(
            'select id,account_id, sum(amount) amount, type, created_at '
            'from account_sequence where account_id = %s and type <> %s and '
            'account_archive_id is null and created_at >= %s and created_at < %s group by type',
            account.id, const.seq.WITHDRAW, yestoday, today)

        for sequence in account_sequences:
            archive_done = db.query(
                'select * from account_archive where status=0 and account_id =%s and type = %s and '
                'created_at >= %s and created_at < %s ', account.id, sequence.type, yestoday, today)
            #防止重复执行的条件
            if len(archive_done) > 0:
                continue

            #进行归档
            archive_id = db.execute(
                'insert into account_archive (type,account_id,amount,status,archive_date,created_at) '
                'values(%s,%s,%s,%s,%s,now())', sequence.type, account.id, sequence.amount, '0', yestoday)
            #标记sequence中前一天归档的记录
            db.execute('update account_sequence set account_archive_id =%s '
                       'where account_id =%s and created_at >= %s and created_at < %s ',
                       archive_id, account.id, yestoday, today)

    db.close()


if __name__ == '__main__':
    load_app_options()  # 加载配置
    args = sys.argv[1:]
    #现在时间today，开始时间yestoday
    if len(args) == 0:
        today = datetime.date.today()
        yestoday = today - datetime.timedelta(days=1)
    else:
        today = args[1]
        yestoday = args[0]

do_job(today, yestoday)
