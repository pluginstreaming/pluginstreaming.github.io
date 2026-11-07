# -*- coding: utf-8 -*-
"""Testes da lista visual de servidores OFF/ON do FILMOM."""

from __future__ import absolute_import, unicode_literals

import os
import sys
import types
import unittest
from unittest import mock

ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugin.video.filmom"))
sys.path.insert(0, ADDON_ROOT)


class StubAddon(object):
    def __init__(self, _addon_id):
        pass

    def getAddonInfo(self, key):
        return "/tmp/filmom" if key == "path" else "/tmp/filmom-profile"

    def getSetting(self, _key):
        return ""

    def setSetting(self, *_args):
        pass


class FakeListItem(object):
    def __init__(self, label=""):
        self.label = label

    def setArt(self, *_args, **_kwargs):
        pass

    def setInfo(self, *_args, **_kwargs):
        pass

    def setProperty(self, *_args, **_kwargs):
        pass


class FakeProgress(object):
    def create(self, *_args, **_kwargs):
        pass

    def update(self, *_args, **_kwargs):
        pass

    def iscanceled(self):
        return False

    def close(self):
        pass


xbmc = sys.modules.setdefault("xbmc", types.ModuleType("xbmc"))
xbmc.LOGWARNING = 2
xbmc.LOGDEBUG = 0
xbmc.LOGERROR = 4
xbmc.LOGINFO = 1
xbmc.NOTIFICATION_INFO = 0
xbmc.NOTIFICATION_WARNING = 1
xbmc.log = lambda *_args, **_kwargs: None
xbmc.translatePath = lambda path: path
xbmc.executebuiltin = lambda *_args, **_kwargs: None

xbmcaddon = sys.modules.setdefault("xbmcaddon", types.ModuleType("xbmcaddon"))
xbmcaddon.Addon = StubAddon
xbmcvfs = sys.modules.setdefault("xbmcvfs", types.ModuleType("xbmcvfs"))
xbmcvfs.translatePath = lambda path: path
xbmcvfs.exists = lambda _path: False
xbmcvfs.mkdirs = lambda _path: True
xbmcvfs.delete = lambda _path: None
xbmcgui = sys.modules.setdefault("xbmcgui", types.ModuleType("xbmcgui"))
xbmcgui.ListItem = FakeListItem
xbmcgui.DialogProgress = FakeProgress
xbmcgui.Dialog = lambda: mock.Mock()
xbmcplugin = sys.modules.setdefault("xbmcplugin", types.ModuleType("xbmcplugin"))

from resources.lib import config, xtream  # noqa: E402

ADDON = config.ADDON
ADDON.getAddonInfo = lambda key: "/tmp/filmom" if key == "path" else "/tmp/filmom-profile"
xbmcplugin.addDirectoryItem = lambda _handle, _url, item, isFolder=True: _DIRECTORY_ITEMS.append(item.label)
xbmcplugin.setContent = lambda *_args, **_kwargs: None
_DIRECTORY_ITEMS = []

_original_argv = list(sys.argv)
sys.argv = [sys.argv[0], "1", ""]
from resources.lib import ui  # noqa: E402
sys.argv = _original_argv


class OfflineServerListTests(unittest.TestCase):
    def setUp(self):
        _DIRECTORY_ITEMS[:] = []
        self.servers = [
            {"name": "Servidor 1", "number": "1"},
            {"name": "Servidor 2", "number": "2"},
            {"name": "Servidor 3", "number": "3"},
            {"name": "Servidor 4", "number": "4"},
        ]
        self.statuses = {"1": "offline", "2": "reachable", "3": "online", "4": "offline"}

    def test_off_and_on_headers_and_numbers_have_requested_colors(self):
        with mock.patch.object(config, "refresh_servers_from_source"), \
                mock.patch.object(config, "load_config", return_value={}), \
                mock.patch.object(config, "get_servers", return_value=self.servers), \
                mock.patch.object(config, "server_has_credentials", return_value=True), \
                mock.patch.object(xtream, "check_server_status", side_effect=lambda server: self.statuses[server["number"]]):
            ui.find_offline_servers()

        self.assertEqual(_DIRECTORY_ITEMS, [
            "[COLOR red][B]SERVIDORES OFF[/B][/COLOR]",
            "[COLOR red][B]1[/B][/COLOR]",
            "[COLOR red][B]4[/B][/COLOR]",
            "[COLOR green][B]SERVIDORES ON[/B][/COLOR]",
            "[COLOR green][B]2[/B][/COLOR]",
            "[COLOR green][B]3[/B][/COLOR]",
        ])


if __name__ == "__main__":
    unittest.main()
