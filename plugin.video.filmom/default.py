# -*- coding: utf-8 -*-
"""Entrada principal do addon FILMOM."""

from __future__ import absolute_import, unicode_literals

import sys
import traceback
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib import auth, config, ui, updater


def params():
    query = sys.argv[2][1:] if len(sys.argv) > 2 and sys.argv[2].startswith("?") else ""
    parsed = urllib.parse.parse_qs(query)
    return {key: values[0] if values else "" for key, values in parsed.items()}


def dispatch():
    p = params()
    action = p.get("action", "home")

    if action == "home":
        ui.home()
    elif action == "servers":
        ui.server_menu()
    elif action == "live_categories":
        ui.live_categories()
    elif action == "live_list":
        ui.live_list(p.get("category_id", ""))
    elif action == "vod_categories":
        ui.vod_categories()
    elif action == "vod_list":
        ui.vod_list(p.get("category_id", ""))
    elif action == "series_categories":
        ui.series_categories()
    elif action == "series_list":
        ui.series_list(p.get("category_id", ""))
    elif action == "series_seasons":
        ui.series_seasons(p.get("series_id", ""), p.get("title", ""), p.get("thumb", ""), p.get("plot_text", p.get("plot", "")))
    elif action == "series_episodes":
        ui.series_episodes(p.get("series_id", ""), p.get("season", ""), p.get("title", ""), p.get("thumb", ""), p.get("plot_text", p.get("plot", "")))
    elif action == "search":
        ui.search()
    elif action == "check_update":
        updater.check_interactive(force=True)
        ui.home()
    elif action == "play":
        ui.play(p.get("url", ""), p.get("title", "FILMOM"), p.get("thumb", ""), p.get("plot_text", p.get("plot", "")), p.get("fallback_url", ""))
    else:
        ui.home()


if __name__ == "__main__":
    post_login_refresh = False
    try:
        config.load_config()
        if auth.require_access():
            updater.check_interactive(force=False)
            dispatch()
            post_login_refresh = auth.consume_post_login_refresh()
    except Exception as exc:
        xbmc.log("[FILMOM] Erro não tratado ao abrir/navegar: %s\n%s" % (exc, traceback.format_exc()), xbmc.LOGERROR)
        try:
            xbmcgui.Dialog().notification("FILMOM", "Erro ao abrir lista. Tente trocar/atualizar servidor.", xbmcgui.NOTIFICATION_ERROR, 5000)
            ui.home()
        except Exception:
            pass
    finally:
        try:
            xbmcplugin.endOfDirectory(int(sys.argv[1]))
        except Exception:
            pass
    if post_login_refresh:
        xbmc.executebuiltin("Container.Refresh")
