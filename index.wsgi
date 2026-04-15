#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WSGI файл для запуска Flask приложения на Timeweb
"""

import os
import sys
import traceback

# Получаем абсолютный путь к директории этого файла
basedir = os.path.abspath(os.path.dirname(__file__))

# ВАЖНО: Добавляем пути к site-packages ПЕРВЫМИ, ДО добавления текущей директории
# Это нужно для того, чтобы Flask и другие пакеты были доступны

# 0. ПРИОРИТЕТ: Добавляем lib в директории проекта (если пакеты установлены туда)
lib_dir = os.path.join(basedir, 'lib')
if os.path.exists(lib_dir):
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)

# 1. Добавляем путь к пользовательским site-packages (где установлены пакеты с --user)
# Python автоматически добавляет этот путь, но убедимся что он есть
user_site_packages_310 = os.path.expanduser('~/.local/lib/python3.10/site-packages')
if os.path.exists(user_site_packages_310):
    # Добавляем в начало, даже если уже есть (на случай если он в конце)
    if user_site_packages_310 in sys.path:
        sys.path.remove(user_site_packages_310)
    sys.path.insert(0, user_site_packages_310)

# 2. Проверяем другие возможные версии Python
for version in ['3.11', '3.9', '3.8', '3.7']:
    user_site_packages = os.path.expanduser(f'~/.local/lib/python{version}/site-packages')
    if os.path.exists(user_site_packages):
        if user_site_packages in sys.path:
            sys.path.remove(user_site_packages)
        sys.path.insert(0, user_site_packages)

# 3. Добавляем текущую директорию
sys.path.insert(0, basedir)

# 4. Проверяем наличие Flask перед импортом bot.py
# Пытаемся импортировать Flask
flask_imported = False
flask_error_msg = None

try:
    import flask
    flask_imported = True
except ImportError as e:
    flask_error_msg = str(e)
    # Flask не найден - пробуем найти через pip show
    try:
        import subprocess
        result = subprocess.run(['python3', '-m', 'pip', 'show', 'flask'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('Location:'):
                    location = line.split(':', 1)[1].strip()
                    if location not in sys.path:
                        sys.path.insert(0, location)
                    # Пробуем импортировать снова
                    try:
                        import flask
                        flask_imported = True
                        break
                    except ImportError:
                        pass
    except:
        pass

# Если Flask все еще не найден, логируем проблему
if not flask_imported:
    error_log = os.path.join(basedir, 'wsgi_error.log')
    try:
        with open(error_log, 'a', encoding='utf-8') as f:
            from datetime import datetime
            f.write(f"\n=== Flask Import Error at {datetime.now()} ===\n")
            f.write(f"Error: {flask_error_msg}\n")
            f.write(f"Python: {sys.version}\n")
            f.write(f"Paths: {sys.path}\n")
            # Проверяем существование Flask
            flask_path_check = os.path.join(user_site_packages_310, 'flask')
            flask_exists = os.path.exists(flask_path_check)
            f.write(f"Flask path: {flask_path_check}\n")
            f.write(f"Flask path exists: {flask_exists}\n")
            
            # Проверяем права доступа
            if flask_exists:
                try:
                    flask_init = os.path.join(flask_path_check, '__init__.py')
                    f.write(f"Flask __init__.py exists: {os.path.exists(flask_init)}\n")
                    if os.path.exists(flask_init):
                        # Пробуем прочитать файл
                        try:
                            with open(flask_init, 'r') as test_file:
                                test_file.read(1)
                            f.write("Flask __init__.py is readable: True\n")
                        except PermissionError:
                            f.write("Flask __init__.py is readable: False (Permission denied)\n")
                except Exception as e:
                    f.write(f"Error checking Flask files: {e}\n")
            
            if os.path.exists(user_site_packages_310):
                try:
                    contents = os.listdir(user_site_packages_310)
                    flask_dirs = [d for d in contents if 'flask' in d.lower()]
                    f.write(f"Site-packages exists: True\n")
                    f.write(f"Packages with 'flask' in name: {flask_dirs}\n")
                except PermissionError as pe:
                    f.write(f"Permission denied reading site-packages: {pe}\n")
                    f.write("SOLUTION: Run 'chmod -R 755 ~/.local/lib/python3.10/site-packages'\n")
                except Exception as e:
                    f.write(f"Error listing site-packages: {e}\n")
            else:
                f.write(f"Site-packages directory does not exist!\n")
            f.write("\n")
    except:
        pass
    
    # Если Flask существует, но не может быть импортирован - это проблема прав доступа
    if os.path.exists(os.path.join(user_site_packages_310, 'flask')):
        raise ImportError(
            f"Flask found but cannot be imported. This is likely a permissions issue.\n"
            f"Run: chmod -R 755 ~/.local/lib/python3.10/site-packages\n"
            f"Or use: bash fix_permissions.sh"
        )
    else:
        raise ImportError(f"Flask not found in {user_site_packages_310}. Please install Flask with: pip install --user flask")

# Также проверяем стандартные пути к virtualenv
python_versions = ['3.10', '3.11', '3.9', '3.8', '3.7']
venv_base = '/home/c/cw998871/venv/lib/python'

for version in python_versions:
    venv_path = os.path.join(venv_base, version, 'site-packages')
    if os.path.exists(venv_path) and venv_path not in sys.path:
        sys.path.insert(0, venv_path)
        break

# Проверяем альтернативные расположения virtualenv
alt_venv_locations = [
    '/home/c/cw998871/.venv',
    os.path.expanduser('~/venv'),
    os.path.expanduser('~/.venv'),
    '/home/c/cw998871/public_html/venv',
    '/home/c/cw998871/public_html/KISSPARTYPAYMAIN/venv',
]

for venv_dir in alt_venv_locations:
    if os.path.exists(venv_dir):
        for version in python_versions:
            site_packages = os.path.join(venv_dir, 'lib', f'python{version}', 'site-packages')
            if os.path.exists(site_packages) and site_packages not in sys.path:
                sys.path.insert(0, site_packages)
                break

try:
    # Импортируем Flask приложение из bot.py
    from bot import app
    
    # WSGI требует переменную application (это должно быть Flask приложение)
    # В bot.py теперь используется telegram_app для Telegram Application
    application = app
    
except Exception as e:
    # Логируем ошибку в файл для диагностики
    error_trace = traceback.format_exc()
    try:
        error_log = os.path.join(basedir, 'wsgi_error.log')
        with open(error_log, 'a', encoding='utf-8') as f:
            from datetime import datetime
            f.write(f"\n=== Error at {datetime.now()} ===\n")
            f.write(f"Error: {str(e)}\n")
            f.write(f"Traceback:\n{error_trace}\n")
            f.write(f"Python: {sys.version}\n")
            f.write(f"Paths: {sys.path}\n\n")
    except:
        pass
    
    try:
        from flask import Flask
        app = Flask(__name__)
    except ImportError:
        # Если даже Flask не импортируется, создаем минимальный WSGI app
        def simple_app(environ, start_response):
            status = '500 Internal Server Error'
            headers = [('Content-Type', 'text/html; charset=utf-8')]
            body = f"""
            <html>
            <head><title>WSGI Error</title></head>
            <body>
                <h1>Error importing bot.py</h1>
                <pre>{str(e)}</pre>
                <h2>Traceback:</h2>
                <pre>{error_trace}</pre>
                <h2>Python version:</h2>
                <pre>{sys.version}</pre>
                <h2>Paths:</h2>
                <pre>{chr(10).join(sys.path)}</pre>
            </body>
            </html>
            """
            start_response(status, headers)
            return [body.encode('utf-8')]
        
        application = simple_app
    else:
        @app.route('/')
        @app.route('/<path:path>')
        def error_handler(path=''):
            return f"""
            <html>
            <head><title>WSGI Error</title></head>
            <body>
                <h1>Error importing bot.py</h1>
                <pre>{str(e)}</pre>
                <h2>Traceback:</h2>
                <pre>{error_trace}</pre>
                <h2>Python version:</h2>
                <pre>{sys.version}</pre>
                <h2>Paths:</h2>
                <pre>{chr(10).join(sys.path)}</pre>
            </body>
            </html>
            """, 500
        
        application = app

