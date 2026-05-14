# -*- coding: utf-8 -*-
"""Atualização do FILMOM por manifesto GitHub.

Manifesto esperado:
{
  "version": "1.0.1",
  "zip_url": "https://github.com/usuario/repositorio/releases/download/v1.0.1/plugin.video.filmom-1.0.1.zip",
  "sha256": "opcional",
  "notes": "Notas da versão"
}
"""

from __future__ import absolute_import, unicode_literals

import hashlib
import json
import os
import time
import urllib.request

import xbmc
import xbmcgui
import xbmcvfs

from resources.lib import config

USER_AGENT = "FILMOM-Updater/1.0"
UPDATE_CHECK_INTERVAL_SECONDS = 12 * 60 * 60
LAST_UPDATE_CHECK_SETTING = "filmom_last_update_check"


def _version_tuple(value):
    try:
        return tuple(int(part) for part in str(value).split(".") if part.isdigit())
    except Exception:
        return (0,)


def current_version():
    return config.ADDON.getAddonInfo("version")


def packages_dir():
    home = config._translate("special://home/addons/packages/")
    if not xbmcvfs.exists(home):
        try:
            xbmcvfs.mkdirs(home)
        except Exception:
            os.makedirs(home, exist_ok=True)
    return home


def fetch_manifest():
    url = config.manifest_url()
    if not url or "SEU-USUARIO" in url:
        return None
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read().decode("utf-8", "ignore")
        return json.loads(raw)
    except Exception as exc:
        xbmc.log("[FILMOM] Falha ao buscar manifesto de atualização: %s" % exc, xbmc.LOGWARNING)
        return None


def has_update(manifest):
    if not manifest:
        return False
    return _version_tuple(manifest.get("version", "0")) > _version_tuple(current_version())


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_update(manifest):
    zip_url = manifest.get("zip_url")
    version = manifest.get("version", "nova")
    if not zip_url:
        return None
    target = os.path.join(packages_dir(), "plugin.video.filmom-%s.zip" % version)
    request = urllib.request.Request(zip_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        with open(target, "wb") as handle:
            handle.write(response.read())
    expected = (manifest.get("sha256") or "").strip().lower()
    if expected and sha256_file(target).lower() != expected:
        try:
            os.remove(target)
        except Exception:
            pass
        raise ValueError("SHA-256 do pacote não confere")
    return target


def _should_check_now(force=False):
    if force:
        return True
    try:
        last = int(config.get_setting(LAST_UPDATE_CHECK_SETTING, "0") or "0")
    except Exception:
        last = 0
    return int(time.time()) - last >= UPDATE_CHECK_INTERVAL_SECONDS


def _mark_checked():
    try:
        config.set_setting(LAST_UPDATE_CHECK_SETTING, str(int(time.time())))
    except Exception:
        pass


def check_interactive(force=False):
    if not force and config.get_setting("auto_update", "true") != "true":
        return
    if not _should_check_now(force=force):
        return
    manifest = fetch_manifest()
    if manifest is not None:
        _mark_checked()
    if not has_update(manifest):
        if force:
            xbmcgui.Dialog().notification("FILMOM", "Nenhuma atualização encontrada.", xbmcgui.NOTIFICATION_INFO, 3500)
        return
    version = manifest.get("version")
    notes = manifest.get("notes", "Atualização disponível.")
    if xbmcgui.Dialog().yesno("FILMOM", "Nova versão disponível: %s\n\n%s\n\nBaixar agora?" % (version, notes)):
        try:
            path = download_update(manifest)
            xbmcgui.Dialog().ok("FILMOM", "Pacote baixado com sucesso:\n%s\n\nInstale pelo Kodi em: Add-ons > Instalar a partir de arquivo ZIP. Em instalações por repositório, o Kodi atualizará automaticamente." % path)
        except Exception as exc:
            xbmcgui.Dialog().ok("FILMOM", "Falha ao baixar atualização:\n%s" % exc)
