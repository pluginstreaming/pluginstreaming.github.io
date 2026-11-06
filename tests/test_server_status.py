# -*- coding: utf-8 -*-
"""Testes para a classificação de disponibilidade dos servidores FILMOM."""

from __future__ import absolute_import, unicode_literals

import base64
import os
import sys
import types
import unittest
import urllib.error
from unittest import mock


ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugin.video.filmom"))
sys.path.insert(0, ADDON_ROOT)


class StubAddon(object):
    def __init__(self, _addon_id):
        pass


sys.modules.setdefault("xbmc", types.ModuleType("xbmc"))
sys.modules["xbmc"].LOGWARNING = 2
sys.modules["xbmc"].LOGDEBUG = 0
sys.modules["xbmc"].LOGERROR = 4
sys.modules["xbmc"].log = lambda *_args, **_kwargs: None

xbmcaddon = types.ModuleType("xbmcaddon")
xbmcaddon.Addon = StubAddon
sys.modules.setdefault("xbmcaddon", xbmcaddon)
sys.modules.setdefault("xbmcgui", types.ModuleType("xbmcgui"))
sys.modules.setdefault("xbmcvfs", types.ModuleType("xbmcvfs"))

from resources.lib import xtream  # noqa: E402


class FakeResponse(object):
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


def server(password="secret", username="filmom"):
    encoded_password = "b64:" + base64.urlsafe_b64encode(password.encode("utf-8")).decode("ascii") if password else ""
    return {
        "name": "Servidor 1",
        "number": "1",
        "url": "http://media.example.test",
        "username": username,
        "password": encoded_password,
    }


class ServerStatusTests(unittest.TestCase):
    def test_valid_api_authentication_is_online(self):
        response = FakeResponse(b'{"user_info":{"auth":1}}')
        with mock.patch.object(xtream.urllib.request, "urlopen", return_value=response):
            self.assertEqual(xtream.check_server_status(server()), "online")

    def test_invalid_api_authentication_is_reachable_not_offline(self):
        response = FakeResponse(b'{"user_info":{"auth":0}}')
        with mock.patch.object(xtream.urllib.request, "urlopen", return_value=response):
            self.assertEqual(xtream.check_server_status(server()), "reachable")

    def test_auth_http_error_means_host_responded(self):
        error = urllib.error.HTTPError("http://media.example.test", 401, "Unauthorized", {}, None)
        with mock.patch.object(xtream.urllib.request, "urlopen", side_effect=error):
            self.assertEqual(xtream.check_server_status(server()), "reachable")

    def test_forbidden_http_error_means_host_responded(self):
        error = urllib.error.HTTPError("http://media.example.test", 403, "Forbidden", {}, None)
        with mock.patch.object(xtream.urllib.request, "urlopen", side_effect=error):
            self.assertEqual(xtream.check_server_status(server()), "reachable")

    def test_missing_api_http_error_is_offline(self):
        error = urllib.error.HTTPError("http://media.example.test", 404, "Not Found", {}, None)
        with mock.patch.object(xtream.urllib.request, "urlopen", side_effect=error):
            self.assertEqual(xtream.check_server_status(server()), "offline")

    def test_server_error_is_offline(self):
        error = urllib.error.HTTPError("http://media.example.test", 503, "Unavailable", {}, None)
        with mock.patch.object(xtream.urllib.request, "urlopen", side_effect=error):
            self.assertEqual(xtream.check_server_status(server()), "offline")

    def test_network_error_is_offline(self):
        with mock.patch.object(xtream.urllib.request, "urlopen", side_effect=urllib.error.URLError("unreachable")):
            self.assertEqual(xtream.check_server_status(server()), "offline")

    def test_incomplete_credentials_are_unknown_without_request(self):
        with mock.patch.object(xtream.urllib.request, "urlopen") as request:
            self.assertEqual(xtream.check_server_status(server(password="")), "unknown")
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
