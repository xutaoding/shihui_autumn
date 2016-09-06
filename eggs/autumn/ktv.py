# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta
import re


class TaobaoSku(object):
    week_names = ['一', '二', '三', '四', '五', '六', '日']

    room_types = ('MINI', 'SMALL', 'MIDDLE', 'LARGE', 'DELUXE')
    room_names = ('迷你包', '小包', '中包', '大包', '豪华包')
    room_keys = ('27426219:6312905', '27426219:3442354', '27426219:6769368', '27426219:3374388', '27426219:40867986')

    def __init__(self, room_type, dt, price, quantity, start_time, duration, sku_id):
        self.room_type = room_type
        self.date = dt
        self.price = price
        self.quantity = quantity
        self.start_time = start_time
        self.duration = duration
        self.sku_id = sku_id

    @property
    def room_key(self):
        return self.room_keys[self.room_types.index(self.room_type)]

    @property
    def room_name(self):
        return self.room_names[self.room_types.index(self.room_type)]

    def __eq__(self, other):
        """ 用于 set 的 + - """
        return hash(self) == hash(other)

    def __hash__(self):
        """ 用于 set 的 + - """
        return hash(self.room_type) + hash(self.date) + hash(self.start_time) * 100 + hash(self.duration)

    def __lt__(self, other):
        """ 用于 sort """
        i = self.room_types.index(self.room_type)
        j = self.room_types.index(other.room_type)
        if i < j:
            return True
        elif i == j:
            if self.date < other.date:
                return True
            elif self.date == other.date:
                return self.start_time < other.start_time
        return False

    def __str__(self):
        return '%s;%s;%s' % (self.room_type, self.human_time_range, self.human_date)

    @property
    def human_time_range(self):
        end = self.start_time + self.duration
        end = end - 24 if end >= 24 else end
        start_str = ('凌晨%s点' if self.start_time < 6 else '%s点') % self.start_time
        end_str = ('凌晨%s点' if end < 6 else '%s点') % end
        return '%s至%s' % (start_str, end_str)

    @property
    def human_date(self):
        return '%s月%s日(周%s)' % (self.date.month, self.date.day, self.week_names[self.date.weekday()])

    def parse_taobao_property(self, room_type_str, time_str, date_str):
        """
        :param room_type_str:  小包
        :param time_str: 17点至20点
        :param date_str: 12月11日(周三)
        """
        # tmp = re.split(r'[:;]', properties_name)
        self.room_type = self.room_types[self.room_names.index(room_type_str)]

        date_info = re.findall(r'\d+', date_str)
        self.date = date.today().replace(month=int(date_info[0]), day=int(date_info[1]))
        if date.today().month in (11, 12) and int(date_info[0]) in (1, 2):
            #  处理明年的情况
            self.date = self.date.replace(year=self.date.year + 1)

        time_info = re.findall(r'\d+', time_str)
        self.start_time = int(time_info[0])
        end_time = int(time_info[1])
        end_time = end_time + 24 if end_time < 6 else end_time
        self.duration = end_time - self.start_time


def build_taobao_sku(db, shop_id, product_id, push_end_hour=18, max_deploy_day=7, pre_order_hour=1):
    """
    @type db torndb.Connection

    @param db: 数据库
    @param shop_id: 门店ID
    @param product_id: KTV产品ID
    @param push_end_hour: 当天的几点之后
    @param max_deploy_day: 最多发布几天之内的KTV产品
    @param pre_order_hour: 不允许预订几个小时之内的SKU
    @return:
    """
    max_sku_count = 600
    now = datetime.now()

    today = start_day = date.today()
    if now.hour >= push_end_hour:
        start_day += timedelta(days=1)

    # 找出与指定的产品和店铺相匹配的价格策略
    schedules = db.query("""
        select kdr.*, kps.room_type, kps.product_id, kps.start_times, kps.duration, ks.room_count, kps.price
        from ktv_date_range kdr, ktv_price_schedule kps, ktv_shop ks
        where kdr.schedule_id=kps.id
            and kps.product_id=%s
            and kps.id = ks.schedule_id
            and ks.shop_id=%s
            and kdr.end_day >= %s
        order by kdr.start_day
        """, product_id, shop_id, start_day)

    date_tiled_schedules = []
    days = []
    for i in range(max_deploy_day):
        #  将 max_deploy_day 天之内的价格策略，按照日期的先后顺序平铺展开
        day = start_day + timedelta(days=i)
        days.append(day)
        schedule_list = []
        for date_range in schedules:
            if date_range.start_day <= day <= date_range.end_day:
                schedule_list.append(date_range)
        date_tiled_schedules.append((day, schedule_list))

    # 查出这个门店的销售订单
    orders = db.query(
        'select * from ktv_order where shop_id=%s and product_id=%s '
        'and (status="DEAL" or (status="LOCK" and created_at>=%s) ) '
        'and scheduled_day in (' + ','.join(['%s'] * len(days)) + ')',
        shop_id, product_id, now - timedelta(minutes=10), *days)
    date_orders = {}
    for order in orders:
        if order.scheduled_day not in date_orders:
            date_orders[order.scheduled_day] = []
        date_orders[order.scheduled_day].append(order)

    room_types = set()
    dates = set()
    time_ranges = set()

    sku_list = []
    for day, schedule_list in date_tiled_schedules:
        for schedule in schedule_list:
            dates.add(day)
            if len(room_types) * len(dates) * len(time_ranges) > max_sku_count:
                break  # 因为日期是顺序排列的，所以一旦有此情况，直接退出循环
            room_types.add(schedule.room_type)
            if len(room_types) * len(dates) * len(time_ranges) > max_sku_count:
                room_types.pop(schedule.room_type)
                continue
            for start_time in [int(i) for i in schedule.start_times.split(',')]:
                if day == today and start_time <= now.hour + pre_order_hour:
                    continue  # 今天 pre_order_hour 小时之内的不能预订
                t = '-'.join(map(str, [start_time, start_time + schedule.duration]))
                time_ranges.add(t)
                if len(room_types) * len(dates) * len(time_ranges) > max_sku_count:
                    time_ranges.pop(t)
                    continue

                # 判断剩余房间数
                room_count_left = schedule.room_count
                if day in date_orders:
                    for order in date_orders[day]:
                        if order.room_type != schedule.room_type:
                            continue
                        st = start_time + 24 if start_time < 8 else start_time
                        ost = order.scheduled_time + 24 if order.scheduled_time < 8 else order.scheduled_time
                        if ost < (st + schedule.duration) and (ost + schedule.duration) > st:
                            room_count_left -= 1
                    if room_count_left <= 0:
                        continue

                # 生成sku
                sku_list.append(TaobaoSku(
                    room_type=schedule.room_type,
                    dt=day,
                    price=schedule.price,
                    quantity=room_count_left,
                    start_time=start_time,
                    duration=schedule.duration,
                    sku_id=0
                ))
    return sku_list


def diff_local_and_remote(local_sku_list, remote_sku_list):
    """
    传过来本地和远端的SKU列表

    比较两组SKU，得出四个列表，分别是：
    add: 应该添加到淘宝的SKU列表
    delete: 应该删除的淘宝SKU列表
    updatePrice: 应该更新价格的淘宝SKU列表
    updateQuantity: 应该更新数量的淘宝SKU列表（可批量更新）

    @type remote_sku_list list of TaobaoSku
    @type local_sku_list list of TaobaoSku
    """
    local_sku_set = set(local_sku_list)
    remote_sku_set = set(remote_sku_list)

    add_sku_list = sorted(list(local_sku_set - remote_sku_set))
    delete_sku_list = list(remote_sku_set - local_sku_set)
    update_price_sku_list = []
    update_quantity_sku_list = []

    for local_sku, remote_sku in zip(sorted(list(local_sku_set-(local_sku_set-remote_sku_set))),
                                     sorted(list(remote_sku_set-(remote_sku_set-local_sku_set)))):
        if local_sku.price != remote_sku.price:
            remote_sku.price = local_sku.price
            remote_sku.quantity = local_sku.quantity
            update_price_sku_list.append(remote_sku)
        elif local_sku.quantity != remote_sku.quantity:
            remote_sku.quantity = local_sku.quantity
            update_quantity_sku_list.append(remote_sku)

    return add_sku_list, delete_sku_list, update_price_sku_list, update_quantity_sku_list

