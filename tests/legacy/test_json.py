# -*- coding: utf-8 -*-

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import unittest
from json import loads
from logging import log

import pytest
from six.moves.urllib.error import HTTPError
from six.moves.urllib.parse import urlencode
from six.moves.urllib.request import urlopen

url = "http://localhost:8001/api/%s"

@pytest.mark.skip(reason='Broken legacy tests')
class TestJson(unittest.TestCase):

    def call(self, name, post=None):
        if not post: post = {}
        post["session"] = self.key
        u = urlopen(url % name, data=urlencode(post))
        return loads(u.read())

    def setUp(self):
        u = urlopen(url % "login", data=urlencode({"username": "TestUser", "password": "pwhere"}))
        self.key = loads(u.read())
        assert self.key is not False

    def test_wronglogin(self):
        u = urlopen(url % "login", data=urlencode({"username": "crap", "password": "wrongpw"}))
        assert loads(u.read()) is False

    def test_access(self):
        try:
            urlopen(url % "getServerVersion")
        except HTTPError as e:
            assert e.code == 403
        else:
            assert False

    def test_status(self):
        ret = self.call("statusServer")
        log(1, str(ret))
        assert "pause" in ret
        assert "queue" in ret

    def test_unknown_method(self):
        try:
            self.call("notExisting")
        except HTTPError as e:
            assert e.code == 404
        else:
            assert False
