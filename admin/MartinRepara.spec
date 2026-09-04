# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller para empaquetar la app de escritorio.

Genera un único MartinRepara.exe en dist/. Se corre con build.bat, que
antes se asegura de correr collectstatic (staticfiles/ se bundlea
entero: sin eso no hay CSS/logo en el .exe).

Uso manual (equivalente a build.bat):
    venv\\Scripts\\python.exe manage.py collectstatic --noinput
    venv\\Scripts\\python.exe -m PyInstaller MartinRepara.spec --noconfirm
"""
from pathlib import Path

PROJECT_DIR = Path(SPECPATH)

a = Analysis(
    ['app.py'],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=[
        (str(PROJECT_DIR / 'config'), 'config'),
        (str(PROJECT_DIR / 'taller'), 'taller'),
        (str(PROJECT_DIR / 'staticfiles'), 'staticfiles'),
        (str(PROJECT_DIR / 'martinrepara.ico'), '.'),
    ],
    hiddenimports=[
        'django.contrib.admin',
        'django.contrib.admin.apps',
        'django.contrib.auth',
        'django.contrib.auth.apps',
        'django.contrib.auth.backends',
        'django.contrib.contenttypes',
        'django.contrib.contenttypes.apps',
        'django.contrib.sessions',
        'django.contrib.sessions.apps',
        'django.contrib.sessions.backends.db',
        'django.contrib.messages',
        'django.contrib.messages.apps',
        'django.contrib.messages.storage.fallback',
        'django.contrib.staticfiles',
        'django.contrib.staticfiles.apps',
        'django.template.backends.django',
        'django.db.backends.sqlite3',
        'whitenoise.middleware',
        'whitenoise.storage',
        'openpyxl',
        'openpyxl.cell._writer',
        'et_xmlfile',
        'taller',
        'taller.apps',
        'taller.admin',
        'taller.models',
        'taller.views',
        'taller.forms',
        'taller.analytics',
        'taller.urls',
        'taller.templatetags',
        'taller.templatetags.taller_extras',
        'taller.migrations',
        'taller.management',
        'taller.management.commands',
        'taller.management.commands.seed_demo',
        'config',
        'config.settings',
        'config.urls',
        'config.wsgi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MartinRepara',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_DIR / 'martinrepara.ico'),
)
