# -*- coding: utf-8 -*-
"""0bx0d? -- DPI bypass tool v3.4"""
import ctypes, hashlib, json, math, os, random, shutil, socket, struct, subprocess, sys
import tempfile, time, webbrowser, winreg, zipfile
import urllib.request
from datetime import datetime
from pathlib import Path

import psutil
from PySide6.QtCore import (
    Qt, QThread, QObject, Signal, QTimer, QPoint, QPointF,
    QRect, QRectF, QSize,
)
from PySide6.QtGui import (
    QColor, QPainter, QFont, QPen, QBrush, QRadialGradient,
    QLinearGradient, QPixmap, QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFrame, QComboBox, QSizePolicy,
    QStackedWidget, QScrollArea,
)

# =====================================================================
#  CONSTANTS
# =====================================================================
APP_NAME = "0bx0d"
VERSION  = "4.4.1"
BIN_DIR  = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "bin"
ZAPRET_DIR = BIN_DIR / "zapret"
ZAPRET_V1  = BIN_DIR / "zapret-v1"
REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"

# -- palette --
BG       = "#0e0e12"
SURFACE  = "#131318"
CARD     = "#1a1a22"
CARD2    = "#20202c"
BORDER   = "#252530"
ACCENT   = "#e53935"
ACCENT2  = "#ff5252"
ACCENT_DK= "#7f1d1d"
GREEN    = "#4caf50"
GREEN2   = "#66bb6a"
YELLOW   = "#ffc107"
ORANGE   = "#ff6d00"
TEXT     = "#e0e0e6"
TEXT2    = "#8e8ea0"
TEXT3    = "#4a4a5a"

# =====================================================================
#  LOCALIZATION (EN / RU)
# =====================================================================
LANG_REG_KEY = r"Software\0bx0d\Settings"

def get_lang() -> str:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, LANG_REG_KEY, 0, winreg.KEY_QUERY_VALUE)
        v = winreg.QueryValueEx(k, "Language")[0]; winreg.CloseKey(k)
        return v if v in ("en", "ru") else "en"
    except: return "en"

def set_lang(lang: str):
    try:
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, LANG_REG_KEY)
        winreg.SetValueEx(k, "Language", 0, winreg.REG_SZ, lang)
        winreg.CloseKey(k)
    except: pass

_STRINGS = {
    # Sidebar
    "nav_dashboard":      {"en": "Dashboard",      "ru": "Главная"},
    "nav_logs":           {"en": "Session Logs",    "ru": "Логи сессии"},
    "nav_settings":       {"en": "Settings",        "ru": "Настройки"},
    "nav_dns":            {"en": "DNS Manager",     "ru": "DNS Менеджер"},
    "nav_info":           {"en": "About",           "ru": "О программе"},
    # Dashboard
    "view_source":        {"en": "View Source",     "ru": "Исходный код"},
    "open_source_tool":   {"en": "Open source DPI bypass tool",
                           "ru": "DPI bypass с открытым кодом"},
    "engine":             {"en": "ENGINE",           "ru": "ДВИЖОК"},
    "preset":             {"en": "PRESET",          "ru": "ПРЕСЕТ"},
    "custom_lua":         {"en": "CUSTOM LUA ARGS", "ru": "СВОЙ LUA СКРИПТ"},
    "custom_lua_hint":    {"en": "winws2 args for Custom preset",
                           "ru": "Аргументы winws2 для кастомного пресета"},
    "live_logs":          {"en": "LIVE LOGS",       "ru": "ЛОГИ"},
    "autostart":          {"en": "Autostart",       "ru": "Автозапуск"},
    "kill_switch":        {"en": "Kill Switch",     "ru": "Kill Switch"},
    "auto_bypass":        {"en": "Auto-bypass",     "ru": "Авто-обход"},
    # Settings
    "settings":           {"en": "SETTINGS",        "ru": "НАСТРОЙКИ"},
    "startup":            {"en": "STARTUP",         "ru": "ЗАПУСК"},
    "launch_on_login":    {"en": "Launch on Windows login",
                           "ru": "Запускать при входе в Windows"},
    "auto_activate_launch": {"en": "Auto-activate bypass on launch",
                             "ru": "Автоматически включать обход при запуске"},
    "protection":         {"en": "PROTECTION",      "ru": "ЗАЩИТА"},
    "auto_restart":       {"en": "Auto-restart on unexpected exit",
                           "ru": "Перезапускать при неожиданном завершении"},
    "presets_info":       {"en": "PRESETS INFO",    "ru": "ИНФОРМАЦИЯ О ПРЕСЕТАХ"},
    "language":           {"en": "LANGUAGE",         "ru": "ЯЗЫК"},
    # Logs
    "session_log":        {"en": "SESSION LOG",     "ru": "ЛОГ СЕССИИ"},
    # DNS
    "dns_manager":        {"en": "DNS MANAGER",     "ru": "DNS МЕНЕДЖЕР"},
    "refresh":            {"en": "Refresh",         "ru": "Обновить"},
    "check_all":          {"en": "Check All",       "ru": "Проверить"},
    "adapter":            {"en": "Adapter",         "ru": "Адаптер"},
    "servers":            {"en": "SERVERS",          "ru": "СЕРВЕРЫ"},
    "original_not_saved": {"en": "Original DNS not saved yet",
                           "ru": "Оригинальный DNS ещё не сохранён"},
    "apply_selected":     {"en": "Apply Selected",  "ru": "Применить"},
    "restore_original":   {"en": "Restore Original","ru": "Восстановить"},
    "reset_dhcp":         {"en": "Reset to DHCP",   "ru": "Сброс DHCP"},
    "dns_log":            {"en": "DNS LOG",          "ru": "DNS ЛОГ"},
    # Info / About
    "info_subtitle":      {"en": "Open source DPI bypass tool for Windows",
                           "ru": "DPI bypass для Windows с открытым кодом"},
    "how_it_works":       {"en": "HOW IT WORKS",    "ru": "КАК ЭТО РАБОТАЕТ"},
    "how_desc": {
        "en": ("GoodbyeDPI intercepts TCP/UDP packets at the kernel level via "
               "the WinDivert driver and modifies their headers — fragmentation, "
               "wrong checksums, fake ACK packets — so that your ISP's deep "
               "packet inspection (DPI) system can't correctly reassemble the "
               "stream and lets the connection through unblocked.\n\n"
               "When you select a Discord preset, the tool writes target domains "
               "(discord.com, discordapp.com, etc.) to a temporary blacklist file "
               "and passes it to GoodbyeDPI via the --blacklist flag. This ensures "
               "only Discord traffic is intercepted, leaving everything else untouched."),
        "ru": ("GoodbyeDPI перехватывает TCP/UDP пакеты на уровне ядра через "
               "драйвер WinDivert и модифицирует их заголовки — фрагментация, "
               "неверные контрольные суммы, фейковые ACK пакеты — чтобы DPI "
               "система вашего провайдера не могла правильно собрать поток "
               "и пропускала соединение без блокировки.\n\n"
               "Когда вы выбираете пресет Discord, инструмент записывает целевые домены "
               "(discord.com, discordapp.com и т.д.) во временный файл блеклиста "
               "и передаёт его GoodbyeDPI через флаг --blacklist. Так перехватывается "
               "только трафик Discord, остальное остаётся нетронутым."),
    },
    "features":           {"en": "FEATURES",        "ru": "ФУНКЦИИ"},
    "features_list": {
        "en": [
            "4 presets: Discord Only, Discord + Game, All Traffic, Stealth",
            "Kill switch: auto-restarts GoodbyeDPI if it crashes",
            "DNS Manager: change system DNS with latency checker",
            "Save & restore original DNS settings",
            "Autostart: launch on Windows login",
            "Frameless custom UI with dark theme",
            "Network status monitoring (discord.com ping)",
        ],
        "ru": [
            "4 пресета: Discord Only, Discord + Game, All Traffic, Stealth",
            "Kill switch: автоперезапуск GoodbyeDPI при падении",
            "DNS Менеджер: смена системного DNS с проверкой задержки",
            "Сохранение и восстановление оригинального DNS",
            "Автозапуск: запуск при входе в Windows",
            "Кастомный интерфейс без рамки с тёмной темой",
            "Мониторинг сети (пинг discord.com)",
        ],
    },
    "tech_details":       {"en": "TECHNICAL DETAILS","ru": "ТЕХНИЧЕСКИЕ ДЕТАЛИ"},
    "engine":             {"en": "Engine",           "ru": "Движок"},
    "driver":             {"en": "Driver",           "ru": "Драйвер"},
    "framework":          {"en": "Framework",        "ru": "Фреймворк"},
    "platform":           {"en": "Platform",         "ru": "Платформа"},
    "dns_check":          {"en": "DNS Check",        "ru": "DNS Проверка"},
    "license_lbl":        {"en": "License",          "ru": "Лицензия"},
    "driver_val":         {"en": "WinDivert (kernel-level packet interception)",
                           "ru": "WinDivert (перехват пакетов на уровне ядра)"},
    "platform_val":       {"en": "Windows 10 / 11 (x64, requires admin)",
                           "ru": "Windows 10 / 11 (x64, нужен администратор)"},
    "dns_check_val":      {"en": "Raw UDP query to google.com (port 53)",
                           "ru": "Прямой UDP запрос к google.com (порт 53)"},
    "license_val":        {"en": "MIT — free and open source",
                           "ru": "MIT — бесплатно и с открытым кодом"},
    "not_malware":        {"en": "not malware, just raw code",
                           "ru": "не вирус, просто код"},
    # License dialog
    "activation":         {"en": "Activation",       "ru": "Активация"},
    "enter_key":          {"en": "Enter your license key to continue",
                           "ru": "Введите лицензионный ключ для продолжения"},
    "activate_btn":       {"en": "Activate",         "ru": "Активировать"},
    "validating":         {"en": "Validating...",     "ru": "Проверка..."},
    # Startup messages
    "init_boot":          {"en": "Init: {name}? v{ver} booting...",
                           "ru": "Запуск: {name}? v{ver} загрузка..."},
    "admin_ok":           {"en": "✓ admin: OK",       "ru": "✓ админ: ОК"},
    "admin_miss":         {"en": "✗ admin: MISSING — restart as admin",
                           "ru": "✗ админ: НЕТ — перезапустите от админа"},
    "missing_file":       {"en": "✗ missing: {f}",    "ru": "✗ не найден: {f}"},
    "driver_ok":          {"en": "✓ driver files: OK", "ru": "✓ файлы драйвера: ОК"},
    "net_reachable":      {"en": "Network: discord.com → reachable",
                           "ru": "Сеть: discord.com → доступен"},
    "net_blocked":        {"en": "ERROR: Discord RTC blocked.",
                           "ru": "ОШИБКА: Discord RTC заблокирован."},
    "auto_bypass_start":  {"en": "⚡ Auto-bypass enabled — starting DPI tunnel...",
                           "ru": "⚡ Авто-обход включён — запуск DPI туннеля..."},
    "awaiting":           {"en": "Status: Awaiting Activation...",
                           "ru": "Статус: Ожидание активации..."},
    "activated_msg":      {"en": "▶ ACTIVATED. enjoy your freedom.",
                           "ru": "▶ АКТИВИРОВАНО. наслаждайся свободой."},
    "deactivated_msg":    {"en": "■ deactivated.",
                           "ru": "■ деактивировано."},
    "orig_saved":         {"en": "Original saved:  {p}  /  {s}",
                           "ru": "Оригинал сохранён:  {p}  /  {s}"},
    "orig_first_change":  {"en": "Original DNS will be saved on first change",
                           "ru": "Оригинальный DNS сохранится при первом изменении"},
    "adapters_refreshed": {"en": "✓ adapters refreshed",
                           "ru": "✓ адаптеры обновлены"},
    # Updater
    "updates":            {"en": "UPDATES",          "ru": "ОБНОВЛЕНИЯ"},
    "check_updates":      {"en": "Check for updates","ru": "Проверить обновления"},
    "checking_updates":   {"en": "Checking...",      "ru": "Проверка..."},
    "update_available":   {"en": "Update {ver} available!",
                           "ru": "Доступно обновление {ver}!"},
    "no_updates":         {"en": "You have the latest version",
                           "ru": "У вас последняя версия"},
    "download_update":    {"en": "Download & Install","ru": "Скачать и установить"},
    "downloading":        {"en": "Downloading... {pct}%",
                           "ru": "Загрузка... {pct}%"},
    "installing":         {"en": "Installing update, app will restart...",
                           "ru": "Установка обновления, приложение перезапустится..."},
    "update_failed":      {"en": "Update failed. Download manually from GitHub.",
                           "ru": "Ошибка обновления. Скачайте вручную с GitHub."},
    "current_version":    {"en": "Current: v{ver}",  "ru": "Текущая: v{ver}"},
}

_current_lang = get_lang()

def tr(key: str, **kwargs) -> str:
    """Get translated string."""
    s = _STRINGS.get(key, {}).get(_current_lang, key)
    if kwargs:
        try: return s.format(**kwargs)
        except: return s
    return s

def tr_list(key: str) -> list[str]:
    """Get translated list."""
    return _STRINGS.get(key, {}).get(_current_lang, [])

# -- discord domains (written to temp file for --blacklist) --
# Full list from GoodbyeDPI-Discord + zapret-discord-youtube + official issues
DISCORD_DOMAINS = [
    "discord.com",
    "discordapp.com",
    "discordapp.net",
    "discord.gg",
    "discord.media",
    "discordcdn.com",
    "discord.co",
    "discord.dev",
    "discord.new",
    "discord.gift",
    "discord.gifts",
    "discord.design",
    "discord.store",
    "discord.tools",
    "discordmerch.com",
    "discordpartygames.com",
    "discord-activities.com",
    "discordactivities.com",
    "discordsays.com",
    "cdn.discordapp.com",
    "media.discordapp.net",
    "images-ext-1.discordapp.net",
    "images-ext-2.discordapp.net",
    "gateway.discord.gg",
    "router.discord.com",
    "status.discord.com",
    "dl.discordapp.net",
    "updates.discord.com",
    "latency.discord.media",
    "discord-attachments-uploads-prd.storage.googleapis.com",
    "dis.gd",
]
_blacklist_path: str | None = None

def _ensure_blacklist_file() -> str:
    global _blacklist_path
    if _blacklist_path and os.path.exists(_blacklist_path):
        return _blacklist_path
    fd, path = tempfile.mkstemp(prefix="0bx0d_bl_", suffix=".txt")
    with os.fdopen(fd, "w") as f:
        for d in DISCORD_DOMAINS:
            f.write(d + "\n")
    _blacklist_path = path
    return path

# Presets: based on official GoodbyeDPI recommendations + community configs
# -9 = default mode: -f 2 -e 2 --wrong-seq --wrong-chksum --reverse-frag --max-payload -q
# For Russia: -9 + DNS redir to Yandex 77.88.8.8:1253 (official script)
# For aggressive TSPU: add --set-ttl or --auto-ttl + --frag-by-sni
PRESETS = {
    "Discord (Russia — recommended)": {
        "mode": "DISCORD",
        "desc": "-9 + Yandex DNS (official RU config)",
        "args": ["-9",
                 "--dns-addr","77.88.8.8","--dns-port","1253",
                 "--dnsv6-addr","2a02:6b8::feed:0ff","--dnsv6-port","1253"],
    },
    "Discord (Russia — TTL)": {
        "mode": "DISCORD",
        "desc": "-9 + auto-TTL + frag-by-SNI (stronger)",
        "args": ["-9","--auto-ttl","1-4-10","--frag-by-sni",
                 "--dns-addr","77.88.8.8","--dns-port","1253",
                 "--dnsv6-addr","2a02:6b8::feed:0ff","--dnsv6-port","1253"],
    },
    "Discord (Russia — Aggressive)": {
        "mode": "DISCORD",
        "desc": "-9 + set-ttl 4 + fake packets (max bypass)",
        "args": ["-9","--set-ttl","4","--frag-by-sni",
                 "--fake-gen","5","--fake-resend","3",
                 "--dns-addr","77.88.8.8","--dns-port","1253",
                 "--dnsv6-addr","2a02:6b8::feed:0ff","--dnsv6-port","1253"],
    },
    "Discord (Standard)": {
        "mode": "DISCORD",
        "desc": "-9 default (non-Russia)",
        "args": ["-9"],
    },
    "All Traffic (Russia)": {
        "mode": "ALL",
        "desc": "-9 + Yandex DNS (all sites)",
        "args": ["-9",
                 "--dns-addr","77.88.8.8","--dns-port","1253",
                 "--dnsv6-addr","2a02:6b8::feed:0ff","--dnsv6-port","1253"],
    },
    "All Traffic (Standard)": {
        "mode": "ALL",
        "desc": "-9 default (all sites)",
        "args": ["-9"],
    },
    "Discord (Russia — Simple Fake)": {
        "mode": "DISCORD",
        "desc": "wrong-seq + wrong-chksum + frag (lite -9)",
        "args": ["-p","-r","-s","-e","2",
                 "--wrong-chksum","--wrong-seq",
                 "--dns-addr","77.88.8.8","--dns-port","1253",
                 "--dnsv6-addr","2a02:6b8::feed:0ff","--dnsv6-port","1253"],
    },
    "Discord (Russia — Auto-TTL)": {
        "mode": "DISCORD",
        "desc": "auto-ttl + frag-by-SNI + DNS (alt strategy)",
        "args": ["-p","-r","-s","-e","2",
                 "--auto-ttl","1-4-10","--frag-by-sni",
                 "--dns-addr","77.88.8.8","--dns-port","1253",
                 "--dnsv6-addr","2a02:6b8::feed:0ff","--dnsv6-port","1253"],
    },
}

# -- Zapret engine presets --
ZAPRET_PRESETS = {
    "Discord (Zapret — recommended)": {
        "engine": "zapret",
        "desc": "fake TLS + split SNI + QUIC fake (best for RU)",
        "args": [
            "--wf-tcp-out=443", "--wf-udp-out=443,50000-65535",
            "--filter-tcp=443", "--filter-l7=tls",
            "--payload=tls_client_hello",
            "--lua-desync=fake:blob=fake_tls:tcp_md5",
            "--lua-desync=multisplit:pos=1,midsld",
            "--new",
            "--filter-udp=443", "--filter-l7=quic",
            "--payload=quic_initial",
            "--lua-desync=fake:blob=fake_quic:repeats=6",
            "--new",
            "--filter-udp=50000-65535",
            "--lua-desync=fake:blob=fake_stun:repeats=2",
        ],
        "blobs": {
            "fake_tls": "fake/tls_clienthello_iana_org.bin",
            "fake_quic": "fake/quic_initial_www_google_com.bin",
            "fake_stun": "fake/stun.bin",
        },
    },
    "Discord (Zapret — Voice Fix)": {
        "engine": "zapret",
        "desc": "UDP desync for Voice/RTC (STUN/Discord)",
        "args": [
            "--wf-tcp-out=443", "--wf-udp-out=443,50000-65535",
            "--filter-tcp=443", "--filter-l7=tls",
            "--payload=tls_client_hello",
            "--lua-desync=fake:blob=fake_tls:tcp_md5:tcp_seq=-10000",
            "--lua-desync=multidisorder:pos=1,midsld",
            "--new",
            "--filter-udp=443", "--filter-l7=quic",
            "--payload=quic_initial",
            "--lua-desync=fake:blob=fake_quic:repeats=6",
            "--new",
            "--filter-udp=50000-65535",
            "--lua-desync=fake:blob=fake_discord:repeats=4",
        ],
        "blobs": {
            "fake_tls": "fake/tls_clienthello_iana_org.bin",
            "fake_quic": "fake/quic_initial_www_google_com.bin",
            "fake_discord": "fake/discord-ip-discovery-with-port.bin",
        },
    },
    "All Traffic (Zapret)": {
        "engine": "zapret",
        "desc": "HTTP + TLS + QUIC bypass (all sites)",
        "args": [
            "--wf-tcp-out=80,443", "--wf-udp-out=443",
            "--filter-tcp=80", "--filter-l7=http",
            "--payload=http_req",
            "--lua-desync=fake:blob=0x00000000000000000000:tcp_md5",
            "--lua-desync=multisplit:pos=method+2",
            "--new",
            "--filter-tcp=443", "--filter-l7=tls",
            "--payload=tls_client_hello",
            "--lua-desync=fake:blob=fake_tls:tcp_md5",
            "--lua-desync=multisplit:pos=1,midsld",
            "--new",
            "--filter-udp=443", "--filter-l7=quic",
            "--payload=quic_initial",
            "--lua-desync=fake:blob=fake_quic:repeats=6",
        ],
        "blobs": {
            "fake_tls": "fake/tls_clienthello_iana_org.bin",
            "fake_quic": "fake/quic_initial_www_google_com.bin",
        },
    },
    "Custom Lua Script": {
        "engine": "zapret",
        "desc": "user-defined script (edit in settings)",
        "args": [],
        "custom": True,
    },
    "Discord (Flowseal — SIMPLE FAKE)": {
        "engine": "flowseal",
        "desc": "Flowseal v1 — tested on RU ISPs (best compat)",
        "args": [],
    },
}

def _blacklist_args(mode: str) -> list[str]:
    if mode == "DISCORD":
        return ["--blacklist", _ensure_blacklist_file()]
    return []

DNS_SERVERS = {
    "Google":     ("8.8.8.8",        "8.8.4.4"),
    "Cloudflare": ("1.1.1.1",        "1.0.0.1"),
    "Quad9":      ("9.9.9.9",        "149.112.112.112"),
    "AdGuard":    ("94.140.14.14",   "94.140.15.15"),
    "OpenDNS":    ("208.67.222.222", "208.67.220.220"),
    "Yandex":     ("77.88.8.8",      "77.88.8.1"),
}

# =====================================================================
#  LICENSE SYSTEM
# =====================================================================
# -- PASTE YOUR FIREBASE DATABASE URL BELOW --
FIREBASE_DB_URL  = "https://obxod-64191-default-rtdb.europe-west1.firebasedatabase.app"
LICENSE_REG_KEY  = r"Software\0bx0d\License"
OFFLINE_GRACE    = 7 * 86400  # 7 days offline grace period

def _key_hash(key: str) -> str:
    return hashlib.sha256(key.strip().upper().encode()).hexdigest()

def _validate_online(key: str) -> dict | None:
    """Check key against Firebase. Returns key data or None on error."""
    try:
        h = _key_hash(key)
        url = f"{FIREBASE_DB_URL}/keys/{h}.json"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        return data  # None if key not found, dict if found
    except Exception:
        return None

def _save_license(key: str, expires: int):
    try:
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, LICENSE_REG_KEY)
        winreg.SetValueEx(k, "Key", 0, winreg.REG_SZ, key.strip().upper())
        winreg.SetValueEx(k, "Validated", 0, winreg.REG_SZ, str(int(time.time())))
        winreg.SetValueEx(k, "Expires", 0, winreg.REG_SZ, str(expires))
        winreg.CloseKey(k)
    except Exception:
        pass

def _load_license() -> tuple[str, int, int] | None:
    """Returns (key, last_validated, expires) or None."""
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, LICENSE_REG_KEY, 0, winreg.KEY_READ)
        key = winreg.QueryValueEx(k, "Key")[0]
        val = int(winreg.QueryValueEx(k, "Validated")[0])
        exp = int(winreg.QueryValueEx(k, "Expires")[0])
        winreg.CloseKey(k)
        return (key, val, exp)
    except Exception:
        return None

def _clear_license():
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, LICENSE_REG_KEY)
    except Exception:
        pass

def check_license() -> tuple[bool, str]:
    """Returns (valid, message)."""
    saved = _load_license()
    if not saved:
        return False, "No license key found"

    key, last_val, expires = saved
    now = int(time.time())

    # Try online validation
    data = _validate_online(key)
    if data is not None:
        # Key found in database
        if not data.get("active", False):
            _clear_license()
            return False, "License has been revoked"
        exp = data.get("expires", 0)
        if exp > 0 and exp < now:
            _clear_license()
            return False, "License has expired"
        _save_license(key, exp)
        return True, "License valid"
    elif data is None and saved:
        # Could be network error OR key not in database
        # Check if key was previously validated (offline grace)
        if now - last_val > OFFLINE_GRACE:
            return False, "Offline validation expired (7 days)"
        if expires > 0 and expires < now:
            _clear_license()
            return False, "License has expired"
        return True, "License valid (offline)"

    return False, "Invalid license key"

def activate_key(key: str) -> tuple[bool, str]:
    """Validate a new key and save if valid. Returns (success, message)."""
    key = key.strip().upper()
    if not key:
        return False, "Enter a license key"

    data = _validate_online(key)
    if data is None:
        return False, "Key not found or network error"
    if not data.get("active", False):
        return False, "This key has been revoked"
    now = int(time.time())
    exp = data.get("expires", 0)
    if exp > 0 and exp < now:
        return False, "This key has expired"

    _save_license(key, exp)
    plan = data.get("plan", "?")
    if exp == 0:
        return True, f"Activated! Plan: lifetime"
    days_left = max(1, (exp - now) // 86400)
    return True, f"Activated! Plan: {plan} ({days_left}d left)"

# =====================================================================
#  FONTS
# =====================================================================
def ui_font(px: int, bold=False) -> QFont:
    f = QFont()
    f.setFamilies(["Segoe UI", "Inter", "Roboto", "Arial"])
    f.setPixelSize(px)
    if bold: f.setWeight(QFont.Weight.DemiBold)
    return f

def mono_font(px: int, bold=False) -> QFont:
    f = QFont()
    f.setFamilies(["JetBrains Mono", "Cascadia Code", "Consolas", "Courier New"])
    f.setPixelSize(px)
    if bold: f.setWeight(QFont.Weight.Bold)
    return f

def title_font(px: int) -> QFont:
    f = QFont()
    f.setFamilies(["Cascadia Code", "JetBrains Mono", "Consolas", "Courier New"])
    f.setPixelSize(px); f.setWeight(QFont.Weight.Bold)
    return f

# =====================================================================
#  ADMIN / AUTOSTART
# =====================================================================
def is_admin() -> bool:
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except: return False

def relaunch_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join(f'"{a}"' for a in sys.argv), None, 1)
    sys.exit(0)

# =====================================================================
#  AUTO-UPDATER (GitHub Releases)
# =====================================================================
GITHUB_REPO = "Freezonplay070/0bx0d"
GITHUB_API  = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

def _parse_version(tag: str) -> tuple[int, ...]:
    """Parse 'v3.4' or '3.4' into (3, 4)."""
    tag = tag.lstrip("vV").strip()
    parts = []
    for p in tag.split("."):
        try: parts.append(int(p))
        except: parts.append(0)
    return tuple(parts) or (0,)

def check_update() -> tuple[bool, str, str]:
    """Check GitHub for newer version. Returns (has_update, new_version, zip_url)."""
    try:
        req = urllib.request.Request(GITHUB_API,
              headers={"Accept": "application/vnd.github.v3+json",
                       "User-Agent": f"0bx0d/{VERSION}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        tag = data.get("tag_name", "")
        remote = _parse_version(tag)
        local  = _parse_version(VERSION)
        if remote > local:
            zip_url = ""
            for asset in data.get("assets", []):
                if asset["name"].lower().endswith(".zip"):
                    zip_url = asset["browser_download_url"]; break
            return True, tag, zip_url
        return False, tag, ""
    except Exception:
        return False, "", ""

def download_update(zip_url: str, progress_cb=None) -> str | None:
    """Download ZIP to temp dir. Returns path or None on failure."""
    try:
        req = urllib.request.Request(zip_url,
              headers={"User-Agent": f"0bx0d/{VERSION}"})
        resp = urllib.request.urlopen(req, timeout=120)
        total = int(resp.headers.get("Content-Length", 0))
        fd, path = tempfile.mkstemp(prefix="0bx0d_update_", suffix=".zip")
        downloaded = 0
        with os.fdopen(fd, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk: break
                f.write(chunk); downloaded += len(chunk)
                if progress_cb and total > 0:
                    progress_cb(int(downloaded * 100 / total))
        return path
    except Exception:
        return None

def apply_update(zip_path: str) -> bool:
    """Extract update ZIP over current installation and restart."""
    try:
        if getattr(sys, "frozen", False):
            app_dir = Path(sys.executable).resolve().parent
            exe_path = Path(sys.executable).resolve()
        else:
            app_dir = Path(__file__).resolve().parent
            exe_path = Path(sys.executable).resolve()
        exe_name = exe_path.name

        # Extract to temp dir first
        tmp_dir = tempfile.mkdtemp(prefix="0bx0d_upd_")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)

        # ZIP may contain a single wrapper folder (e.g. "0bx0d/0bx0d.exe")
        # Detect it and use the inner folder as the copy source
        src_dir = tmp_dir
        children = os.listdir(tmp_dir)
        if len(children) == 1:
            candidate = os.path.join(tmp_dir, children[0])
            if os.path.isdir(candidate):
                src_dir = candidate

        # Build the batch updater script
        # Key: wait in a loop until the EXE is actually gone, then robocopy
        bat_path = os.path.join(tempfile.gettempdir(), "0bx0d_updater.bat")
        with open(bat_path, "w", encoding="utf-8") as bat:
            bat.write(f"""@echo off
chcp 65001 >nul
title 0bx0d updater
echo [0bx0d] Waiting for app to close...
:waitloop
tasklist /fi "imagename eq {exe_name}" 2>nul | find /i "{exe_name}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto waitloop
)
echo [0bx0d] App closed. Copying files...
xcopy /s /y /q "{src_dir}\\*" "{app_dir}\\" >nul 2>&1
if errorlevel 1 (
    echo [0bx0d] xcopy failed, trying robocopy...
    robocopy "{src_dir}" "{app_dir}" /s /is /it /r:3 /w:1 >nul 2>&1
)
echo [0bx0d] Restarting...
start "" "{exe_path}"
timeout /t 3 /nobreak >nul
rmdir /s /q "{tmp_dir}" >nul 2>&1
del /q "{zip_path}" >nul 2>&1
del /q "%~f0" >nul 2>&1
exit
""")
        subprocess.Popen(["cmd", "/c", bat_path],
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
        return True
    except Exception:
        return False

def set_autostart(on: bool):
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0,
                           winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
        if on:
            val = (sys.executable if getattr(sys, "frozen", False)
                   else f'"{sys.executable}" "{os.path.abspath(__file__)}"')
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, val)
        else:
            try: winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError: pass
        winreg.CloseKey(k)
    except: pass

def get_autostart() -> bool:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_QUERY_VALUE)
        winreg.QueryValueEx(k, APP_NAME); winreg.CloseKey(k); return True
    except: return False

AUTO_ACTIVATE_REG = r"Software\0bx0d\Settings"

def set_auto_activate(on: bool):
    try:
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, AUTO_ACTIVATE_REG)
        winreg.SetValueEx(k, "AutoActivate", 0, winreg.REG_SZ, "1" if on else "0")
        winreg.CloseKey(k)
    except: pass

def get_auto_activate() -> bool:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTO_ACTIVATE_REG, 0, winreg.KEY_QUERY_VALUE)
        v = winreg.QueryValueEx(k, "AutoActivate")[0]; winreg.CloseKey(k)
        return v == "1"
    except: return False

# =====================================================================
#  DNS UTILITIES
# =====================================================================
_original_dns: dict[str, str] = {}

def get_adapters() -> list[str]:
    try:
        r = subprocess.run(["netsh", "interface", "show", "interface"],
                           capture_output=True, text=True, timeout=5)
        out = []
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] in ("Connected", "Enabled", u"Підключено"):
                out.append(" ".join(parts[3:]))
        return out or ["Wi-Fi", "Ethernet"]
    except: return ["Wi-Fi", "Ethernet"]

def get_dns_ips(adapter: str) -> tuple[str, str]:
    try:
        r = subprocess.run(["netsh", "interface", "ip", "show", "dns", adapter],
                           capture_output=True, text=True, timeout=5)
        ips = []
        for line in r.stdout.splitlines():
            for p in line.strip().split():
                if p.count(".") == 3:
                    try: socket.inet_aton(p); ips.append(p)
                    except: pass
        return (ips[0] if ips else "", ips[1] if len(ips) > 1 else "")
    except: return ("", "")

def save_original_dns(adapter: str):
    if adapter not in _original_dns:
        p, s = get_dns_ips(adapter)
        _original_dns[adapter] = f"{p},{s}"

def get_original_dns(adapter: str) -> tuple[str, str]:
    raw = _original_dns.get(adapter, ",")
    parts = raw.split(",", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")

def check_dns_latency(server_ip: str) -> float | None:
    try:
        tid = random.randint(1, 65535)
        hdr = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)
        qname = b"\x06google\x03com\x00"
        question = qname + struct.pack(">HH", 1, 1)
        query = hdr + question
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2.0)
        t0 = time.perf_counter()
        s.sendto(query, (server_ip, 53))
        s.recv(512)
        ms = (time.perf_counter() - t0) * 1000
        s.close()
        return round(ms, 1)
    except: return None

# =====================================================================
#  WORKERS
# =====================================================================
class UpdateWorker(QObject):
    """Background update checker/downloader."""
    check_done  = Signal(bool, str, str)  # has_update, version, zip_url
    dl_progress = Signal(int)             # percent 0-100
    dl_done     = Signal(bool, str)       # success, zip_path
    apply_done  = Signal(bool)

    _do_check    = Signal()
    _do_download = Signal(str)
    _do_apply    = Signal(str)

    def __init__(self):
        super().__init__()
        self._do_check.connect(self._check)
        self._do_download.connect(self._download)
        self._do_apply.connect(self._apply)

    def check(self):   self._do_check.emit()
    def download(self, url): self._do_download.emit(url)
    def apply(self, path):   self._do_apply.emit(path)

    def _check(self):
        has, ver, url = check_update()
        self.check_done.emit(has, ver, url)

    def _download(self, url):
        path = download_update(url, lambda p: self.dl_progress.emit(p))
        self.dl_done.emit(path is not None, path or "")

    def _apply(self, path):
        ok = apply_update(path)
        self.apply_done.emit(ok)


class TunnelWorker(QObject):
    log     = Signal(str)
    started = Signal()
    stopped = Signal()
    error   = Signal(str)
    _go     = Signal(list, bool)

    def __init__(self):
        super().__init__()
        self._proc = None; self._run = False
        self._cmd = []; self._ks = False
        self._go.connect(self._start)

    def launch(self, preset_name: str, ks: bool, custom_args: str = ""):
        p = PRESETS.get(preset_name) or ZAPRET_PRESETS.get(preset_name)
        if not p:
            p = list(PRESETS.values())[0]
        engine = p.get("engine", "gdpi")
        if engine == "flowseal":
            cmd = self._build_flowseal_cmd()
        elif engine == "zapret":
            cmd = self._build_zapret_cmd(p, custom_args)
        else:
            cmd = [str(BIN_DIR / "goodbyedpi.exe")] + p["args"] + _blacklist_args(p.get("mode", "ALL"))
        self._engine = engine
        self._go.emit(cmd, ks)

    def _build_zapret_cmd(self, preset: dict, custom_args: str = "") -> list[str]:
        exe = str(ZAPRET_DIR / "winws2.exe")
        lua_dir = str(ZAPRET_DIR / "lua")
        cmd = [exe,
               f"--lua-init=@{lua_dir}/zapret-lib.lua",
               f"--lua-init=@{lua_dir}/zapret-antidpi.lua"]
        if preset.get("custom") and custom_args.strip():
            import shlex
            cmd += shlex.split(custom_args)
        else:
            # Add blob references
            for name, fpath in preset.get("blobs", {}).items():
                cmd += [f"--blob={name}:@{ZAPRET_DIR / fpath}"]
            cmd += preset.get("args", [])
        return cmd

    def _build_flowseal_cmd(self) -> list[str]:
        d = ZAPRET_V1
        exe = str(d / "winws.exe")
        bl = str(d / "lists" / "list-general.txt")
        gl = str(d / "lists" / "list-google.txt")
        fq = str(d / "fake" / "quic_initial_www_google_com.bin")
        fd = str(d / "fake" / "quic_initial_dbankcloud_ru.bin")
        ft = str(d / "fake" / "tls_clienthello_www_google_com.bin")
        fs = str(d / "fake" / "stun.bin")
        fm = str(d / "fake" / "tls_clienthello_max_ru.bin")
        return [exe,
            "--wf-tcp=80,443", "--wf-udp=443,19294-19344,50000-50100",
            "--filter-udp=443", f"--hostlist={bl}",
            "--dpi-desync=fake", "--dpi-desync-repeats=6",
            f"--dpi-desync-fake-quic={fq}", "--new",
            "--filter-udp=19294-19344,50000-50100",
            "--filter-l7=discord,stun",
            "--dpi-desync=fake", "--dpi-desync-repeats=6",
            f"--dpi-desync-fake-discord={fd}",
            f"--dpi-desync-fake-stun={fd}", "--new",
            "--filter-tcp=443", f"--hostlist={gl}",
            "--dpi-desync=fake", "--dpi-desync-repeats=6",
            "--dpi-desync-fooling=ts",
            f"--dpi-desync-fake-tls={ft}", "--new",
            "--filter-tcp=80,443", f"--hostlist={bl}",
            "--dpi-desync=fake", "--dpi-desync-repeats=6",
            "--dpi-desync-fooling=ts",
            f"--dpi-desync-fake-tls={ft}",
            f"--dpi-desync-fake-http={fm}",
        ]

    def _kill_old(self):
        targets = {"goodbyedpi.exe", "winws2.exe", "winws.exe"}
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                if (proc.info["name"] or "").lower() in targets:
                    proc.kill(); proc.wait(3)
            except: pass

    def _start(self, cmd, ks):
        self._run = True; self._cmd = cmd; self._ks = ks
        self._kill_old()
        self.log.emit("→ " + " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            self.started.emit()
            self._watch()
        except OSError as e:
            self.error.emit(str(e))

    def _watch(self):
        t_start = time.monotonic()
        while self._run:
            if not self._proc: break
            if self._proc.poll() is not None:
                uptime = time.monotonic() - t_start
                if self._run and self._ks:
                    if uptime < 5:
                        self.error.emit(
                            "Process exited in <5s — likely a config error. "
                            "Kill switch disabled to prevent loop.")
                        break
                    self.log.emit("⚡ kill switch triggered, restarting...")
                    time.sleep(1); self._kill_old()
                    try:
                        self._proc = subprocess.Popen(
                            self._cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW)
                        t_start = time.monotonic()
                        continue
                    except OSError as e:
                        self.error.emit(str(e)); break
                else:
                    self.stopped.emit(); break
            if self._proc and self._proc.stdout:
                line = self._proc.stdout.readline()
                if line:
                    text = line.decode("utf-8", "replace").strip()
                    if text:
                        self.log.emit(text)
            else:
                time.sleep(0.05)

    def stop(self):
        self._run = False
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try: self._proc.wait(4)
            except: self._proc.kill()
        self._proc = None; self._kill_old(); self.stopped.emit()


class PingWorker(QObject):
    result  = Signal(object)
    _active = False

    def run(self):
        self._active = True
        while self._active:
            try:
                s = socket.socket(); s.settimeout(2.5)
                t0 = time.perf_counter()
                s.connect(("discord.com", 443))
                self.result.emit(round((time.perf_counter() - t0) * 1000, 1))
                s.close()
            except:
                self.result.emit(None)
            time.sleep(5)

    def stop(self): self._active = False


class DnsWorker(QObject):
    log           = Signal(str)
    done          = Signal(bool, str)
    _go           = Signal(str, str, str)
    _rst          = Signal(str)
    check_all_req = Signal()
    dns_result    = Signal(str, object)

    def __init__(self):
        super().__init__()
        self._go.connect(self._apply)
        self._rst.connect(self._reset)
        self.check_all_req.connect(self._check_all)

    def apply(self, adapter, primary, secondary): self._go.emit(adapter, primary, secondary)
    def reset(self, adapter): self._rst.emit(adapter)
    def check_latency(self): self.check_all_req.emit()

    def _apply(self, adapter, primary, secondary):
        save_original_dns(adapter)
        self.log.emit(f"Applying DNS → {primary}" + (f" / {secondary}" if secondary else ""))
        try:
            subprocess.run(["netsh", "interface", "ip", "set", "dns", adapter, "static", primary],
                           capture_output=True, timeout=8)
            if secondary:
                subprocess.run(["netsh", "interface", "ip", "add", "dns", adapter, secondary, "index=2"],
                               capture_output=True, timeout=8)
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=5)
            self.done.emit(True, f"✓ DNS set to {primary}")
        except Exception as e:
            self.done.emit(False, f"✗ DNS error: {e}")

    def _reset(self, adapter):
        orig_p, orig_s = get_original_dns(adapter)
        if orig_p:
            self.log.emit(f"Restoring DNS → {orig_p}")
            try:
                subprocess.run(["netsh", "interface", "ip", "set", "dns", adapter, "static", orig_p],
                               capture_output=True, timeout=8)
                if orig_s:
                    subprocess.run(["netsh", "interface", "ip", "add", "dns", adapter, orig_s, "index=2"],
                                   capture_output=True, timeout=8)
                subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=5)
                self.done.emit(True, f"✓ Original DNS restored ({orig_p})")
                return
            except Exception as e:
                self.done.emit(False, f"✗ {e}"); return
        self.log.emit("Resetting DNS → DHCP auto")
        try:
            subprocess.run(["netsh", "interface", "ip", "set", "dns", adapter, "dhcp"],
                           capture_output=True, timeout=8)
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=5)
            self.done.emit(True, "✓ DNS reset to auto (DHCP)")
        except Exception as e:
            self.done.emit(False, f"✗ {e}")

    def _check_all(self):
        self.log.emit("Checking DNS latency...")
        for name, (ip, _) in DNS_SERVERS.items():
            ms = check_dns_latency(ip)
            self.dns_result.emit(name, ms)
        self.log.emit("✓ Latency check complete")

# =====================================================================
#  BACKGROUND FRAME
# =====================================================================
_NOISE_PIX: QPixmap | None = None

def _get_noise(w, h) -> QPixmap:
    global _NOISE_PIX
    if _NOISE_PIX and _NOISE_PIX.width() >= w and _NOISE_PIX.height() >= h:
        return _NOISE_PIX
    pix = QPixmap(w, h); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); rng = random.Random(42)
    for _ in range(w * h // 14):
        x, y = rng.randint(0, w - 1), rng.randint(0, h - 1)
        v = rng.randint(130, 210); a = rng.randint(2, 5)
        p.setPen(QColor(v, v, v, a)); p.drawPoint(x, y)
    p.end(); _NOISE_PIX = pix; return pix


class BgFrame(QWidget):
    def paintEvent(self, _):
        p = QPainter(self); r = self.rect()
        p.fillRect(r, QColor(BG))
        p.drawPixmap(0, 0, _get_noise(r.width(), r.height()))
        g = QRadialGradient(r.width() / 2, r.height() / 2, max(r.width(), r.height()) * 0.6)
        g.setColorAt(0.0, QColor(20, 8, 8, 6))
        g.setColorAt(0.6, QColor(0, 0, 0, 0))
        g.setColorAt(1.0, QColor(0, 0, 0, 80))
        p.fillRect(r, g); p.end()

# =====================================================================
#  CARD
# =====================================================================
class Card(QWidget):
    def __init__(self, parent=None, radius=10):
        super().__init__(parent); self._r = radius

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(QColor(CARD)); p.setPen(QPen(QColor(BORDER), 1))
        p.drawRoundedRect(r, self._r, self._r)
        g = QLinearGradient(0, 0, 0, 24)
        g.setColorAt(0, QColor(255, 255, 255, 5)); g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, self._r, self._r)
        p.end()

# =====================================================================
#  GLITCH TITLE (animated title with RGB split)
# =====================================================================
class GlitchTitle(QWidget):
    def __init__(self, text, px=17, parent=None):
        super().__init__(parent)
        self._text = text; self._px = px
        self._ox = 0; self._oy = 0; self._glitch = False
        self._scan = 0.0  # scanline position
        self.setFixedHeight(px + 8)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedWidth(self._px * len(text) // 2 + 30)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(70)

    def _tick(self):
        if random.random() < 0.04:
            self._glitch = True
            self._ox = random.choice([-3, -2, -1, 1, 2, 3])
            self._oy = random.choice([-1, 0, 1])
        else:
            self._glitch = False; self._ox = 0; self._oy = 0
        self._scan = (self._scan + 0.07) % 1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        f = title_font(self._px)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        p.setFont(f)
        r = self.rect()
        ox, oy = self._ox, self._oy

        if self._glitch:
            # Red channel offset
            p.setPen(QColor(255, 0, 0, 90))
            p.drawText(r.translated(ox + 2, oy), Qt.AlignmentFlag.AlignVCenter, self._text)
            # Cyan channel offset
            p.setPen(QColor(0, 200, 220, 50))
            p.drawText(r.translated(ox - 2, oy), Qt.AlignmentFlag.AlignVCenter, self._text)

        # Main text
        p.setPen(QColor(TEXT))
        p.drawText(r.translated(ox, oy), Qt.AlignmentFlag.AlignVCenter, self._text)

        # Subtle scanline
        scan_y = int(self._scan * self.height())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 6))
        p.drawRect(0, scan_y, self.width(), 2)
        p.end()

# =====================================================================
#  SIDEBAR BUTTON
# =====================================================================
class SideBtn(QWidget):
    clicked = Signal()

    def __init__(self, icon_id: str, tooltip="", parent=None):
        super().__init__(parent)
        self._id = icon_id; self._tip = tooltip
        self._hover = False; self._active = False
        self.setFixedSize(54, 44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip: self.setToolTip(tooltip)

    def set_active(self, v): self._active = v; self.update()
    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        if self._active:
            p.fillRect(r, QColor(26, 14, 14))
            p.fillRect(QRectF(0, 6, 2.5, r.height() - 12), QColor(ACCENT))
        elif self._hover:
            p.fillRect(r, QColor(22, 18, 20))

        col = QColor(ACCENT) if self._active else (QColor(TEXT2) if self._hover else QColor(TEXT3))
        cx, cy = r.width() / 2, r.height() / 2
        pen = QPen(col, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)

        if self._id == "home":
            s = 5
            for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                rc = QRectF(cx + dx * 5.5 - s / 2, cy + dy * 5 - s / 2, s, s)
                p.setBrush(col if self._active else Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rc, 1.5, 1.5)
            p.setBrush(Qt.BrushStyle.NoBrush)
        elif self._id == "logs":
            for i, w in enumerate([16, 12, 15]):
                y = cy - 6 + i * 6
                p.drawLine(QPointF(cx - w / 2, y), QPointF(cx + w / 2, y))
        elif self._id == "settings":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), 7.5, 7.5)
            p.setBrush(col); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, cy), 2.5, 2.5)
            p.setPen(pen)
            for angle_deg in range(0, 360, 60):
                a = math.radians(angle_deg)
                x1 = cx + 7.5 * math.cos(a); y1 = cy + 7.5 * math.sin(a)
                x2 = cx + 10 * math.cos(a); y2 = cy + 10 * math.sin(a)
                p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        elif self._id == "dns":
            r2 = 8.5
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r2, r2)
            p.drawLine(QPointF(cx - r2, cy), QPointF(cx + r2, cy))
            path = QPainterPath()
            path.moveTo(cx, cy - r2); path.quadTo(cx - 5, cy, cx, cy + r2)
            p.drawPath(path)
            path2 = QPainterPath()
            path2.moveTo(cx, cy - r2); path2.quadTo(cx + 5, cy, cx, cy + r2)
            p.drawPath(path2)
        elif self._id == "info":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), 8.5, 8.5)
            p.setFont(ui_font(13, bold=True))
            p.drawText(QRect(0, 0, r.width(), r.height()), Qt.AlignmentFlag.AlignCenter, "i")
        p.end()

# =====================================================================
#  STATUS BADGE
# =====================================================================
class StatusBadge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._on = False; self._phase = 0.0
        self.setFixedSize(148, 28)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(40)

    def set_on(self, v): self._on = v; self.update()

    def _tick(self):
        self._phase = (self._phase + 0.06) % (2 * math.pi)
        if self._on: self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())

        if self._on:
            pulse = 0.5 + 0.5 * math.sin(self._phase)
            bg, border = QColor(35, 12, 12), QColor(ACCENT)
            dot_col = QColor(255, int(80 + 80 * pulse), int(60 + 60 * pulse))
            text, text_col = "CONNECTED", QColor(ACCENT)
        else:
            pulse = 0
            bg, border = QColor(20, 20, 26), QColor(BORDER)
            dot_col = QColor(TEXT3)
            text, text_col = "OFFLINE", QColor(TEXT3)

        p.setBrush(bg); p.setPen(QPen(border, 1))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)

        p.setBrush(dot_col); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(16, 14), 3.5, 3.5)
        if self._on:
            g = QRadialGradient(16, 14, 9)
            g.setColorAt(0, QColor(255, 60, 60, int(55 * pulse)))
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(g); p.drawEllipse(QPointF(16, 14), 9, 9)

        f = ui_font(10, bold=True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.8)
        p.setFont(f); p.setPen(text_col)
        p.drawText(QRect(30, 0, self.width() - 32, self.height()),
                   Qt.AlignmentFlag.AlignVCenter, text)
        p.end()

# =====================================================================
#  POWER BUTTON
# =====================================================================
class PowerButton(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False; self._hover = False; self._phase = 0.0
        self.setFixedSize(160, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(30)

    def _tick(self):
        self._phase = (self._phase + 0.04) % (2 * math.pi)
        if self._active or self._hover: self.update()

    def set_active(self, v): self._active = v; self.update()
    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2 - 10
        R = 56

        if self._active:
            pulse = 0.5 + 0.5 * math.sin(self._phase)
            for i in range(4):
                g = QRadialGradient(cx, cy, R + 12 + i * 10)
                g.setColorAt(0, QColor(229, 57, 53, int((35 - i * 7) * (0.6 + 0.4 * pulse))))
                g.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(cx, cy), R + 12 + i * 10, R + 12 + i * 10)
            bg = QRadialGradient(cx, cy - 8, R)
            bg.setColorAt(0, QColor(55, 12, 12)); bg.setColorAt(1, QColor(30, 6, 6))
            p.setBrush(bg)
            p.setPen(QPen(QColor(229, 57, 53, int(160 + 90 * pulse)), 2))
            p.drawEllipse(QPointF(cx, cy), R, R)
            icon_col = QColor(255, 255, 255, 230)
        else:
            bg = QRadialGradient(cx, cy - 8, R)
            bg.setColorAt(0, QColor(32, 32, 42)); bg.setColorAt(1, QColor(22, 22, 30))
            p.setBrush(bg)
            border = QColor(ACCENT) if self._hover else QColor(BORDER)
            p.setPen(QPen(border, 1.5))
            p.drawEllipse(QPointF(cx, cy), R, R)
            icon_col = QColor(ACCENT) if self._hover else QColor(TEXT3)

        pen = QPen(icon_col, 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 18), QPointF(cx, cy - 6))
        arc_r = 16
        arc_rect = QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2)
        p.drawArc(arc_rect, 50 * 16, -280 * 16)

        f = ui_font(10, bold=True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        p.setFont(f)
        label_y = int(cy + R + 14)
        if self._active:
            p.setPen(QColor(ACCENT2))
            p.drawText(QRect(0, label_y, self.width(), 20),
                       Qt.AlignmentFlag.AlignHCenter, "ACTIVE")
        else:
            p.setPen(QColor(ACCENT) if self._hover else QColor(TEXT3))
            p.drawText(QRect(0, label_y, self.width(), 20),
                       Qt.AlignmentFlag.AlignHCenter, "ACTIVATE")
        p.end()

# =====================================================================
#  TOGGLE SWITCH
# =====================================================================
class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, label, checked=False, parent=None):
        super().__init__(parent)
        self._c = checked; self._label = label; self._hover = False
        self._disabled = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def isChecked(self): return self._c
    def setChecked(self, v): self._c = v; self.update()

    def setDisabled(self, v):
        self._disabled = v
        self.setCursor(Qt.CursorShape.ForbiddenCursor if v
                       else Qt.CursorShape.PointingHandCursor)
        if v and self._c:
            self._c = False; self.toggled.emit(False)
        self.update()

    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()
    def mousePressEvent(self, e):
        if self._disabled: return
        if e.button() == Qt.MouseButton.LeftButton:
            self._c = not self._c; self.update(); self.toggled.emit(self._c)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tw, th = 36, 20
        ty = (self.height() - th) // 2
        track = QRectF(0, ty, tw, th)
        if self._disabled:
            p.setBrush(QColor("#1c1c28")); p.setPen(QPen(QColor("#303040"), 1))
        elif self._c:
            p.setBrush(QColor(ACCENT)); p.setPen(Qt.PenStyle.NoPen)
        else:
            p.setBrush(QColor(BORDER)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(track, th / 2, th / 2)

        thumb_r = (th - 6) / 2
        thumb_x = tw - thumb_r - 4 if self._c else thumb_r + 4
        thumb_y = ty + th / 2
        if self._disabled:
            p.setBrush(QColor("#2e2e3c"))
        elif self._c:
            p.setBrush(QColor(255, 255, 255))
        else:
            p.setBrush(QColor(TEXT3))
        p.drawEllipse(QPointF(thumb_x, thumb_y), thumb_r, thumb_r)

        p.setFont(ui_font(12))
        if self._disabled:
            p.setPen(QColor("#50505e"))
        elif self._hover or self._c:
            p.setPen(QColor(TEXT))
        else:
            p.setPen(QColor(TEXT2))
        p.drawText(QRect(tw + 12, 0, 300, self.height()),
                   Qt.AlignmentFlag.AlignVCenter, self._label)
        p.end()

    def sizeHint(self): return QSize(220, 28)

# =====================================================================
#  TERMINAL
# =====================================================================
class Terminal(QTextEdit):
    def __init__(self, compact=False, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        sz = 11 if not compact else 10
        self.document().setDefaultStyleSheet("p{margin:1px 0;padding:0;}")
        self.setStyleSheet(f"""
            QTextEdit {{
                background: #101014; color: {TEXT2};
                border: 1px solid {BORDER}; border-radius: 8px;
                padding: 10px 14px;
                font-family: 'JetBrains Mono','Cascadia Code','Consolas',monospace;
                font-size: {sz}px; line-height: 1.65;
            }}
            QScrollBar:vertical {{
                background: #101014; width: 6px; border: none; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {TEXT3}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._queue: list[str] = []; self._busy = False

    def _col(self, t: str) -> str:
        lo = t.lower()
        if any(x in lo for x in ("error", "✗", "fail", "blocked", "no admin", "missing", "can't")):
            return ACCENT2
        if any(x in lo for x in ("✓", "ok", "activ", "enjoy", "▶", "alive", "success", "set", "restored")):
            return GREEN
        if "⚡" in lo or "warn" in lo or "restart" in lo:
            return ORANGE
        if t.startswith("→"):
            return TEXT3
        return TEXT2

    def queue_line(self, text: str):
        if not text.strip(): return
        ts = datetime.now().strftime("%H:%M:%S")
        col = self._col(text)
        html = (f'<p><span style="color:{TEXT3};font-size:9px">[{ts}]</span>'
                f'&nbsp;<span style="color:{col}">{text}</span></p>')
        self._queue.append(html)
        if not self._busy: self._pop()

    def _pop(self):
        if not self._queue: self._busy = False; return
        self._busy = True; self.append(self._queue.pop(0))
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        QTimer.singleShot(35, self._pop)

# =====================================================================
#  BUTTONS
# =====================================================================
class Btn(QPushButton):
    def __init__(self, text, accent=False, parent=None):
        super().__init__(text, parent)
        self._accent = accent; self._hover = False
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("border:none;background:transparent;")
        # Auto-size: measure text and add padding
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(text) + 40
        self.setMinimumWidth(max(text_w, 90))

    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        if self._accent:
            bg = QColor(40, 12, 12) if self._hover else QColor(28, 8, 8)
            bc = QColor(ACCENT) if self._hover else QColor(ACCENT_DK)
        else:
            bg = QColor(28, 28, 38) if self._hover else QColor(CARD)
            bc = QColor(TEXT3) if self._hover else QColor(BORDER)
        p.setBrush(bg); p.setPen(QPen(bc, 1))
        p.drawRoundedRect(r, 7, 7)

        f = ui_font(11, bold=True)
        p.setFont(f)
        col = QColor(ACCENT2) if (self._hover and self._accent) else \
              QColor(TEXT) if self._hover else QColor(TEXT2)
        p.setPen(col)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()

# =====================================================================
#  DNS CARD (with flash animation on apply)
# =====================================================================
class DnsCard(QWidget):
    selected = Signal(str)
    MAX_MS = 300.0

    def __init__(self, name, ip1, ip2="", parent=None):
        super().__init__(parent)
        self._name = name; self._ip1 = ip1; self._ip2 = ip2
        self._latency: float | None = None
        self._checking = False; self._sel = False; self._hover = False
        self._applied = False   # currently active DNS
        self._flash = 0.0       # flash animation 1.0→0.0
        self.setMinimumWidth(100); self.setFixedHeight(84)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._flash_tmr = QTimer(self)
        self._flash_tmr.timeout.connect(self._flash_tick)

    def set_latency(self, ms): self._latency = ms; self._checking = False; self.update()
    def set_checking(self): self._checking = True; self.update()
    def set_selected(self, v): self._sel = v; self.update()
    def set_applied(self, v):
        self._applied = v
        if v:
            self._flash = 1.0
            self._flash_tmr.start(25)
        self.update()
    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.selected.emit(self._name)

    def _flash_tick(self):
        self._flash = max(0.0, self._flash - 0.04)
        if self._flash <= 0: self._flash_tmr.stop()
        self.update()

    def _lat_color(self, ms: float) -> QColor:
        if ms < 50: return QColor(GREEN)
        if ms < 100: return QColor(YELLOW)
        if ms < 200: return QColor(ORANGE)
        return QColor(ACCENT)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        # Flash glow
        if self._flash > 0:
            glow = QRadialGradient(self.width() / 2, self.height() / 2,
                                   max(self.width(), self.height()) * 0.6)
            glow.setColorAt(0, QColor(76, 175, 80, int(60 * self._flash)))
            glow.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(glow); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r.adjusted(-4, -4, 4, 4), 12, 12)

        bg = QColor(30, 14, 14) if self._sel else (QColor(28, 28, 38) if self._hover else QColor(CARD))
        if self._applied: bc = QColor(GREEN)
        elif self._sel: bc = QColor(ACCENT)
        elif self._hover: bc = QColor(TEXT3)
        else: bc = QColor(BORDER)
        bw = 1.5 if (self._applied or self._sel) else 1
        p.setBrush(bg); p.setPen(QPen(bc, bw))
        p.drawRoundedRect(r, 8, 8)

        # Applied indicator
        if self._applied:
            p.fillRect(QRectF(1, 10, 3, r.height() - 18), QColor(GREEN))
        elif self._sel:
            p.fillRect(QRectF(1, 10, 3, r.height() - 18), QColor(ACCENT))

        # Name
        p.setFont(ui_font(12, bold=True))
        name_col = QColor(GREEN2) if self._applied else \
                   (QColor(TEXT) if (self._sel or self._hover) else QColor(TEXT2))
        p.setPen(name_col)
        p.drawText(QRect(12, 8, self.width() - 14, 20), Qt.AlignmentFlag.AlignLeft, self._name)

        # Applied badge
        if self._applied:
            badge_f = ui_font(8, bold=True)
            p.setFont(badge_f); p.setPen(QColor(GREEN))
            p.drawText(QRect(12, 8, self.width() - 20, 20),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "ACTIVE")

        # IP
        p.setFont(mono_font(9)); p.setPen(QColor(TEXT3))
        p.drawText(QRect(12, 26, self.width() - 14, 14), Qt.AlignmentFlag.AlignLeft, self._ip1)

        # Latency bar
        bar_x, bar_y, bar_h = 12, 44, 6
        bar_w = self.width() - 24
        p.setBrush(QColor(18, 18, 24)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)

        if self._checking:
            p.setBrush(QColor(35, 25, 25))
            p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w * 0.3, bar_h), 3, 3)
        elif self._latency is not None:
            fill = min(1.0, self._latency / self.MAX_MS)
            col = self._lat_color(self._latency)
            g = QLinearGradient(bar_x, 0, bar_x + bar_w * fill, 0)
            g.setColorAt(0, col)
            g.setColorAt(1, QColor(col.red() // 2, col.green() // 2, col.blue() // 2))
            p.setBrush(g)
            p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w * fill, bar_h), 3, 3)

        # Latency text
        p.setFont(mono_font(9, bold=True))
        if self._checking:
            p.setPen(QColor(TEXT3)); txt = "checking..."
        elif self._latency is None:
            p.setPen(QColor(TEXT3)); txt = "—"
        else:
            p.setPen(self._lat_color(self._latency))
            txt = f"{self._latency:.0f} ms"
        p.drawText(QRect(12, 54, self.width() - 14, 18), Qt.AlignmentFlag.AlignLeft, txt)
        p.end()

# =====================================================================
#  TITLE BAR
# =====================================================================
class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self._win = parent; self._drag = QPoint()
        self.setFixedHeight(44)
        self.setStyleSheet(f"background:{SURFACE};")
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 8, 0); lay.setSpacing(0)
        lay.addSpacing(56)

        div = QFrame(); div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet(f"color:{BORDER}; max-width:1px;"); lay.addWidget(div)
        lay.addSpacing(14)

        self._gtitle = GlitchTitle("0bx0d?", 17)
        lay.addWidget(self._gtitle)
        lay.addSpacing(10)

        # Version pill badge
        ver = QLabel(f" v{VERSION} ")
        ver.setFont(mono_font(9))
        ver.setFixedHeight(18)
        ver.setStyleSheet(
            f"color:{TEXT3}; background:{CARD}; border:1px solid {BORDER};"
            "border-radius:9px; padding:0 6px;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ver, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch()

        self._badge = StatusBadge(); lay.addWidget(self._badge)
        lay.addSpacing(14)

        for sym, slot in [("—", parent.showMinimized), ("✕", parent.close)]:
            btn = QPushButton(sym); btn.setFixedSize(32, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{TEXT3};border:none;"
                "font-size:14px;font-weight:700;border-radius:5px;}"
                f"QPushButton:hover{{background:{BORDER};color:{TEXT};}}")
            btn.clicked.connect(slot); lay.addWidget(btn)

    def set_connected(self, on): self._badge.set_on(on)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and not self._drag.isNull():
            self._win.move(e.globalPosition().toPoint() - self._drag)

# =====================================================================
#  HELPERS
# =====================================================================
def section_label(text: str, bright: bool = False) -> QLabel:
    lbl = QLabel(text)
    f = ui_font(11, bold=True)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
    lbl.setFont(f)
    color = TEXT2 if bright else TEXT3
    lbl.setStyleSheet(f"color:{color};")
    return lbl

def hdiv() -> QFrame:
    f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{BORDER}; max-height:1px;")
    return f

def info_row(label: str, value: str) -> QHBoxLayout:
    h = QHBoxLayout(); h.setSpacing(12)
    l = QLabel(label); l.setFont(ui_font(11, bold=True)); l.setStyleSheet(f"color:{TEXT3};")
    l.setFixedWidth(120); h.addWidget(l)
    v = QLabel(value); v.setFont(ui_font(11)); v.setStyleSheet(f"color:{TEXT2};")
    v.setWordWrap(True); h.addWidget(v, 1)
    return h

# =====================================================================
#  GLOBAL STYLESHEET
# =====================================================================
QSS = f"""
* {{ color: {TEXT}; }}
QWidget {{ background: transparent; }}
QComboBox {{
    background: {CARD}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 7px 14px;
    font-family: 'Segoe UI','Inter','Roboto',sans-serif; font-size: 13px;
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: none; }}
QComboBox QAbstractItemView {{
    background: {CARD}; color: {TEXT}; border: 1px solid {BORDER};
    selection-background-color: {BORDER}; selection-color: {ACCENT2};
    font-family: 'Segoe UI',sans-serif; font-size: 13px; outline: none; padding: 4px;
}}
QScrollBar:horizontal {{ height: 0; }}
QToolTip {{
    background: {CARD}; color: {TEXT}; border: 1px solid {BORDER};
    font-family: 'Segoe UI',sans-serif; padding: 6px 8px; font-size: 12px;
}}
"""

# =====================================================================
#  LICENSE DIALOG
# =====================================================================
class LicenseDialog(QMainWindow):
    """Activation window shown when no valid license is found."""
    activated = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(460, 340)
        self.setWindowTitle("0bx0d? — Activation")
        self._success = False
        self._drag = QPoint()
        self._setup_ui()

    def _setup_ui(self):
        root = BgFrame(); self.setCentralWidget(root)
        vl = QVBoxLayout(root); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(0)

        # Title bar
        tbar = QWidget(); tbar.setFixedHeight(40)
        tbar.setStyleSheet(f"background:{SURFACE};")
        tl = QHBoxLayout(tbar); tl.setContentsMargins(16, 0, 8, 0)
        t = QLabel("0bx0d?"); t.setFont(title_font(14))
        t.setStyleSheet(f"color:{TEXT};"); tl.addWidget(t)
        tl.addStretch()
        close_btn = QPushButton("✕"); close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{TEXT3};border:none;"
            "font-size:13px;border-radius:4px;}"
            f"QPushButton:hover{{background:{BORDER};color:{TEXT};}}")
        close_btn.clicked.connect(self.close)
        tl.addWidget(close_btn)
        vl.addWidget(tbar)
        vl.addWidget(hdiv())

        # Content
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(36, 28, 36, 28); cl.setSpacing(16)

        title = QLabel(tr("activation"))
        title.setFont(ui_font(22, bold=True))
        title.setStyleSheet(f"color:{TEXT};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(title)

        hint = QLabel(tr("enter_key"))
        hint.setFont(ui_font(12)); hint.setStyleSheet(f"color:{TEXT3};")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(hint)

        cl.addSpacing(4)

        from PySide6.QtWidgets import QLineEdit
        self._input = QLineEdit()
        self._input.setPlaceholderText("0BX0D-XXXXX-XXXXX-XXXXX-XXXXX")
        self._input.setFont(mono_font(14))
        self._input.setFixedHeight(44)
        self._input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {CARD}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 8px; padding: 0 16px;
                selection-background-color: {ACCENT};
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self._input.returnPressed.connect(self._do_activate)
        cl.addWidget(self._input)

        self._act_btn = Btn(tr("activate_btn"), accent=True)
        self._act_btn.setFixedHeight(42)
        self._act_btn.clicked.connect(self._do_activate)
        cl.addWidget(self._act_btn)

        self._status = QLabel("")
        self._status.setFont(ui_font(11))
        self._status.setStyleSheet(f"color:{TEXT3};")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        cl.addWidget(self._status)

        cl.addStretch()
        vl.addWidget(content)

    def _do_activate(self):
        key = self._input.text().strip()
        self._status.setText(tr("validating"))
        self._status.setStyleSheet(f"color:{TEXT2};")
        QApplication.processEvents()

        ok, msg = activate_key(key)
        if ok:
            self._status.setText(msg)
            self._status.setStyleSheet(f"color:{GREEN};")
            self._success = True
            QTimer.singleShot(800, self.close)
        else:
            self._status.setText(msg)
            self._status.setStyleSheet(f"color:{ACCENT2};")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and not self._drag.isNull():
            self.move(e.globalPosition().toPoint() - self._drag)

# =====================================================================
#  MAIN WINDOW
# =====================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(800, 580); self.resize(840, 620)
        self.setWindowTitle("0bx0d?")
        self._on = False; self._ping = None
        self._dns_sel: str | None = None
        self._dns_applied: str | None = None
        self._setup_ui(); self._setup_workers()
        QTimer.singleShot(250, self._startup)

    def _setup_ui(self):
        root = BgFrame(); self.setCentralWidget(root)
        hl = QHBoxLayout(root); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(0)

        sb = QWidget(); sb.setFixedWidth(54)
        sb.setStyleSheet(f"background:{SURFACE};")
        sl = QVBoxLayout(sb); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(2)
        sl.addSpacing(46)
        self._sbs = [
            SideBtn("home", tr("nav_dashboard")),
            SideBtn("logs", tr("nav_logs")),
            SideBtn("settings", tr("nav_settings")),
            SideBtn("dns", tr("nav_dns")),
            SideBtn("info", tr("nav_info")),
        ]
        self._sbs[0].set_active(True)
        for b in self._sbs: sl.addWidget(b)
        sl.addStretch()
        hl.addWidget(sb)

        right = QWidget()
        rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0); rv.setSpacing(0)
        self._tbar = TitleBar(self); rv.addWidget(self._tbar)
        rv.addWidget(hdiv())
        self._stack = QStackedWidget()
        for page in [self._build_dash(), self._build_logs(),
                     self._build_sett(), self._build_dns(), self._build_info()]:
            self._stack.addWidget(page)
        rv.addWidget(self._stack)
        hl.addWidget(right)

        for i, b in enumerate(self._sbs):
            b.clicked.connect(lambda _=None, idx=i: self._nav(idx))

    def _nav(self, i):
        self._stack.setCurrentIndex(i)
        for j, b in enumerate(self._sbs): b.set_active(j == i)

    # -- DASHBOARD --
    def _build_dash(self) -> QWidget:
        page = QWidget()
        vl = QVBoxLayout(page); vl.setContentsMargins(24, 20, 24, 16); vl.setSpacing(14)

        top = QHBoxLayout(); top.setSpacing(20)
        self._pwr = PowerButton(); self._pwr.clicked.connect(self._toggle)
        top.addWidget(self._pwr, 0, Qt.AlignmentFlag.AlignVCenter)

        rc = Card(radius=10); rc_vl = QVBoxLayout(rc)
        rc_vl.setContentsMargins(18, 16, 18, 16); rc_vl.setSpacing(10)

        src_btn = Btn(tr("view_source"), accent=True); src_btn.setFixedHeight(42)
        src_btn.clicked.connect(
            lambda: webbrowser.open("https://github.com/Freezonplay070/0bx0d"))
        rc_vl.addWidget(src_btn)

        sub = QLabel(tr("open_source_tool"))
        sub.setFont(ui_font(11)); sub.setStyleSheet(f"color:{TEXT3};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter); rc_vl.addWidget(sub)

        rc_vl.addWidget(hdiv())
        rc_vl.addWidget(section_label(tr("engine")))
        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["GoodbyeDPI", "Zapret v2", "Zapret Flowseal"])
        self._engine_combo.currentIndexChanged.connect(self._on_engine_change)
        rc_vl.addWidget(self._engine_combo)
        rc_vl.addSpacing(4)
        rc_vl.addWidget(section_label(tr("preset")))
        self._preset = QComboBox()
        self._preset.addItems(list(PRESETS.keys()))
        rc_vl.addWidget(self._preset); rc_vl.addStretch()
        top.addWidget(rc)
        vl.addLayout(top)

        lc = Card(radius=10); lc_vl = QVBoxLayout(lc)
        lc_vl.setContentsMargins(14, 12, 14, 12); lc_vl.setSpacing(6)
        lc_vl.addWidget(section_label(tr("live_logs")))
        self._term = Terminal(compact=True)
        self._term.setMinimumHeight(110); self._term.setMaximumHeight(150)
        lc_vl.addWidget(self._term)
        vl.addWidget(lc)

        bot = QHBoxLayout(); bot.setSpacing(24)
        self._auto = ToggleSwitch(tr("autostart"), get_autostart())
        self._auto.toggled.connect(self._on_autostart_toggle)
        self._ks = ToggleSwitch(tr("kill_switch"), True)
        self._auto_act = ToggleSwitch(tr("auto_bypass"), get_auto_activate())
        self._auto_act.setDisabled(not get_autostart())
        self._auto_act.toggled.connect(set_auto_activate)
        bot.addWidget(self._auto); bot.addWidget(self._ks)
        bot.addWidget(self._auto_act); bot.addStretch()
        bl = QLabel("by solevoyq")
        bl.setFont(ui_font(10)); bl.setStyleSheet(f"color:{TEXT3};")
        bot.addWidget(bl)
        vl.addLayout(bot)
        return page

    # -- LOGS --
    def _build_logs(self) -> QWidget:
        page = QWidget()
        vl = QVBoxLayout(page); vl.setContentsMargins(24, 20, 24, 16)
        vl.addWidget(section_label(tr("session_log"))); vl.addSpacing(6)
        self._full = Terminal(); vl.addWidget(self._full)
        return page

    # -- SETTINGS --
    def _build_sett(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea{{border:none;background:transparent;}}"
            f" QScrollBar:vertical{{width:6px;background:transparent;}}"
            f" QScrollBar::handle:vertical{{background:{BORDER};border-radius:3px;}}"
            f" QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )
        page = QWidget()
        vl = QVBoxLayout(page); vl.setContentsMargins(24, 20, 24, 16); vl.setSpacing(14)
        vl.addWidget(section_label(tr("settings"))); vl.addWidget(hdiv())

        c1 = Card(radius=10); c1l = QVBoxLayout(c1)
        c1l.setContentsMargins(20, 18, 20, 18); c1l.setSpacing(14)

        c1l.addWidget(section_label(tr("startup"), bright=True))
        a2 = ToggleSwitch(tr("launch_on_login"), get_autostart())
        a2.toggled.connect(lambda on: (set_autostart(on), self._auto.setChecked(on),
                                        self._auto_act.setDisabled(not on)))
        c1l.addWidget(a2)

        a3 = ToggleSwitch(tr("auto_activate_launch"), get_auto_activate())
        a3.setDisabled(not get_autostart())
        a2.toggled.connect(lambda on: a3.setDisabled(not on))
        a3.toggled.connect(set_auto_activate)
        a3.toggled.connect(self._auto_act.setChecked)
        c1l.addWidget(a3)

        c1l.addWidget(hdiv())
        c1l.addWidget(section_label(tr("protection"), bright=True))
        k2 = ToggleSwitch(tr("auto_restart"), True)
        k2.toggled.connect(self._ks.setChecked)
        c1l.addWidget(k2)
        vl.addWidget(c1)

        # Language
        cl = Card(radius=10); cll = QVBoxLayout(cl)
        cll.setContentsMargins(20, 18, 20, 18); cll.setSpacing(10)
        cll.addWidget(section_label(tr("language"), bright=True))
        lang_row = QHBoxLayout(); lang_row.setSpacing(8)
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["English", "Русский"])
        self._lang_combo.setCurrentIndex(0 if _current_lang == "en" else 1)
        self._lang_combo.currentIndexChanged.connect(self._change_lang)
        lang_row.addWidget(self._lang_combo); lang_row.addStretch()
        cll.addLayout(lang_row)
        vl.addWidget(cl)

        # Updates
        cu = Card(radius=10); cul = QVBoxLayout(cu)
        cul.setContentsMargins(20, 18, 20, 18); cul.setSpacing(10)
        cul.addWidget(section_label(tr("updates"), bright=True))
        self._upd_ver = QLabel(tr("current_version", ver=VERSION))
        self._upd_ver.setFont(ui_font(11)); self._upd_ver.setStyleSheet(f"color:{TEXT2};")
        cul.addWidget(self._upd_ver)
        upd_row = QHBoxLayout(); upd_row.setSpacing(8)
        self._upd_btn = Btn(tr("check_updates"), accent=True)
        self._upd_btn.clicked.connect(self._do_check_update)
        upd_row.addWidget(self._upd_btn)
        self._upd_status = QLabel("")
        self._upd_status.setFont(ui_font(11)); self._upd_status.setStyleSheet(f"color:{TEXT3};")
        upd_row.addWidget(self._upd_status); upd_row.addStretch()
        cul.addLayout(upd_row)
        vl.addWidget(cu)

        # Custom Lua args
        clua = Card(radius=10); clual = QVBoxLayout(clua)
        clual.setContentsMargins(20, 18, 20, 18); clual.setSpacing(10)
        clual.addWidget(section_label(tr("custom_lua"), bright=True))
        hint = QLabel(tr("custom_lua_hint"))
        hint.setFont(ui_font(10)); hint.setStyleSheet(f"color:{TEXT3};")
        hint.setWordWrap(True); clual.addWidget(hint)
        self._custom_lua_edit = QTextEdit()
        self._custom_lua_edit.setPlaceholderText(
            '--wf-tcp-out=443 --wf-udp-out=443,50000-65535\n'
            '--filter-tcp=443 --filter-l7=tls --payload=tls_client_hello\n'
            '--lua-desync=fake:blob=0x00:tcp_md5\n'
            '--lua-desync=multisplit:pos=1,midsld')
        self._custom_lua_edit.setFont(ui_font(10))
        self._custom_lua_edit.setMaximumHeight(120)
        self._custom_lua_edit.setStyleSheet(
            f"QTextEdit{{background:#101014;color:{TEXT2};border:1px solid {BORDER};"
            f"border-radius:6px;padding:8px;}}")
        clual.addWidget(self._custom_lua_edit)
        vl.addWidget(clua)

        c2 = Card(radius=10); c2l = QVBoxLayout(c2)
        c2l.setContentsMargins(20, 18, 20, 18); c2l.setSpacing(8)
        c2l.addWidget(section_label(tr("presets_info"), bright=True))
        all_presets = list(PRESETS.items()) + list(ZAPRET_PRESETS.items())
        for name, data in all_presets:
            info = data.get("desc", "custom")
            engine_tag = "[Zapret] " if data.get("engine") == "zapret" else "[GDPI] "
            desc = QLabel(f"{engine_tag}{name}\n    {info}")
            desc.setWordWrap(True)
            desc.setFont(ui_font(10)); desc.setStyleSheet(f"color:{TEXT2};")
            c2l.addWidget(desc)
        vl.addWidget(c2)

        vl.addStretch()
        info = QLabel(f"0bx0d? v{VERSION}  ·  GoodbyeDPI v0.2.3rc3 + Zapret v0.9.5  ·  MIT License")
        info.setFont(ui_font(10)); info.setStyleSheet(f"color:{TEXT3};")
        vl.addWidget(info)
        scroll.setWidget(page)
        return scroll

    # -- DNS --
    def _build_dns(self) -> QWidget:
        page = QWidget()
        vl = QVBoxLayout(page); vl.setContentsMargins(24, 20, 24, 16); vl.setSpacing(10)

        h = QHBoxLayout()
        h.addWidget(section_label(tr("dns_manager"))); h.addStretch()
        ref = Btn(tr("refresh")); ref.clicked.connect(self._dns_refresh)
        chk = Btn(tr("check_all"), accent=True)
        chk.clicked.connect(self._dns_check_all)
        h.addWidget(ref); h.addSpacing(6); h.addWidget(chk)
        vl.addLayout(h); vl.addWidget(hdiv())

        ac = Card(radius=8); acl = QHBoxLayout(ac)
        acl.setContentsMargins(16, 10, 16, 10); acl.setSpacing(12)
        al = QLabel(tr("adapter"))
        al.setFont(ui_font(11, bold=True)); al.setStyleSheet(f"color:{TEXT3};")
        al.setFixedWidth(65); acl.addWidget(al)
        self._adapter = QComboBox()
        self._adapter.addItems(get_adapters())
        self._adapter.currentTextChanged.connect(self._dns_show_current)
        acl.addWidget(self._adapter); acl.addSpacing(12)
        self._dns_cur_lbl = QLabel("—")
        self._dns_cur_lbl.setFont(mono_font(11))
        self._dns_cur_lbl.setStyleSheet(f"color:{TEXT2};")
        acl.addWidget(self._dns_cur_lbl, 1)
        vl.addWidget(ac)

        vl.addWidget(section_label(tr("servers")))
        self._dns_cards: dict[str, DnsCard] = {}
        grid_w = QWidget(); grid_l = QHBoxLayout(grid_w)
        grid_l.setContentsMargins(0, 0, 0, 0); grid_l.setSpacing(6)
        for name, (ip1, ip2) in DNS_SERVERS.items():
            card = DnsCard(name, ip1, ip2)
            card.selected.connect(self._dns_select)
            self._dns_cards[name] = card; grid_l.addWidget(card)
        vl.addWidget(grid_w)

        self._orig_lbl = QLabel(tr("original_not_saved"))
        self._orig_lbl.setFont(ui_font(10)); self._orig_lbl.setStyleSheet(f"color:{TEXT3};")
        vl.addWidget(self._orig_lbl)

        ab = QHBoxLayout(); ab.setSpacing(8)
        self._dns_act = Btn(tr("apply_selected"), accent=True)
        self._dns_act.clicked.connect(self._dns_activate)
        self._dns_rst = Btn(tr("restore_original"))
        self._dns_rst.clicked.connect(self._dns_restore)
        self._dns_dhcp = Btn(tr("reset_dhcp"))
        self._dns_dhcp.clicked.connect(self._dns_reset_dhcp)
        ab.addWidget(self._dns_act); ab.addWidget(self._dns_rst); ab.addWidget(self._dns_dhcp)
        ab.addStretch(); vl.addLayout(ab)

        self._dns_log = Terminal(compact=True); self._dns_log.setMaximumHeight(80)
        vl.addWidget(self._dns_log)
        QTimer.singleShot(400, self._dns_show_current)
        return page

    # -- ABOUT --
    def _build_info(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea{{border:none;background:transparent;}}"
            f"QScrollBar:vertical{{background:transparent;width:6px;border:none;}}"
            f"QScrollBar::handle:vertical{{background:{BORDER};border-radius:3px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}")

        page = QWidget()
        vl = QVBoxLayout(page); vl.setContentsMargins(28, 24, 28, 20); vl.setSpacing(16)

        # Header
        title = QLabel("0bx0d?")
        title.setFont(title_font(30))
        title.setStyleSheet(f"color:{ACCENT};"); vl.addWidget(title)
        subtitle = QLabel(tr("info_subtitle"))
        subtitle.setFont(ui_font(13)); subtitle.setStyleSheet(f"color:{TEXT2};")
        vl.addWidget(subtitle)

        # How it works
        c1 = Card(radius=10); c1l = QVBoxLayout(c1)
        c1l.setContentsMargins(20, 18, 20, 18); c1l.setSpacing(10)
        c1l.addWidget(section_label(tr("how_it_works")))
        desc = QLabel(tr("how_desc"))
        desc.setWordWrap(True)
        desc.setFont(ui_font(12)); desc.setStyleSheet(f"color:{TEXT2};")
        c1l.addWidget(desc)
        vl.addWidget(c1)

        # Features
        c2 = Card(radius=10); c2l = QVBoxLayout(c2)
        c2l.setContentsMargins(20, 18, 20, 18); c2l.setSpacing(6)
        c2l.addWidget(section_label(tr("features")))
        for feat in tr_list("features_list"):
            fl = QLabel(f"  •  {feat}")
            fl.setFont(ui_font(11)); fl.setStyleSheet(f"color:{TEXT2};")
            fl.setWordWrap(True); c2l.addWidget(fl)
        vl.addWidget(c2)

        # Tech info
        c3 = Card(radius=10); c3l = QVBoxLayout(c3)
        c3l.setContentsMargins(20, 18, 20, 18); c3l.setSpacing(6)
        c3l.addWidget(section_label(tr("tech_details")))
        c3l.addLayout(info_row(tr("engine"), "GoodbyeDPI v0.2.3rc3 by ValdikSS"))
        c3l.addLayout(info_row(tr("driver"), tr("driver_val")))
        c3l.addLayout(info_row(tr("framework"), "PySide6 (Qt for Python)"))
        c3l.addLayout(info_row(tr("platform"), tr("platform_val")))
        c3l.addLayout(info_row(tr("dns_check"), tr("dns_check_val")))
        c3l.addLayout(info_row(tr("license_lbl"), tr("license_val")))
        vl.addWidget(c3)

        # Links
        brow = QHBoxLayout(); brow.setSpacing(8)
        gh = Btn("GitHub", accent=True)
        gh.clicked.connect(lambda: webbrowser.open("https://github.com/Freezonplay070/0bx0d"))
        gdpi = Btn("GoodbyeDPI")
        gdpi.clicked.connect(lambda: webbrowser.open("https://github.com/ValdikSS/GoodbyeDPI"))
        brow.addWidget(gh); brow.addWidget(gdpi); brow.addStretch()
        vl.addLayout(brow)

        ft = QLabel(f"v{VERSION}  ·  by solevoyq  ·  MIT  ·  {tr('not_malware')}")
        ft.setFont(ui_font(10)); ft.setStyleSheet(f"color:{TEXT3};")
        vl.addWidget(ft)
        vl.addSpacing(8)

        scroll.setWidget(page)
        return scroll

    # -- Workers --
    def _setup_workers(self):
        self._tw = TunnelWorker(); self._tt = QThread()
        self._tw.moveToThread(self._tt)
        self._tw.log.connect(self._log)
        self._tw.started.connect(self._on_start)
        self._tw.stopped.connect(self._on_stop)
        self._tw.error.connect(self._on_err)
        self._tt.start()

        self._pw = PingWorker(); self._pt = QThread()
        self._pw.moveToThread(self._pt)
        self._pw.result.connect(self._on_ping)
        self._pt.started.connect(self._pw.run); self._pt.start()

        self._dw = DnsWorker(); self._dt = QThread()
        self._dw.moveToThread(self._dt)
        self._dw.log.connect(self._dns_log.queue_line)
        self._dw.done.connect(self._dns_done)
        self._dw.dns_result.connect(self._dns_card_result)
        self._dt.start()

        self._uw = UpdateWorker(); self._ut = QThread()
        self._uw.moveToThread(self._ut)
        self._uw.check_done.connect(self._on_update_check)
        self._uw.dl_progress.connect(self._on_update_progress)
        self._uw.dl_done.connect(self._on_update_downloaded)
        self._uw.apply_done.connect(self._on_update_applied)
        self._ut.start()
        self._upd_zip_url = ""

    def _log(self, t):
        self._term.queue_line(t); self._full.queue_line(t)

    # -- Startup --
    def _change_lang(self, idx):
        global _current_lang
        lang = "en" if idx == 0 else "ru"
        if lang == _current_lang: return
        _current_lang = lang; set_lang(lang)
        # Rebuild UI pages
        self._stack.setCurrentIndex(0)
        for i in reversed(range(self._stack.count())):
            w = self._stack.widget(i); self._stack.removeWidget(w); w.deleteLater()
        for page in [self._build_dash(), self._build_logs(),
                     self._build_sett(), self._build_dns(), self._build_info()]:
            self._stack.addWidget(page)
        # Reconnect workers to new terminal widgets
        try:
            self._tw.log.disconnect()
            self._dw.log.disconnect()
        except: pass
        self._tw.log.connect(self._log)
        self._dw.log.connect(self._dns_log.queue_line)
        self._dw.done.connect(self._dns_done)
        self._dw.dns_result.connect(self._dns_card_result)
        # Update sidebar labels
        labels = ["nav_dashboard", "nav_logs", "nav_settings", "nav_dns", "nav_info"]
        for btn, key in zip(self._sbs, labels):
            btn._tip = tr(key); btn.setToolTip(tr(key)); btn.update()
        self._startup()

    # -- Updater --
    def _do_check_update(self):
        self._upd_btn.setEnabled(False)
        self._upd_status.setText(tr("checking_updates"))
        self._upd_status.setStyleSheet(f"color:{TEXT2};")
        self._uw.check()

    def _on_update_check(self, has_update, version, zip_url):
        if has_update:
            self._upd_zip_url = zip_url
            self._upd_status.setText(tr("update_available", ver=version))
            self._upd_status.setStyleSheet(f"color:{GREEN};")
            self._upd_btn.setText(tr("download_update"))
            self._upd_btn.setEnabled(True)
            try: self._upd_btn.clicked.disconnect()
            except: pass
            self._upd_btn.clicked.connect(self._do_download_update)
        else:
            self._upd_status.setText(tr("no_updates"))
            self._upd_status.setStyleSheet(f"color:{TEXT3};")
            self._upd_btn.setEnabled(True)

    def _do_download_update(self):
        if not self._upd_zip_url: return
        self._upd_btn.setEnabled(False)
        self._upd_status.setText(tr("downloading", pct=0))
        self._upd_status.setStyleSheet(f"color:{ACCENT};")
        self._uw.download(self._upd_zip_url)

    def _on_update_progress(self, pct):
        self._upd_status.setText(tr("downloading", pct=pct))

    def _on_update_downloaded(self, ok, path):
        if ok:
            self._upd_status.setText(tr("installing"))
            self._upd_status.setStyleSheet(f"color:{GREEN};")
            self._uw.apply(path)
        else:
            self._upd_status.setText(tr("update_failed"))
            self._upd_status.setStyleSheet(f"color:{ACCENT2};")
            self._upd_btn.setEnabled(True)

    def _on_update_applied(self, ok):
        if ok:
            self._upd_status.setText(tr("installing"))
            # App will be killed by the updater batch script
            QTimer.singleShot(1500, lambda: sys.exit(0))
        else:
            self._upd_status.setText(tr("update_failed"))
            self._upd_status.setStyleSheet(f"color:{ACCENT2};")
            self._upd_btn.setEnabled(True)

    def _on_autostart_toggle(self, on: bool):
        set_autostart(on)
        self._auto_act.setDisabled(not on)

    def _startup(self):
        admin = is_admin()
        self._log(tr("init_boot", name=APP_NAME, ver=VERSION))
        self._log(tr("admin_ok") if admin else tr("admin_miss"))
        miss = [f for f in ("goodbyedpi.exe", "WinDivert.dll", "WinDivert64.sys")
                if not (BIN_DIR / f).exists()]
        for f in miss: self._log(tr("missing_file", f=f))
        if not miss: self._log(tr("driver_ok"))
        try:
            socket.create_connection(("discord.com", 443), timeout=3).close()
            self._log(tr("net_reachable"))
        except:
            self._log(tr("net_blocked"))
        # Auto-activate bypass if both autostart and auto-bypass are on
        if get_autostart() and get_auto_activate() and not miss and admin:
            self._log(tr("auto_bypass_start"))
            QTimer.singleShot(500, self._toggle)
        else:
            self._log(tr("awaiting"))

    def _on_engine_change(self, idx):
        self._preset.clear()
        if idx == 0:
            self._preset.addItems(list(PRESETS.keys()))
        elif idx == 1:
            self._preset.addItems([k for k, v in ZAPRET_PRESETS.items()
                                   if v.get("engine") == "zapret"])
        else:
            self._preset.addItems([k for k, v in ZAPRET_PRESETS.items()
                                   if v.get("engine") == "flowseal"])

    # -- Tunnel --
    def _toggle(self):
        if self._on: self._tw.stop()
        else:
            custom = getattr(self, '_custom_lua_edit', None)
            custom_args = custom.toPlainText() if custom else ""
            self._tw.launch(self._preset.currentText(),
                            self._ks.isChecked(), custom_args)

    def _on_start(self):
        self._on = True; self._pwr.set_active(True)
        self._tbar.set_connected(True); self._log(tr("activated_msg"))

    def _on_stop(self):
        self._on = False; self._pwr.set_active(False)
        self._tbar.set_connected(False); self._log(tr("deactivated_msg"))

    def _on_err(self, msg): self._on_stop(); self._log(f"✗ error: {msg}")
    def _on_ping(self, ms): self._ping = ms

    # -- DNS --
    def _dns_show_current(self):
        adapter = self._adapter.currentText()
        p, s = get_dns_ips(adapter)
        self._dns_cur_lbl.setText(f"{p}  /  {s}" if p else "AUTO (DHCP)")
        op, os_ = get_original_dns(adapter)
        if op: self._orig_lbl.setText(tr("orig_saved", p=op, s=os_ or '—'))
        else: self._orig_lbl.setText(tr("orig_first_change"))

    def _dns_refresh(self):
        ads = get_adapters(); cur = self._adapter.currentText()
        self._adapter.clear(); self._adapter.addItems(ads)
        if cur in ads: self._adapter.setCurrentText(cur)
        self._dns_show_current()
        self._dns_log.queue_line(tr("adapters_refreshed"))

    def _dns_select(self, name):
        self._dns_sel = name
        for n, c in self._dns_cards.items(): c.set_selected(n == name)

    def _dns_check_all(self):
        for c in self._dns_cards.values(): c.set_checking()
        self._dw.check_latency()

    def _dns_card_result(self, name, ms):
        if name in self._dns_cards: self._dns_cards[name].set_latency(ms)

    def _dns_activate(self):
        if not self._dns_sel:
            self._dns_log.queue_line("✗ select a server first"); return
        adapter = self._adapter.currentText()
        save_original_dns(adapter)
        p, s = DNS_SERVERS[self._dns_sel]
        self._dw.apply(adapter, p, s)
        # Mark applied card
        self._dns_applied = self._dns_sel
        for n, c in self._dns_cards.items():
            c.set_applied(n == self._dns_sel)

    def _dns_restore(self):
        self._dw.reset(self._adapter.currentText())
        # Clear applied state
        self._dns_applied = None
        for c in self._dns_cards.values(): c.set_applied(False)

    def _dns_reset_dhcp(self):
        adapter = self._adapter.currentText()
        _original_dns.pop(adapter, None)
        self._dw.reset(adapter)
        self._dns_applied = None
        for c in self._dns_cards.values(): c.set_applied(False)

    def _dns_done(self, ok, msg):
        self._dns_log.queue_line(msg)
        QTimer.singleShot(500, self._dns_show_current)

    # -- Close --
    def closeEvent(self, e):
        if self._on: self._tw.stop()
        self._pw.stop()
        for t in (self._pt, self._tt, self._dt, self._ut): t.quit(); t.wait(2000)
        e.accept()

# =====================================================================
#  ENTRY
# =====================================================================
def _setup_app():
    """Create and configure QApplication."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion"); app.setApplicationName("0bx0d?")
    app.setStyleSheet(QSS)

    from PySide6.QtGui import QPalette
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Base,            QColor("#101014"))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(SURFACE))
    pal.setColor(QPalette.ColorRole.Text,            QColor(TEXT))
    pal.setColor(QPalette.ColorRole.BrightText,      QColor(ACCENT2))
    pal.setColor(QPalette.ColorRole.Button,          QColor(CARD))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Link,            QColor(ACCENT))
    app.setPalette(pal)
    return app


def main():
    if sys.platform == "win32" and not is_admin():
        relaunch_admin()

    app = _setup_app()

    # -- License check --
    valid, msg = check_license()
    if not valid:
        dlg = LicenseDialog()
        dlg.show()
        app.exec()
        if not dlg._success:
            sys.exit(0)

    # -- Main app --
    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
