# 0bx0d?

> DPI bypass for Discord. Voice. No VPN. No lag.

![platform](https://img.shields.io/badge/platform-Windows%2010%2F11-blue?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![release](https://img.shields.io/github/v/release/Freezonplay070/0bx0d?style=flat-square&color=red)

---

## What is it?

**0bx0d?** is a lightweight GUI tool for bypassing Discord blocks (including Voice/RTC) using [GoodbyeDPI](https://github.com/ValdikSS/GoodbyeDPI) + WinDivert. No VPN. No ping overhead.

## Features

- **4 presets** — Discord Only, Discord + Game (UDP), All Traffic, Stealth Stream
- **Kill switch** — auto-restarts GoodbyeDPI if it crashes unexpectedly
- **DNS Manager** — switch system DNS with built-in latency checker
- **Autostart** — launch on Windows login with optional auto-bypass
- **License key system** — Firebase-based activation
- **EN / RU interface** — switch language in settings
- **Dark UI** — frameless custom PySide6 interface

## Download

👉 **[Download latest release → 0bx0d.zip](../../releases/latest/download/0bx0d.zip)**

Extract → Right-click `0bx0d.exe` → **Run as Administrator**.

> ⚠️ Windows SmartScreen may warn you — click "More info" → "Run anyway". The app is open source, not malware.

## Usage

1. Download and extract `0bx0d.zip`
2. Run `0bx0d.exe` as Administrator (required for WinDivert driver)
3. Enter your license key to activate
4. Choose a preset (Discord Only / All Traffic / etc.)
5. Press the power button — done, Discord is alive

## How it works

GoodbyeDPI intercepts TCP/UDP packets at the kernel level via the WinDivert driver and modifies their headers — fragmentation, wrong checksums, fake ACK packets — so your ISP's Deep Packet Inspection (DPI) can't correctly reassemble the stream and lets the connection through.

When using Discord presets, only Discord domains are targeted via a blacklist file (`--blacklist` flag), leaving all other traffic untouched.

## Build from source

```bash
cd app
pip install PySide6 psutil pyinstaller
python -m PyInstaller --noconfirm --onedir --name 0bx0d --add-data "bin;bin" --version-file version_info.py --uac-admin --hidden-import psutil --noconsole main.py
```

Output: `app/dist/0bx0d/`

## Project structure

```
0bx0d/
├── index.html          ← Landing page (GitHub Pages)
├── admin/index.html    ← Admin panel (key management)
├── README.md
└── app/
    ├── main.py         ← PySide6 GUI (~1800 lines)
    ├── version_info.py ← EXE metadata for PyInstaller
    └── bin/
        ├── goodbyedpi.exe
        ├── WinDivert.dll
        └── WinDivert64.sys
```

## Tech stack

| Component | Technology |
|-----------|-----------|
| Engine | GoodbyeDPI v0.2.2 by ValdikSS |
| Driver | WinDivert (kernel-level packet interception) |
| GUI | PySide6 (Qt for Python) |
| Platform | Windows 10 / 11 (x64, admin required) |
| License system | Firebase Realtime Database + SHA256 |
| Build | PyInstaller |

## License

MIT — free and open source.

---

# 0bx0d? (RU)

> DPI обход для Discord. Голос. Без VPN. Без лагов.

## Что это?

**0bx0d?** — лёгкий GUI-инструмент для обхода блокировок Discord (включая голос/RTC) через [GoodbyeDPI](https://github.com/ValdikSS/GoodbyeDPI) + WinDivert. Без VPN. Без потери пинга.

## Возможности

- **4 пресета** — Discord Only, Discord + Game (UDP), All Traffic, Stealth Stream
- **Kill switch** — автоперезапуск GoodbyeDPI при падении
- **DNS Менеджер** — смена системного DNS с проверкой задержки
- **Автозапуск** — запуск при входе в Windows с авто-обходом
- **Система лицензий** — активация ключом через Firebase
- **EN / RU интерфейс** — переключение языка в настройках
- **Тёмный UI** — кастомный интерфейс без рамки на PySide6

## Скачать

👉 **[Скачать последний релиз → 0bx0d.zip](../../releases/latest/download/0bx0d.zip)**

Распакуй → ПКМ на `0bx0d.exe` → **Запустить от имени администратора**.

> ⚠️ Windows SmartScreen может выдать предупреждение — нажми "Подробнее" → "Выполнить в любом случае". Программа с открытым кодом, не вирус.

## Использование

1. Скачай и распакуй `0bx0d.zip`
2. Запусти `0bx0d.exe` от имени администратора (нужно для драйвера WinDivert)
3. Введи лицензионный ключ для активации
4. Выбери пресет (Discord Only / All Traffic / и т.д.)
5. Нажми кнопку питания — готово, Discord работает

## Как это работает

GoodbyeDPI перехватывает TCP/UDP пакеты на уровне ядра через драйвер WinDivert и модифицирует их заголовки — фрагментация, неверные контрольные суммы, фейковые ACK пакеты — чтобы DPI система провайдера не могла правильно собрать поток и пропускала соединение.

При использовании пресетов Discord обрабатываются только домены Discord через файл блеклиста (флаг `--blacklist`), остальной трафик не затрагивается.

## Сборка из исходников

```bash
cd app
pip install PySide6 psutil pyinstaller
python -m PyInstaller --noconfirm --onedir --name 0bx0d --add-data "bin;bin" --version-file version_info.py --uac-admin --hidden-import psutil --noconsole main.py
```

Результат: `app/dist/0bx0d/`

## Лицензия

MIT — бесплатно и с открытым кодом.

---

by [solevoyq](https://github.com/Freezonplay070)
