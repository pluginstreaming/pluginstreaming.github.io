# -*- coding: utf-8 -*-
"""Camada de reprodução do FILMOM.

A partir da v1.0.24, o addon usa somente um fluxo de reprodução nativo do Kodi.
A reprodução direta reduz travamentos, falsos negativos de inicialização e quedas
causadas por servidores locais intermediários.
"""

from __future__ import absolute_import, unicode_literals

import re
import sys
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

USER_AGENT = "Mozilla/5.0 (Linux; Android 11; Kodi) AppleWebKit/537.36 FILMOM/1.0"
COMMON_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Connection": "keep-alive",
    "Icy-MetaData": "0",
}


def _filmom_log(message, level=None):
    try:
        xbmc.log("[FILMOM] %s" % message, level if level is not None else xbmc.LOGINFO)
    except Exception:
        pass


def _split_url_headers(url):
    if "|" not in (url or ""):
        return url or "", {}
    base, header_text = url.split("|", 1)
    parsed = {}
    for key, values in urllib.parse.parse_qs(header_text, keep_blank_values=True).items():
        if values:
            parsed[key] = values[-1]
    return base, parsed


def _headers_string(extra=None):
    headers = dict(COMMON_HEADERS)
    headers.update(extra or {})
    return urllib.parse.urlencode(headers)


def _url_with_headers(url, extra=None):
    base, existing = _split_url_headers(url)
    existing.update(extra or {})
    return base + "|" + _headers_string(existing)


def _extension_from_url(url):
    base, _headers = _split_url_headers(url)
    path = urllib.parse.urlparse(base).path.lower()
    match = re.search(r"\.([a-z0-9]{2,5})$", path)
    return match.group(1) if match else ""


def _mime_for_url(url):
    ext = _extension_from_url(url)
    if ext == "ts":
        return "video/mp2t"
    if ext == "m3u8":
        return "application/vnd.apple.mpegurl"
    if ext == "mkv":
        return "video/x-matroska"
    if ext == "avi":
        return "video/x-msvideo"
    if ext in ("mpd", "dash"):
        return "application/dash+xml"
    if ext == "mp4":
        return "video/mp4"
    return "video/mp4"


def _safe_call(obj, method, *args, **kwargs):
    try:
        getattr(obj, method)(*args, **kwargs)
    except Exception:
        pass


def _is_hls(url):
    return _extension_from_url(url) == "m3u8" or ".m3u8" in (url or "").lower()


def _is_dash(url):
    ext = _extension_from_url(url)
    return ext in ("mpd", "dash") or ".mpd" in (url or "").lower()


def choose_playback_url(url, fallback_url=""):
    """Escolhe a melhor URL direta para o player único.

    Quando existir uma URL de fallback explícita, ela tem prioridade. Isso permite
    que canais ao vivo tentem HLS/M3U8 antes do TS direto, quando o servidor
    disponibilizar ambos, sem depender de componentes intermediários.
    """
    fallback = (fallback_url or "").strip()
    primary = (url or "").strip()
    return fallback or primary


def apply_fast_playback_properties(item, url, mediatype="video"):
    """Aplica propriedades seguras para reprodução nativa sem servidor intermediário."""
    item.setProperty("IsPlayable", "true")
    item.setProperty("mediatype", mediatype or "video")
    item.setProperty("FILMOM.Player", "NATIVE_SINGLE_PLAYER")
    _safe_call(item, "setMimeType", _mime_for_url(url))
    _safe_call(item, "setContentLookup", False)

    if _is_hls(url) or _is_dash(url):
        # Kodi 19+ aceita inputstream via propriedade moderna. Em versões antigas,
        # a chamada é ignorada pelo `_safe_call`, preservando compatibilidade.
        item.setProperty("inputstream", "inputstream.adaptive")
        item.setProperty("inputstream.adaptive.manifest_type", "hls" if _is_hls(url) else "mpd")
        item.setProperty("inputstream.adaptive.stream_headers", _headers_string())
        item.setProperty("inputstream.adaptive.manifest_headers", _headers_string())
        item.setProperty("inputstream.adaptive.license_key", "")
    return item


def playable_item(title, url, thumb="", fanart="", plot="", mediatype="video"):
    item = xbmcgui.ListItem(label=title or "FILMOM")
    art = thumb or fanart
    item.setArt({"icon": art, "thumb": art, "poster": art, "fanart": fanart or thumb})
    item.setInfo("video", {
        "title": title or "FILMOM",
        "plot": plot or "Sinopse não informada pelo servidor.",
        "mediatype": mediatype or "video"
    })
    selected_url = _url_with_headers(url)
    apply_fast_playback_properties(item, selected_url, mediatype)
    item.setPath(selected_url)
    return item


def resolve(url, title="FILMOM", thumb="", fanart="", plot="", fallback_url=""):
    selected_url = choose_playback_url(url, fallback_url)
    if not selected_url:
        xbmcgui.Dialog().notification("FILMOM", "URL de reprodução inválida.", xbmcgui.NOTIFICATION_ERROR, 4000)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
        return
    _filmom_log("Player único nativo: resolvendo %s" % _extension_from_url(selected_url), xbmc.LOGINFO)
    item = playable_item(title, selected_url, thumb, fanart, plot)
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)


def add_context_play_properties(item, url):
    return apply_fast_playback_properties(item, _url_with_headers(url))
