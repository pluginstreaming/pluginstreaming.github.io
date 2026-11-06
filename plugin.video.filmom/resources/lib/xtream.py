# -*- coding: utf-8 -*-
"""Cliente de API compatível com Player API/Xtream para contas autorizadas."""

from __future__ import absolute_import, unicode_literals

import hashlib
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

import xbmc
import xbmcgui

from resources.lib import config

USER_AGENT = "FILMOM/1.0 Kodi Addon"
API_CACHE_PREFIX = "filmom_xtream_api_"


def timeout():
    try:
        return max(5, int(config.get_setting("network_timeout", "18")))
    except Exception:
        return 18


def build_query_url(base_url, path="player_api.php", **params):
    base = config.normalize_url(base_url)
    query = urllib.parse.urlencode(params)
    return "%s/%s?%s" % (base, path.lstrip("/"), query)


def credentials():
    return config.get_active_credentials()


def api_url(action=None, **extra):
    cred = credentials()
    params = {"username": cred["username"], "password": cred["password"]}
    if action:
        params["action"] = action
    params.update(extra)
    return build_query_url(cred["url"], "player_api.php", **params)


def _api_cache_path(url):
    digest = hashlib.sha1((url or "").encode("utf-8", "ignore")).hexdigest()
    return os.path.join(config.profile_dir(), "%s%s.json" % (API_CACHE_PREFIX, digest))


def _api_cache_ttl(url):
    text = (url or "").lower()
    if "get_vod_streams" in text or "get_series" in text:
        return 60 * 60
    if "get_vod_categories" in text or "get_series_categories" in text or "get_live_categories" in text:
        return 12 * 60 * 60
    if "get_vod_info" in text or "get_series_info" in text:
        return 6 * 60 * 60
    if "get_live_streams" in text:
        return 10 * 60
    return 5 * 60


def _read_api_cache(url, allow_stale=False):
    path = _api_cache_path(url)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if allow_stale:
            return data
        age = time.time() - os.path.getmtime(path)
        if age >= 0 and age <= _api_cache_ttl(url):
            return data
    except Exception:
        return None
    return None


def _write_api_cache(url, data):
    try:
        with open(_api_cache_path(url), "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
    except Exception as exc:
        xbmc.log("[FILMOM] Falha ao gravar cache da API: %s" % exc, xbmc.LOGDEBUG)


def request_json(url, silent=False):
    cached = _read_api_cache(url, allow_stale=False)
    if cached is not None:
        return cached
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"})
    try:
        socket.setdefaulttimeout(timeout())
        with urllib.request.urlopen(req, timeout=timeout()) as response:
            raw = response.read().decode("utf-8", "ignore")
        if not raw:
            return None
        data = json.loads(raw)
        _write_api_cache(url, data)
        return data
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, socket.timeout) as exc:
        xbmc.log("[FILMOM] Falha de API: %s | %s" % (url, exc), xbmc.LOGWARNING)
        stale = _read_api_cache(url, allow_stale=True)
        if stale is not None:
            return stale
        if not silent:
            xbmcgui.Dialog().notification("FILMOM", "Falha ao consultar servidor. Verifique URL, usuário, senha ou conexão.", xbmcgui.NOTIFICATION_ERROR, 5000)
        return None


def account_info():
    return request_json(api_url(), silent=True) or {}


def check_server_status(server):
    """Retorna online, reachable ou offline sem registrar URL/credenciais.

    ``reachable`` indica que houve resposta HTTP, mas a API não confirmou a
    autenticação; esse resultado não deve ser confundido com servidor offline.
    """
    if not isinstance(server, dict):
        return "unknown"
    credentials = config.get_server_credentials(server)
    base_url = credentials["url"]
    username = credentials["username"]
    password = credentials["password"]
    if not (base_url and username and password):
        return "unknown"

    url = build_query_url(base_url, "player_api.php", username=username, password=password)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout()) as response:
            raw = response.read().decode("utf-8", "ignore")
        if not raw:
            return "reachable"
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return "reachable"
        user_info = data.get("user_info") if isinstance(data, dict) else None
        if isinstance(user_info, dict) and str(user_info.get("auth")) == "1":
            return "online"
        return "reachable"
    except urllib.error.HTTPError as exc:
        # Autenticação negada ainda prova que o host respondeu; erros 5xx
        # indicam que o serviço do servidor não está disponível.
        return "offline" if 500 <= int(exc.code or 0) < 600 else "reachable"
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError, ValueError):
        return "offline"


def auth_ok():
    data = account_info()
    try:
        return str(data.get("user_info", {}).get("auth")) == "1"
    except Exception:
        return False


def live_categories():
    data = request_json(api_url("get_live_categories"))
    return data if isinstance(data, list) else []


def live_streams(category_id=None):
    params = {}
    if category_id:
        params["category_id"] = category_id
    data = request_json(api_url("get_live_streams", **params))
    return data if isinstance(data, list) else []


def vod_categories():
    data = request_json(api_url("get_vod_categories"))
    return data if isinstance(data, list) else []


def vod_streams(category_id=None):
    params = {}
    if category_id:
        params["category_id"] = category_id
    data = request_json(api_url("get_vod_streams", **params))
    return data if isinstance(data, list) else []


def vod_info(vod_id):
    data = request_json(api_url("get_vod_info", vod_id=vod_id))
    return data if isinstance(data, dict) else {}


def series_categories():
    data = request_json(api_url("get_series_categories"))
    return data if isinstance(data, list) else []


def series_list(category_id=None):
    params = {}
    if category_id:
        params["category_id"] = category_id
    data = request_json(api_url("get_series", **params))
    return data if isinstance(data, list) else []


def series_info(series_id):
    data = request_json(api_url("get_series_info", series_id=series_id))
    return data if isinstance(data, dict) else {}


def live_play_url(stream_id, extension="ts"):
    cred = credentials()
    extension = extension or "ts"
    return "%s/live/%s/%s/%s.%s" % (cred["url"], urllib.parse.quote(cred["username"]), urllib.parse.quote(cred["password"]), stream_id, extension)


def movie_play_url(stream_id, extension="mp4"):
    cred = credentials()
    extension = extension or "mp4"
    return "%s/movie/%s/%s/%s.%s" % (cred["url"], urllib.parse.quote(cred["username"]), urllib.parse.quote(cred["password"]), stream_id, extension)


def series_play_url(stream_id, extension="mp4"):
    cred = credentials()
    extension = extension or "mp4"
    return "%s/series/%s/%s/%s.%s" % (cred["url"], urllib.parse.quote(cred["username"]), urllib.parse.quote(cred["password"]), stream_id, extension)


def search_all(term):
    term = (term or "").lower().strip()
    if not term:
        return []
    results = []
    for item in live_streams():
        if term in (item.get("name", "").lower()):
            results.append(("live", item))
    for item in vod_streams():
        if term in (item.get("name", "").lower()):
            results.append(("movie", item))
    for item in series_list():
        if term in (item.get("name", "").lower()):
            results.append(("series", item))
    return results


def content_plot(item, fallback="Sinopse não informada pelo servidor."):
    for key in ("plot", "description", "info", "overview"):
        value = item.get(key)
        if isinstance(value, dict):
            value = value.get("plot") or value.get("description")
        if value:
            return str(value)
    return fallback


def is_adult_name(name):
    text = (name or "").lower()
    adult_terms = ["xxx", "adult", "adults", "porn", "18+", "hot"]
    return any(term in text for term in adult_terms)


def visible_items(items):
    if config.get_setting("hide_adult", "true") != "true":
        return items
    return [item for item in items if not is_adult_name(item.get("name") or item.get("category_name") or "")]
