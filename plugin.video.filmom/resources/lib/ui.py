# -*- coding: utf-8 -*-
"""Interface Kodi do FILMOM, com navegação inspirada em serviços de streaming."""

from __future__ import absolute_import, unicode_literals

import sys
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib import config, player, xtream

HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
ADDON_PATH = config.ADDON.getAddonInfo("path")
MEDIA = ADDON_PATH + "/resources/media/"
FANART = ADDON_PATH + "/fanart.jpg"
DEFAULT_THUMB = MEDIA + "default_thumb.png"


def media(name):
    return MEDIA + name


def build_url(action, **kwargs):
    params = {"action": action}
    params.update(kwargs)
    return BASE_URL + "?" + urllib.parse.urlencode(params)


def set_view(content="videos", view_mode=55):
    xbmcplugin.setContent(HANDLE, content)
    xbmc.executebuiltin("Container.SetViewMode(%s)" % view_mode)


def add_item(label, action=None, icon=None, fanart=None, plot="", folder=True, playable=False, **params):
    url = build_url(action, **params) if action else ""
    list_item = xbmcgui.ListItem(label=label)
    art = icon or DEFAULT_THUMB
    list_item.setArt({"icon": art, "thumb": art, "poster": art, "fanart": fanart or FANART})
    list_item.setInfo("video", {
        "title": clean_label(label),
        "plot": plot or "Sinopse não informada pelo servidor.",
        "mediatype": "video"
    })
    if playable:
        list_item.setProperty("IsPlayable", "true")
        player.add_context_play_properties(list_item, params.get("url", ""))
    xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=folder)


def clean_label(label):
    return (label or "").replace("[COLOR gold]", "").replace("[/COLOR]", "").replace("[B]", "").replace("[/B]", "")


def active_server_number():
    credentials = config.get_active_credentials()
    return str(credentials.get("number") or "1")


def require_credentials():
    if config.has_credentials():
        return True
    xbmcgui.Dialog().notification("FILMOM", "Configure URL, usuário e senha em TROCA DE SERVIDOR.", xbmcgui.NOTIFICATION_WARNING, 5000)
    config.server_wizard()
    return config.has_credentials()


def home():
    active_server = active_server_number()
    add_item("[COLOR gold][B]TROCA DE SERVIDOR[/B][/COLOR] - [ATIVO] %s" % active_server, "servers", media("icon_server.png"), plot="Selecione o servidor ativo por número, sem exibir dados de conta na interface.")
    add_item("BUSCAR SERVIDORES OFFLINE", "offline_servers", media("icon_server.png"), plot="Verifica todos os servidores habilitados e mostra os que não respondem.")
    add_item("TV AO VIVO", "live_categories", media("icon_live.png"), plot="Canais ao vivo organizados por categoria, com capa e sinopse quando enviados pelo servidor.")
    add_item("FILMES", "vod_categories", media("icon_movies.png"), plot="Catálogo de filmes com posters, informações e sinopse em visual moderno.")
    add_item("SÉRIES", "series_categories", media("icon_series.png"), plot="Séries, temporadas e episódios com metadados e descrição.")
    add_item("BUSCA", "search", media("icon_search.png"), plot="Pesquise em TV ao vivo, filmes e séries de forma unificada.")
    set_view("videos", 500)


def server_menu():
    config.select_server_dialog()
    home()


def find_offline_servers():
    # Atualiza a lista remota antes da varredura; em caso de falha, a configuração
    # preserva os servidores válidos já instalados localmente.
    config.refresh_servers_from_source(use_cache=False)
    data = config.load_config()
    servers = [server for server in config.get_servers(data) if config.server_has_credentials(server)]
    if not servers:
        xbmcgui.Dialog().ok("FILMOM", "Nenhum servidor habilitado com credenciais completas foi encontrado.")
        return

    progress = xbmcgui.DialogProgress()
    progress.create("FILMOM", "Verificando %d servidores..." % len(servers))
    results = []
    cancelled = False
    try:
        for index, server in enumerate(servers, start=1):
            name = server.get("name") or "Servidor %s" % (server.get("number") or "?")
            progress.update(int(index * 100 / len(servers)), "Verificando %s..." % name)
            if progress.iscanceled():
                cancelled = True
                break
            status = xtream.check_server_status(server)
            results.append((server, status))
    finally:
        progress.close()

    if not results:
        xbmcgui.Dialog().notification("FILMOM", "Verificação cancelada.", xbmcgui.NOTIFICATION_INFO, 3000)
        return

    offline = [server for server, status in results if status == "offline"]
    online = [(server, status) for server, status in results if status in ("online", "reachable")]
    add_item("[COLOR red][B]SERVIDORES OFF[/B][/COLOR]", icon=media("icon_server.png"), plot="Lista dos números de servidores cuja API Xtream está indisponível.", folder=False)
    if offline:
        for server in offline:
            number = str(server.get("number") or config._server_number(server.get("name") or "1"))
            add_item("[COLOR red][B]%s[/B][/COLOR]" % number, icon=media("icon_server.png"), plot="Servidor %s: API Xtream indisponível." % number, folder=False)
    else:
        add_item("Nenhum", icon=media("icon_server.png"), plot="Nenhum servidor offline foi encontrado nesta verificação.", folder=False)
    add_item("[COLOR green][B]SERVIDORES ON[/B][/COLOR]", icon=media("icon_server.png"), plot="Lista dos números de servidores online ou que respondem pela rede.", folder=False)
    if online:
        for server, status in online:
            number = str(server.get("number") or config._server_number(server.get("name") or "1"))
            plot = "Servidor %s online." % number if status == "online" else "Servidor %s responde pela rede, mas a autenticação não foi confirmada." % number
            add_item("[COLOR green][B]%s[/B][/COLOR]" % number, icon=media("icon_server.png"), plot=plot, folder=False)
    else:
        add_item("Nenhum", icon=media("icon_server.png"), plot="Nenhum servidor online foi confirmado nesta verificação.", folder=False)
    if cancelled:
        xbmcgui.Dialog().notification("FILMOM", "Verificação parcial dos servidores.", xbmcgui.NOTIFICATION_WARNING, 3000)
    set_view("videos", 55)


def player_menu():
    config.select_player_dialog()
    home()


def live_categories():
    if not require_credentials():
        return
    categories = xtream.visible_items(xtream.live_categories())
    add_item("[COLOR gold]TODOS OS CANAIS[/COLOR]", "live_list", media("icon_live.png"), plot="Todos os canais ao vivo disponíveis no servidor ativo.")
    for cat in categories:
        name = cat.get("category_name", "Categoria")
        cat_id = cat.get("category_id", "")
        add_item(name, "live_list", media("icon_live.png"), plot="Categoria de TV ao vivo: %s." % name, category_id=cat_id)
    set_view("tvshows", 55)


def live_list(category_id=""):
    if not require_credentials():
        return
    for item in xtream.visible_items(xtream.live_streams(category_id or None)):
        name = item.get("name", "Canal")
        stream_id = item.get("stream_id")
        extension = "ts"
        thumb = item.get("stream_icon") or media("icon_live.png")
        plot = xtream.content_plot(item, "Canal ao vivo: %s. Sinopse detalhada não fornecida pelo servidor." % name)
        url = xtream.live_play_url(stream_id, extension)
        fallback_url = xtream.live_play_url(stream_id, "m3u8")
        add_item(name, "play", thumb, FANART, plot, folder=False, playable=True, url=url, title=name, thumb=thumb, plot_text=plot, fallback_url=fallback_url)
    set_view("videos", 55)


def vod_categories():
    if not require_credentials():
        return
    categories = xtream.visible_items(xtream.vod_categories())
    add_item("[COLOR gold]TODOS OS FILMES[/COLOR]", "vod_list", media("icon_movies.png"), plot="Todos os filmes disponíveis no servidor ativo.")
    for cat in categories:
        name = cat.get("category_name", "Categoria")
        add_item(name, "vod_list", media("icon_movies.png"), plot="Categoria de filmes: %s." % name, category_id=cat.get("category_id", ""))
    set_view("movies", 55)


def vod_list(category_id=""):
    if not require_credentials():
        return
    for item in xtream.visible_items(xtream.vod_streams(category_id or None)):
        name = item.get("name", "Filme")
        stream_id = item.get("stream_id")
        extension = item.get("container_extension") or "mp4"
        thumb = item.get("stream_icon") or item.get("cover") or DEFAULT_THUMB
        plot = xtream.content_plot(item, "Filme: %s. A sinopse completa não foi enviada pelo servidor." % name)
        url = xtream.movie_play_url(stream_id, extension)
        add_item(name, "play", thumb, FANART, plot, folder=False, playable=True, url=url, title=name, thumb=thumb, plot_text=plot)
    set_view("movies", 55)


def series_categories():
    if not require_credentials():
        return
    categories = xtream.visible_items(xtream.series_categories())
    add_item("[COLOR gold]TODAS AS SÉRIES[/COLOR]", "series_list", media("icon_series.png"), plot="Todas as séries disponíveis no servidor ativo.")
    for cat in categories:
        name = cat.get("category_name", "Categoria")
        add_item(name, "series_list", media("icon_series.png"), plot="Categoria de séries: %s." % name, category_id=cat.get("category_id", ""))
    set_view("tvshows", 55)


def series_list(category_id=""):
    if not require_credentials():
        return
    for item in xtream.visible_items(xtream.series_list(category_id or None)):
        name = item.get("name", "Série")
        series_id = item.get("series_id")
        thumb = item.get("cover") or DEFAULT_THUMB
        fanart = FANART
        backdrop = item.get("backdrop_path")
        if isinstance(backdrop, list) and backdrop:
            fanart = backdrop[0]
        plot = xtream.content_plot(item, "Série: %s. A sinopse completa não foi enviada pelo servidor." % name)
        add_item(name, "series_seasons", thumb, fanart, plot, series_id=series_id, title=name, thumb=thumb, plot_text=plot)
    set_view("tvshows", 55)


def series_seasons(series_id="", title="", thumb="", plot=""):
    if not require_credentials():
        return
    info = xtream.series_info(series_id)
    episodes = info.get("episodes", {}) if isinstance(info, dict) else {}
    show_info = info.get("info", {}) if isinstance(info, dict) else {}
    show_plot = show_info.get("plot") or plot or "Sinopse da série não informada pelo servidor."
    for season in sorted(episodes.keys(), key=lambda value: int(value) if str(value).isdigit() else 999):
        add_item("Temporada %s" % season, "series_episodes", thumb or show_info.get("cover") or DEFAULT_THUMB, FANART, show_plot, series_id=series_id, season=season, title=title, thumb=thumb or show_info.get("cover") or DEFAULT_THUMB, plot_text=show_plot)
    set_view("seasons", 55)


def series_episodes(series_id="", season="", title="", thumb="", plot=""):
    if not require_credentials():
        return
    info = xtream.series_info(series_id)
    episodes = (info.get("episodes", {}) or {}).get(str(season), [])
    for episode in episodes:
        ep_title = episode.get("title") or episode.get("name") or "Episódio"
        stream_id = episode.get("id")
        extension = episode.get("container_extension") or "mp4"
        ep_info = episode.get("info") or {}
        ep_thumb = ep_info.get("movie_image") or thumb or DEFAULT_THUMB
        ep_plot = ep_info.get("plot") or plot or "Episódio de %s. Sinopse não enviada pelo servidor." % title
        url = xtream.series_play_url(stream_id, extension)
        add_item(ep_title, "play", ep_thumb, FANART, ep_plot, folder=False, playable=True, url=url, title=ep_title, thumb=ep_thumb, plot_text=ep_plot)
    set_view("episodes", 55)


def search():
    if not require_credentials():
        return
    term = xbmcgui.Dialog().input("FILMOM - BUSCA")
    if not term:
        return
    for kind, item in xtream.search_all(term):
        name = item.get("name", "Resultado")
        if kind == "live":
            url = xtream.live_play_url(item.get("stream_id"), "ts")
            fallback_url = xtream.live_play_url(item.get("stream_id"), "m3u8")
            thumb = item.get("stream_icon") or media("icon_live.png")
        elif kind == "movie":
            url = xtream.movie_play_url(item.get("stream_id"), item.get("container_extension") or "mp4")
            thumb = item.get("stream_icon") or DEFAULT_THUMB
        else:
            thumb = item.get("cover") or DEFAULT_THUMB
            add_item("[SÉRIE] %s" % name, "series_seasons", thumb, FANART, xtream.content_plot(item, "Resultado de série encontrado na busca."), series_id=item.get("series_id"), title=name, thumb=thumb, plot_text=xtream.content_plot(item, "Resultado de série encontrado na busca."))
            continue
        plot = xtream.content_plot(item, "Resultado encontrado na busca FILMOM.")
        route_params = {"url": url, "title": name, "thumb": thumb, "plot_text": plot}
        if kind == "live":
            route_params["fallback_url"] = fallback_url
        add_item("[%s] %s" % (kind.upper(), name), "play", thumb, FANART, plot, folder=False, playable=True, **route_params)
    set_view("videos", 55)


def play(url="", title="FILMOM", thumb="", plot="", fallback_url=""):
    player.resolve(url, title, thumb, FANART, plot, fallback_url=fallback_url)
