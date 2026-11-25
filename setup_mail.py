"""Запускать только в приватной консоли PythonAnywhere, не в веб-странице."""
import getpass,json,os
from pathlib import Path
print('Настройка почтовых уведомлений. Нужен отдельный пароль приложения Google.')
user=input('Gmail отправителя: ').strip()
password=getpass.getpass('Пароль приложения Google (при вводе не отображается): ').replace(' ','')
if not user or not password: raise SystemExit('Нужны адрес и пароль приложения.')
config={'SMTP_HOST':'smtp.gmail.com','SMTP_PORT':'587','SMTP_USER':user,'SMTP_PASSWORD':password,'MAIL_TO':'gudkovdanil181@gmail.com'}
p=Path.home()/'.tochka_config.json'
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(config,f)
os.chmod(p,0o600)
print('Сохранено. Вернитесь во вкладку Web и нажмите Reload. Затем отправьте тестовую заявку.')
