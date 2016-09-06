# -*- coding: utf-8 -*-
import hashlib
import base64
from autumn.api import BaseAPI
from datetime import datetime
from Crypto.Cipher import DES
from autumn.utils import des_padding, des_unpadding
import xml.etree.ElementTree as ET
from tornado.options import options


class Huanlegu(BaseAPI):
    def __init__(self, method):
        super(Huanlegu, self).__init__()
        self.method = method

    def http_method(self):
        return 'POST'

    def url(self):
        return options.hlg_url + self.method + '/'

    def before_request(self):
        body = u''.join([u'<{0}>{1}</{0}>'.format(key, self._fields[key]) for key in self._fields])
        now = datetime.now()
        serial = now.strftime('%Y%m%d%H%M%S%f')

        body = request_xml % {
            'version':      '1',
            'sequenceId':   serial,
            'distributorId': options.hlg_distributor_id,
            'clientId':     options.hlg_client_id,
            'timeStamp':    now.strftime('%Y-%m-%d %H:%M:%S'),
            'sign':         sign(serial, body, options.hlg_distributor_id, options.hlg_client_id),
            'body':         encrypt(body, options.hlg_secret_key)
        }
        self._fields = {'xmlContent': body}

    def parse_response(self, response):
        xml = ET.fromstring(response)
        head = xml.find('Head')
        sequence_id = head.findtext('SequenceId')
        signed = head.findtext('Signed')

        self.status_code = head.findtext('StatusCode')

        raw_content = xml.findtext('Body')
        if raw_content and self.is_ok():
            decrypted = decrypt(raw_content, options.hlg_secret_key)
            if sign(sequence_id, decrypted, options.hlg_distributor_id, options.hlg_client_id) == signed:
                self.message = ET.fromstring('<Body>%s</Body>' % decrypted)
        else:
            self.message = None

    def is_ok(self):
        return self.status_code == '200'


def encrypt(content, secret_key):
    content = content.encode('utf-8')
    cipher = DES.new(secret_key)
    return base64.b64encode(cipher.encrypt(des_padding(content)).encode('hex'))


def decrypt(content, secret_key):
    content = content.encode('utf-8')
    cipher = DES.new(secret_key)
    return des_unpadding(cipher.decrypt(base64.b64decode(content).decode('hex')))


def sign(serial, content, distributor_id, client_id):
    md5 = hashlib.md5(serial + distributor_id + client_id + str(len(content))).digest().encode('hex')
    return base64.b64encode(md5)

request_xml = u'''\
<?xml version="1.0" encoding="UTF-8"?>
<Trade>
    <Head>
        <Version>%(version)s</Version>
        <SequenceId>%(sequenceId)s</SequenceId>
        <DistributorId>%(distributorId)s</DistributorId>
        <ClientId>%(clientId)s</ClientId>
        <TimeStamp>%(timeStamp)s</TimeStamp>
        <Signed>%(sign)s</Signed>
    </Head>
    <Body>%(body)s</Body>
</Trade>'''