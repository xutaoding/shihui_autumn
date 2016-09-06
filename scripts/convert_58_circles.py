#! usr/bin/python 
#-*- coding:utf-8 -*-
import json
import sys

areas = json.loads(open('areas.txt').read())
circles = json.loads(open('circles.txt').read())

cities = [
        { 'name': '哈尔滨', 'id':10},
        { 'name': '北京', 'id':2},
        { 'name': '上海', 'id':4},
        { 'name': '天津', 'id':5},
        { 'name': '苏州', 'id':21},
        { 'name': '南京', 'id':29},
        { 'name': '杭州', 'id':35},
        { 'name': '成都', 'id':36},
        { 'name': '宁波', 'id':205},
        { 'name': '无锡', 'id':361},
        { 'name': '常州', 'id':64},
        { 'name': '广州', 'id':7},
        { 'name': '深圳', 'id':11},
        { 'name': '南通', 'id':208},
    ]
city_map = dict([(item['id'], item) for item in cities])
area_map = {}
for area in areas:
    if area['cityId'] not in city_map:
        continue
    city = city_map[area['cityId']]
    a = {'id': area['areaId'], 'name': area['areaName']}
    area_map[a['id']]=a
    if 'children' not in city:
        city['children'] = []
    city['children'].append(a)


for circle in circles:
    if circle['areaId'] not in area_map:
        continue
    area = area_map[circle['areaId']]
    c = {'id': circle['circleId'], 'name': circle['circleName']}
    if 'children' not in area:
        area['children'] = []
    area['children'].append(c)

for city in cities:
    if 'children' in city:
        city['nocheck'] = True
        for area in city['children']:
            if 'children' in area:
                area['nocheck'] = True

print json.dumps(cities)
