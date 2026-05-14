# -*- coding: utf-8 -*-
"""Autenticação do FILMOM no padrão simples do plugin funcional.

O acesso é validado por ``clients.json`` com campos ``password`` e ``active``. Ao
validar um cliente ativo, o addon carrega as credenciais Xtream a partir de
``servers.json`` e grava apenas o estado local de autenticação no perfil Kodi.
"""

from __future__ import absolute_import, unicode_literals

import json
import os
import time

import xbmc
import xbmcgui
import xbmcvfs

from resources.lib import config

AUTH_FILE_NAME = "filmom_auth.json"
PASSWORD_PROMPT = "DIGITE A SENHA DO CLIENTE"
POST_LOGIN_REFRESH_SETTING = "filmom_post_login_refresh"


def _auth_path():
    return os.path.join(config.profile_dir(), AUTH_FILE_NAME)


def _read_auth():
    path = _auth_path()
    if not xbmcvfs.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_auth(data):
    data = data or {}
    data["updated_at"] = int(time.time())
    try:
        with open(_auth_path(), "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=True)
    except Exception as exc:
        xbmc.log("[FILMOM] Falha ao salvar autenticação local: %s" % exc, xbmc.LOGWARNING)


def reset_auth():
    try:
        path = _auth_path()
        if xbmcvfs.exists(path):
            try:
                xbmcvfs.delete(path)
            except Exception:
                os.remove(path)
    except Exception:
        pass
    config.set_setting("client_password", "")
    config.set_setting("authenticated_client", "")
    config.clear_remote_cache()


def _normalize_text(value):
    return str(value or "").strip()


def _password_variants(password):
    base = _normalize_text(password)
    variants = []
    for item in (base, base.lower(), base.upper()):
        if item and item not in variants:
            variants.append(item)
    return variants


def keyboard_input(heading, hidden=False, default_value=""):
    """Usa o teclado clássico do Kodi, como no modelo funcional."""
    try:
        keyboard = xbmc.Keyboard(default_value or "", heading, bool(hidden))
        keyboard.setHeading(heading)
        try:
            keyboard.setHiddenInput(bool(hidden))
        except Exception:
            pass
        keyboard.doModal()
        if keyboard.isConfirmed():
            return _normalize_text(keyboard.getText())
        return ""
    except Exception:
        dialog = xbmcgui.Dialog()
        input_type = getattr(xbmcgui, "INPUT_ALPHANUM", 0)
        hide_option = getattr(xbmcgui, "ALPHANUM_HIDE_INPUT", 0) if hidden else 0
        try:
            value = dialog.input(heading, default_value or "", input_type, hide_option)
        except TypeError:
            try:
                value = dialog.input(heading, defaultt=default_value or "", type=input_type, option=hide_option)
            except TypeError:
                value = dialog.input(heading, default_value or "")
        return _normalize_text(value)


def fetch_clients_json(use_cache=True):
    data = config.fetch_clients_config(use_cache=use_cache)
    if not isinstance(data, dict):
        return {}
    return data


def _clients_list(data):
    raw = (data or {}).get("clients") or (data or {}).get("clientes") or []
    if isinstance(raw, dict):
        raw = list(raw.values())
    return [item for item in raw if isinstance(item, dict)]


def _is_active(client):
    value = client.get("active", client.get("ativo", True))
    if str(value).strip().lower() in ("false", "0", "no", "nao", "não", "off", "blocked", "bloqueado"):
        return False
    expires = _normalize_text(client.get("expires") or client.get("expira"))
    if expires:
        try:
            if expires < time.strftime("%Y-%m-%d"):
                return False
        except Exception:
            pass
    return True


def _client_name(client):
    return _normalize_text(client.get("name") or client.get("nome") or client.get("id") or "cliente")


def _client_password(client):
    return _normalize_text(client.get("password") or client.get("senha") or client.get("pass"))


def _show_welcome(client):
    client_name = _client_name(client) or "cliente"
    bonequinho = "\n".join([
        "♪  \\o/  ♪",
        "    |",
        "   / \\" 
    ])
    xbmcgui.Dialog().ok(
        "FILMOM",
        "Bem-vindo, %s!\n\n%s\n\nAcesso liberado. A interface será carregada agora." % (client_name, bonequinho)
    )


def _find_client_by_password(password, data=None):
    data = data or fetch_clients_json(use_cache=True)
    variants = _password_variants(password)
    for client in _clients_list(data):
        stored = _client_password(client)
        if stored and stored in variants:
            return client
    return None


def validate_password(password, data=None):
    client = _find_client_by_password(password, data=data)
    if not client:
        return False, None, "Senha inválida."
    if not _is_active(client):
        return False, client, "Senha bloqueada."
    return True, client, "Acesso liberado."


def _ask_password(default_value=""):
    return keyboard_input(PASSWORD_PROMPT, hidden=False, default_value=default_value)


def _save_success(password, client):
    client_id = _normalize_text(client.get("id") or _client_name(client))
    client_name = _client_name(client)
    _write_auth({
        "authenticated": True,
        "schema": "filmom-simple-clients-v1",
        "client_id": client_id,
        "client_name": client_name,
        "client_password": _normalize_text(password)
    })
    config.set_setting("client_password", _normalize_text(password))
    config.set_setting("authenticated_client", client_id)


def _load_saved_password():
    saved = _read_auth().get("client_password") or config.get_setting("client_password", "")
    return _normalize_text(saved)


def _finish_success(password, client, silent=False):
    _save_success(password, client)
    has_servers = config.has_credentials()
    if silent:
        # Em acessos já autenticados, force a releitura do servers.json para que
        # mudanças publicadas no GitHub, como troca do servidor 2, sejam aplicadas
        # sem reinstalar o addon. Se a rede falhar, config preserva o servidor local.
        refreshed = config.refresh_servers_from_source(use_cache=False)
        has_servers = refreshed or config.has_credentials()
    elif not has_servers:
        has_servers = config.refresh_servers_from_source(use_cache=False)
    if not silent:
        _show_welcome(client)
    if not has_servers:
        xbmcgui.Dialog().notification("FILMOM", "Acesso liberado. Cadastre servidores no servers.json.", xbmcgui.NOTIFICATION_WARNING, 3500)
    if not silent:
        config.set_setting(POST_LOGIN_REFRESH_SETTING, "true")
    return True


def consume_post_login_refresh():
    flag = config.get_setting(POST_LOGIN_REFRESH_SETTING, "")
    if str(flag).strip().lower() == "true":
        config.set_setting(POST_LOGIN_REFRESH_SETTING, "")
        return True
    return False


def require_access():
    """Valida o cliente pelo `clients.json` simples e instala `servers.json`."""
    clients_data = fetch_clients_json(use_cache=True)
    if not _clients_list(clients_data):
        clients_data = fetch_clients_json(use_cache=False)
    if not _clients_list(clients_data):
        xbmcgui.Dialog().ok("FILMOM", "Nenhum cliente ativo foi cadastrado no clients.json do FILMOM. Cadastre pelo menos um cliente com password e active=true.")
        return False

    saved_password = _load_saved_password()
    if saved_password:
        ok, client, _message = validate_password(saved_password, data=clients_data)
        if ok:
            return _finish_success(saved_password, client, silent=True)
        reset_auth()

    password = _ask_password("")
    if not password:
        return False

    ok, client, message = validate_password(password, data=clients_data)
    if not ok:
        xbmcgui.Dialog().notification("FILMOM", message or "Senha inválida ou bloqueada.", xbmcgui.NOTIFICATION_ERROR, 3500)
        return False
    return _finish_success(password, client, silent=False)


# Compatibilidade com nomes usados em versões intermediárias.
def logout():
    reset_auth()
    xbmcgui.Dialog().notification("FILMOM", "Login removido.", xbmcgui.NOTIFICATION_INFO, 2500)


def ensure_auth():
    return require_access()
