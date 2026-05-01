# 0bx0d?

> DPI bypass для Discord. Голос. Без VPN. Без нервів.

![black](https://img.shields.io/badge/color-black-000000?style=flat-square)
![red](https://img.shields.io/badge/color-dark--red-8b0000?style=flat-square)
![platform](https://img.shields.io/badge/platform-Windows%2010%2F11-blue?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-green?style=flat-square)

## Що це?

**0bx0d?** — легкий GUI-інструмент для обходу блокувань Discord (включаючи Voice/RTC)
через [GoodbyeDPI](https://github.com/ValdikSS/GoodbyeDPI) + WinDivert. Без VPN. Без пінгу.

## Скачати

👉 **[Releases → 0bx0d.zip](../../releases/latest)**

Розпакуй → ПКМ на `0bx0d.exe` → **Запустити від імені адміністратора**.

## Використання

1. `EAT` — скачай zip з exe
2. Запусти від імені адміністратора
3. Вибери режим (`DISCORD` / `ALL TRAFFIC`) і пресет
4. Натисни **ACTIVATE**
5. Discord живий

## Зібрати самому

```bash
cd app
pip install PySide6 psutil pyinstaller
build.bat
```

Готовий `.exe` буде в `app/dist/0bx0d.exe`.

## Структура

```
0bx0d/
├── index.html          ← Landing page (GitHub Pages)
├── README.md
└── app/
    ├── main.py         ← PySide6 GUI
    ├── manifest.xml    ← Admin rights UAC manifest
    ├── version_info.txt← PyInstaller metadata (SmartScreen bypass)
    ├── build.bat       ← One-click build script
    └── bin/
        ├── goodbyedpi.exe
        ├── WinDivert.dll
        └── WinDivert64.sys
```

## Як це працює

GoodbyeDPI перехоплює TCP/UDP пакети через драйвер WinDivert і модифікує їх:
фрагментація, зміна заголовків, фейкові контрольні суми. Провайдерський DPI
не може правильно зібрати пакет і пропускає з'єднання.

Discord Voice (RTC, UDP 50000-65535) обробляється через `--desync-any-protocol`.

---

by [solevoyq](https://github.com/solevoyq)
