#!/usr/bin/env python3
"""Локальный запуск сайта с Gmail SMTP без сохранения пароля в файле."""
import getpass, os, subprocess, sys
print('Настройка Gmail для уведомлений. Не отправляйте пароль приложения в чат.')
user=input('Gmail отправителя: ').strip()
recipient=input('Почта получателя [gudkovdanil181@gmail.com]: ').strip() or 'gudkovdanil181@gmail.com'
password=getpass.getpass('Пароль приложения Google (ввод скрыт): ').replace(' ', '')
if not user or not password: raise SystemExit('Нужны адрес и пароль приложения.')
env=os.environ.copy();env.update(SMTP_HOST='smtp.gmail.com',SMTP_PORT='587',SMTP_USER=user,SMTP_PASSWORD=password,MAIL_TO=recipient)
print('Запускается сайт: http://127.0.0.1:8000. Остановка: Ctrl+C.')
try: subprocess.run([sys.executable, 'server.py'], env=env, cwd=os.path.dirname(os.path.abspath(__file__)))
except KeyboardInterrupt: pass
