# -*- coding: utf-8 -*-
"""Configuração persistente do FILMOM no padrão simples clients.json/servers.json.

Este módulo segue a arquitetura do addon funcional usado como modelo: o acesso do
cliente é validado em ``clients.json`` e as credenciais Xtream são carregadas de
``servers.json``. O restante do addon continua consumindo as credenciais pelo
contrato antigo de ``get_active_credentials()``.
"""

from __future__ import absolute_import, unicode_literals

import base64
import json
import os
import time
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = "plugin.video.filmom"
ADDON = xbmcaddon.Addon(ADDON_ID)
CONFIG_VERSION = 9
CONFIG_FILE_NAME = "filmom_config.json"
REMOTE_CACHE_FILE_NAME = "filmom_remote_config.json"
CLIENTS_CACHE_FILE_NAME = "filmom_clients_cache.json"
SERVERS_CACHE_FILE_NAME = "filmom_servers_cache.json"
PUBLIC_CLIENTS_JSON_URL = "https://raw.githubusercontent.com/brazalvesjr/filmom-dist/main/clients.json"
PUBLIC_SERVERS_JSON_URL = "https://raw.githubusercontent.com/brazalvesjr/filmom-dist/main/servers.json"
PUBLIC_MANIFEST_JSON_URL = "https://raw.githubusercontent.com/brazalvesjr/filmom-dist/main/manifest.json"
USER_AGENT = "Mozilla/5.0 FILMOM-Kodi/1.0"
REMOTE_CACHE_TTL_SECONDS = 6 * 60 * 60
SINGLE_PLAYER_ID = "native_single"
SINGLE_PLAYER_LABEL = "PLAYER ÚNICO NATIVO"


def _translate(path):
    try:
        return xbmcvfs.translatePath(path)
    except AttributeError:
        return xbmc.translatePath(path)


def addon_path():
    return _translate(ADDON.getAddonInfo("path"))


def profile_dir():
    path = _translate(ADDON.getAddonInfo("profile"))
    if not xbmcvfs.exists(path):
        try:
            xbmcvfs.mkdirs(path)
        except Exception:
            os.makedirs(path, exist_ok=True)
    return path


def config_path():
    return os.path.join(profile_dir(), CONFIG_FILE_NAME)


def cache_path(name):
    return os.path.join(profile_dir(), name)


def remote_cache_path():
    return cache_path(REMOTE_CACHE_FILE_NAME)


def get_setting(key, default=""):
    try:
        value = ADDON.getSetting(key)
    except Exception:
        value = ""
    return value if value not in (None, "") else default


def set_setting(key, value):
    try:
        ADDON.setSetting(key, value if value is not None else "")
    except Exception:
        pass


def normalize_url(url):
    url = (url or "").strip()
    if url and not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url.rstrip("/")


def _obfuscate(value):
    value = value or ""
    raw = value.encode("utf-8")
    return "b64:" + base64.urlsafe_b64encode(raw).decode("ascii")


def _deobfuscate(value):
    value = value or ""
    if not value.startswith("b64:"):
        return value
    try:
        return base64.urlsafe_b64decode(value[4:].encode("ascii")).decode("utf-8")
    except Exception:
        return ""


def _empty_server_record():
    return {"name": "Servidor 1", "number": "1", "url": "", "username": "", "password": _obfuscate("")}


def _clear_server_settings():
    set_setting("active_server_name", "Servidor 1")
    set_setting("server_url", "")
    set_setting("username", "")
    set_setting("password", "")


def default_config():
    return {
        "config_version": CONFIG_VERSION,
        "updated_at": int(time.time()),
        "active_server": get_setting("active_server_name", "Servidor 1") or "Servidor 1",
        "servers": []
    }


def _server_number(name):
    text = str(name or "Servidor 1")
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits or "1"


def _server_key(value):
    """Retorna uma chave numérica estável para comparar servidores por nome ou número."""
    if isinstance(value, dict):
        return str(value.get("number") or _server_number(value.get("name") or "1"))
    return _server_number(value)


def _server_display_name(server):
    number = _server_key(server)
    name = (server or {}).get("name") or "Servidor %s" % number
    if not str(name).lower().startswith("servidor"):
        name = "Servidor %s" % number
    return name


def _same_server(left, right):
    return _server_key(left) == _server_key(right)


def _read_json_file(path):
    if not path or not xbmcvfs.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json_file(path, data):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data or {}, handle, indent=2, ensure_ascii=False, sort_keys=True)
    except Exception as exc:
        xbmc.log("[FILMOM] Falha ao salvar JSON local: %s" % exc, xbmc.LOGWARNING)


def _cache_is_fresh(path, ttl_seconds=REMOTE_CACHE_TTL_SECONDS):
    if not path or not xbmcvfs.exists(path):
        return False
    try:
        age = time.time() - os.path.getmtime(path)
        return age >= 0 and age <= int(ttl_seconds or REMOTE_CACHE_TTL_SECONDS)
    except Exception:
        return False


def _read_cache_if_fresh(cache_name, ttl_seconds=REMOTE_CACHE_TTL_SECONDS):
    if not cache_name:
        return {}
    path = cache_path(cache_name)
    if not _cache_is_fresh(path, ttl_seconds):
        return {}
    return _read_json_file(path)


def load_config():
    data = default_config()
    loaded = _read_json_file(config_path())
    if loaded:
        data.update(loaded)
    data.pop("clients", None)
    return ensure_initial_server(data)


def save_config(data):
    data = data or default_config()
    data["config_version"] = CONFIG_VERSION
    data["updated_at"] = int(time.time())
    data.pop("clients", None)
    _write_json_file(config_path(), data)


def _timeout():
    try:
        return max(5, int(get_setting("network_timeout", "18") or 18))
    except Exception:
        return 18


def _legacy_url(url):
    text = (url or "").strip().lower()
    return (not text) or "clientes.json" in text or "seu-usuario" in text or "brazalvesjr/filmom" in text and "filmom-dist" not in text


def clients_json_url():
    url = (get_setting("clients_json_url", "") or "").strip()
    if _legacy_url(url):
        url = PUBLIC_CLIENTS_JSON_URL
        set_setting("clients_json_url", url)
    return url


def servers_json_url():
    url = (get_setting("servers_json_url", "") or "").strip()
    if _legacy_url(url):
        url = PUBLIC_SERVERS_JSON_URL
        set_setting("servers_json_url", url)
    return url


def remote_json_url():
    return clients_json_url()


def manifest_url():
    url = (get_setting("github_manifest_url", "") or "").strip()
    if _legacy_url(url):
        url = PUBLIC_MANIFEST_JSON_URL
        set_setting("github_manifest_url", url)
    return url


def player_options():
    """Retorna somente o player único, preservando compatibilidade com código legado."""
    return [{"id": SINGLE_PLAYER_ID, "label": SINGLE_PLAYER_LABEL, "description": "Reprodução nativa direta com fallback HLS quando disponível."}]


def get_active_player_id():
    return SINGLE_PLAYER_ID


def get_active_player_label():
    return SINGLE_PLAYER_LABEL


def set_active_player(player_id):
    return SINGLE_PLAYER_ID


def _remove_file(path):
    try:
        if xbmcvfs.exists(path):
            try:
                xbmcvfs.delete(path)
            except Exception:
                os.remove(path)
    except Exception:
        pass


def clear_remote_cache():
    for name in (REMOTE_CACHE_FILE_NAME, CLIENTS_CACHE_FILE_NAME, SERVERS_CACHE_FILE_NAME):
        _remove_file(cache_path(name))


def _fetch_json_url(url, cache_name=None, local_name=None, use_cache=True, bust_cache=True):
    if use_cache and cache_name:
        fresh = _read_cache_if_fresh(cache_name, REMOTE_CACHE_TTL_SECONDS)
        if fresh:
            return fresh
    if url:
        final_url = url
        if bust_cache and not use_cache:
            separator = "&" if "?" in final_url else "?"
            final_url = "%s%snocache=%s" % (final_url, separator, int(time.time()))
        request = urllib.request.Request(final_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=_timeout()) as response:
                raw = response.read().decode("utf-8", "ignore")
            data = json.loads(raw)
            if isinstance(data, dict):
                if cache_name:
                    _write_json_file(cache_path(cache_name), data)
                return data
        except Exception as exc:
            xbmc.log("[FILMOM] Falha ao buscar JSON remoto %s: %s" % (url, exc), xbmc.LOGWARNING)
    if cache_name:
        cached = _read_json_file(cache_path(cache_name))
        if cached:
            return cached
    if local_name:
        local = _read_json_file(os.path.join(addon_path(), local_name))
        if local:
            return local
    return {}


def fetch_clients_config(use_cache=True):
    return _fetch_json_url(clients_json_url(), CLIENTS_CACHE_FILE_NAME, "clients.json", use_cache=use_cache)


def fetch_servers_config(use_cache=True):
    return _fetch_json_url(servers_json_url(), SERVERS_CACHE_FILE_NAME, "servers.json", use_cache=use_cache)


def fetch_remote_config(use_cache=True):
    """Compatibilidade: agora retorna o clients.json simples."""
    return fetch_clients_config(use_cache=use_cache)


def _plain(value):
    return str(value or "").strip()


def _is_false(value):
    return str(value).strip().lower() in ("false", "0", "no", "nao", "não", "off", "disabled")


def _server_is_enabled(server):
    """Servidor só é utilizável quando não foi explicitamente desativado."""
    if not isinstance(server, dict):
        return False
    return not _is_false(server.get("active", server.get("ativo", True)))


def _server_has_credentials(server):
    if not isinstance(server, dict):
        return False
    return bool(server.get("url") and server.get("username") and _deobfuscate(server.get("password", "")))


def _find_enabled_server(servers, active):
    for server in servers or []:
        if not _server_is_enabled(server):
            continue
        if server.get("name") == active or _same_server(server, active):
            return server
    return None


def _normalize_remote_servers(remote):
    remote = remote or {}
    raw_servers = remote.get("servers") or remote.get("servidores") or []
    if isinstance(raw_servers, dict):
        raw_servers = list(raw_servers.values())
    servers = []
    for index, item in enumerate(raw_servers, start=1):
        if not isinstance(item, dict):
            continue
        if not _server_is_enabled(item):
            continue
        number = item.get("id") or item.get("number") or item.get("numero") or item.get("n") or index
        name = _plain(item.get("name") or item.get("nome") or "Servidor %s" % number) or "Servidor %s" % number
        if not name.lower().startswith("servidor") and name.isdigit():
            name = "Servidor %s" % name
        url = normalize_url(item.get("url") or item.get("server_url") or item.get("host") or "")
        username = _plain(item.get("username") or item.get("user") or item.get("usuario") or item.get("usuário"))
        password = _plain(item.get("password") or item.get("senha") or item.get("pass"))
        if url and username and password:
            servers.append({"name": name, "number": str(number), "url": url, "username": username, "password": _obfuscate(password), "remote": True})
    return servers


def install_servers_payload(payload, source="servers.json"):
    payload = payload or {}
    servers = _normalize_remote_servers(payload)
    data = default_config()
    loaded = _read_json_file(config_path())
    if loaded:
        data.update(loaded)

    if not servers:
        previous_servers = data.get("servers") or []
        valid_previous = [server for server in previous_servers if _server_is_enabled(server) and _server_has_credentials(server)]
        if valid_previous:
            xbmc.log("[FILMOM] servers.json indisponível ou sem servidores ativos; mantendo servidores já instalados.", xbmc.LOGWARNING)
            data["servers"] = valid_previous
            data["servers_empty"] = False
            data["server_source"] = source
            save_config(data)
            sync_active_to_settings(data)
            return False
        xbmc.log("[FILMOM] servers.json sem servidores ativos e sem fallback local válido.", xbmc.LOGWARNING)
        data["servers"] = [_empty_server_record()]
        data["active_server"] = "Servidor 1"
        data["server_source"] = source
        data["servers_empty"] = True
        save_config(data)
        _clear_server_settings()
        return False

    previous_servers = data.get("servers") or []
    remote_numbers = set(_server_key(server) for server in servers)
    merged_servers = list(servers)
    for local_server in previous_servers:
        if not _server_is_enabled(local_server):
            continue
        if not _server_has_credentials(local_server):
            continue
        if _server_key(local_server) not in remote_numbers:
            local_server["name"] = _server_display_name(local_server)
            local_server["number"] = _server_key(local_server)
            local_server["local"] = True
            merged_servers.append(local_server)

    active = data.get("active_server") or get_setting("active_server_name", "Servidor 1") or "Servidor 1"
    active_server = _find_enabled_server(merged_servers, active)
    if not active_server:
        settings_active = get_setting("active_server_name", "")
        active_server = _find_enabled_server(merged_servers, settings_active)
    if not active_server:
        active_server = merged_servers[0]
    data["servers"] = merged_servers
    data["active_server"] = _server_display_name(active_server)
    data["server_source"] = source
    data["servers_empty"] = False
    save_config(data)
    sync_active_to_settings(data)
    return True


def refresh_servers_from_source(use_cache=True):
    return install_servers_payload(fetch_servers_config(use_cache=use_cache), source="servers.json")


def install_protected_payload(client_id, payload):
    """Compatibilidade com versões antigas: instala servidores se um payload já vier aberto."""
    ok = install_servers_payload({"servers": (payload or {}).get("servers") or (payload or {}).get("servidores") or []}, source="payload")
    if ok:
        data = load_config()
        data["client_id"] = client_id or (payload or {}).get("client_id") or "cliente"
        save_config(data)
    return ok


def ensure_initial_server(data):
    data = data or default_config()
    servers = data.get("servers") or []
    settings_url = normalize_url(get_setting("server_url"))
    settings_user = get_setting("username")
    settings_pass = get_setting("password")
    active_name = data.get("active_server") or "Servidor 1"

    if settings_url and settings_user and settings_pass and not servers:
        servers.append({"name": active_name, "number": _server_number(active_name), "url": settings_url, "username": settings_user, "password": _obfuscate(settings_pass)})
    elif not servers:
        servers.append(_empty_server_record())

    active_server = _find_enabled_server(servers, active_name)
    if not active_server:
        settings_active = get_setting("active_server_name", "")
        active_server = _find_enabled_server(servers, settings_active)
    if not active_server:
        for server in servers:
            if _server_is_enabled(server):
                active_server = server
                break

    data["servers"] = servers
    data["active_server"] = _server_display_name(active_server) if active_server else active_name
    sync_active_to_settings(data)
    return data


def _all_servers(data=None):
    data = data or load_config()
    servers = [server for server in (data.get("servers") or []) if _server_is_enabled(server)]
    for index, server in enumerate(servers, start=1):
        server.setdefault("number", _server_number(server.get("name") or index))
    return servers


def sync_active_to_settings(data):
    data = data or load_config()
    server = get_active_server(data)
    if not server:
        return
    set_setting("active_server_name", server.get("name", "Servidor 1"))
    set_setting("server_url", server.get("url", ""))
    set_setting("username", server.get("username", ""))
    set_setting("password", _deobfuscate(server.get("password", "")))


def get_servers(data=None):
    return _all_servers(data)


def get_active_server(data=None):
    data = data or load_config()
    active = data.get("active_server") or get_setting("active_server_name", "Servidor 1") or "Servidor 1"
    servers = _all_servers(data)
    server = _find_enabled_server(servers, active)
    if server:
        return server
    settings_active = get_setting("active_server_name", "")
    server = _find_enabled_server(servers, settings_active)
    return server or (servers[0] if servers else None)


def get_active_credentials():
    data = load_config()
    server = get_active_server(data) or {}
    return {
        "name": server.get("name", "Servidor 1"),
        "number": server.get("number", _server_number(server.get("name", "Servidor 1"))),
        "url": normalize_url(server.get("url", "")),
        "username": server.get("username", ""),
        "password": _deobfuscate(server.get("password", ""))
    }


def has_credentials():
    credentials = get_active_credentials()
    return bool(credentials["url"] and credentials["username"] and credentials["password"])


def add_or_update_server(name, url, username, password, make_active=True, active=True):
    data = load_config()
    name = (name or "Servidor 1").strip()
    if not name.lower().startswith("servidor"):
        name = "Servidor %s" % _server_number(name)
    url = normalize_url(url)
    enabled = not _is_false(active)
    servers = data.get("servers") or []
    found = False
    for server in servers:
        if server.get("name") == name:
            server.update({"name": name, "number": _server_number(name), "url": url, "username": username or "", "password": _obfuscate(password or ""), "active": enabled})
            found = True
            break
    if not found:
        servers.append({"name": name, "number": _server_number(name), "url": url, "username": username or "", "password": _obfuscate(password or ""), "active": enabled})
    data["servers"] = servers
    if make_active and enabled:
        data["active_server"] = "Servidor %s" % _server_number(name)
    save_config(data)
    sync_active_to_settings(data)
    return data


def remove_server(name):
    data = load_config()
    data["servers"] = [server for server in data.get("servers", []) if server.get("name") != name]
    if not data["servers"]:
        data["servers"] = [_empty_server_record()]
    if data.get("active_server") == name or _same_server(data.get("active_server"), name):
        data["active_server"] = _server_display_name(data["servers"][0])
    save_config(data)
    sync_active_to_settings(data)
    return data


def select_player_dialog():
    xbmcgui.Dialog().notification("FILMOM", "O addon agora usa somente o player único nativo.", xbmcgui.NOTIFICATION_INFO, 3000)
    xbmc.executebuiltin("Container.Refresh")



def select_server_dialog():
    # Ao abrir a troca de servidor, busque o servers.json publicado sem usar o cache
    # de 6 horas. Isso garante que mudanças feitas no GitHub, como troca do servidor
    # 2, apareçam imediatamente no Kodi sem reinstalar o addon.
    updated = refresh_servers_from_source(use_cache=False)
    if not updated and not has_credentials():
        refresh_servers_from_source(use_cache=True)
    data = load_config()
    servers = [server for server in get_servers(data) if _server_is_enabled(server) and _server_has_credentials(server)]
    if not servers:
        xbmcgui.Dialog().ok("FILMOM", "Nenhum servidor ativo foi encontrado no servers.json.")
        return
    labels = []
    active_server = get_active_server(data) or {}
    for server in servers:
        label = str(server.get("number") or _server_number(server.get("name")))
        if _same_server(server, active_server):
            label = "[COLOR gold][B][ATIVO] %s[/B][/COLOR]" % label
        labels.append(label)
    choice = xbmcgui.Dialog().select("TROCA DE SERVIDOR", labels)
    if choice < 0:
        return
    selected = servers[choice]
    data["active_server"] = _server_display_name(selected)
    save_config(data)
    sync_active_to_settings(data)
    xbmcgui.Dialog().notification("FILMOM", "Servidor %s ativo." % selected.get("number", _server_number(selected.get("name"))), xbmcgui.NOTIFICATION_INFO, 2500)
    xbmc.executebuiltin("Container.Refresh")


def server_wizard():
    if refresh_servers_from_source(use_cache=False):
        xbmcgui.Dialog().notification("FILMOM", "Servidores atualizados.", xbmcgui.NOTIFICATION_INFO, 2500)
        return True
    xbmcgui.Dialog().ok("FILMOM", "Não foi possível carregar o servers.json publicado.")
    return False


def edit_active_server_dialog():
    return server_wizard()
