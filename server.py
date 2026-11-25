#!/usr/bin/env python3
"""Демо-сайт автосервиса: HTTP + SQLite + SMTP, только стандартная библиотека."""
import json, os, re, smtplib, sqlite3, ssl, sys, time
from collections import defaultdict, deque
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / 'public'
DB = Path(os.getenv('DB_PATH', str(ROOT / 'data' / 'requests.sqlite3')))
DESTINATION = os.getenv('MAIL_TO', 'gudkovdanil181@gmail.com')
MAX_BODY = 16_384
rate = defaultdict(deque)

def db_connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('''CREATE TABLE IF NOT EXISTS requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
      name TEXT NOT NULL, phone TEXT, email TEXT, car TEXT, service TEXT,
      message TEXT, consent INTEGER NOT NULL, email_status TEXT NOT NULL DEFAULT 'pending',
      email_error TEXT)''')
    db.commit()
    return db

def one_line(value, maxlen, required=True):
    if not isinstance(value,str): raise ValueError('Проверьте заполнение полей.')
    s = value.strip()
    if ('\r' in s or '\n' in s or len(s)>maxlen or (required and not s)):
        raise ValueError('Проверьте заполнение полей.')
    return s

def validate(kind, data):
    if not isinstance(data,dict) or data.get('consent') is not True: raise ValueError('Необходимо согласие на обработку данных.')
    name=one_line(data.get('name',''),80)
    message=data.get('message','')
    if not isinstance(message,str) or len(message)>1500: raise ValueError('Сообщение слишком длинное.')
    message=message.strip()
    row={'kind':kind, 'name':name, 'phone':'', 'email':'', 'car':'', 'service':'', 'message':message, 'consent':1}
    if kind=='booking':
        phone=one_line(data.get('phone',''),30)
        if not re.fullmatch(r'[+\d()\-\s]{7,30}',phone) or len(re.sub(r'\D','',phone))<7: raise ValueError('Укажите корректный номер телефона.')
        service=one_line(data.get('service',''),80)
        if service not in ('Диагностика','Техническое обслуживание','Ремонт','Другое'): raise ValueError('Выберите услугу из списка.')
        row.update(phone=phone,car=one_line(data.get('car',''),120),service=service)
    else:
        email=one_line(data.get('email',''),254)
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise ValueError('Укажите корректный адрес почты.')
        if len(message)<5: raise ValueError('Напишите сообщение длиной не менее 5 символов.')
        row['email']=email
    return row

def send_email(row):
    host=os.getenv('SMTP_HOST',''); user=os.getenv('SMTP_USER',''); password=os.getenv('SMTP_PASSWORD','')
    if not all((host,user,password)): return 'not_configured','SMTP не настроен'
    try:
        port=int(os.getenv('SMTP_PORT','587'))
        msg=EmailMessage(); msg['Subject']=('Новая заявка на ремонт' if row['kind']=='booking' else 'Новое обращение в поддержку')+f" №{row['id']}"
        msg['From']=os.getenv('SMTP_FROM',user); msg['To']=DESTINATION
        if row['email']: msg['Reply-To']=row['email']
        msg.set_content('\n'.join([f"Обращение №{row['id']} от {row['created_at']} (UTC)",f"Имя: {row['name']}",f"Телефон: {row['phone'] or '—'}",f"Почта: {row['email'] or '—'}",f"Автомобиль: {row['car'] or '—'}",f"Услуга: {row['service'] or '—'}",'',f"Сообщение: {row['message'] or '—'}"]))
        if port==465:
            with smtplib.SMTP_SSL(host,port,timeout=12,context=ssl.create_default_context()) as smtp:
                smtp.login(user,password); smtp.send_message(msg)
        else:
            with smtplib.SMTP(host,port,timeout=12) as smtp:
                smtp.ehlo(); smtp.starttls(context=ssl.create_default_context()); smtp.ehlo(); smtp.login(user,password); smtp.send_message(msg)
        return 'sent',None
    except Exception as exc:
        # Store the exception type only: never write credentials or customer content to logs.
        return 'failed',type(exc).__name__

def store_and_notify(row):
    with db_connect() as db:
        cur=db.execute('INSERT INTO requests(kind,name,phone,email,car,service,message,consent) VALUES (:kind,:name,:phone,:email,:car,:service,:message,:consent)',row)
        row_id=cur.lastrowid; db.commit()
        stored=dict(db.execute('SELECT * FROM requests WHERE id=?',(row_id,)).fetchone())
    status,error=send_email(stored)
    with db_connect() as db: db.execute('UPDATE requests SET email_status=?, email_error=? WHERE id=?',(status,error,row_id))
    return row_id,status

def retry_unsent():
    with db_connect() as db: rows=[dict(r) for r in db.execute("SELECT * FROM requests WHERE email_status IN ('failed','not_configured','pending') ORDER BY id")]
    if not rows: print('Нет неотправленных обращений.'); return
    for row in rows:
        status,error=send_email(row)
        with db_connect() as db: db.execute('UPDATE requests SET email_status=?, email_error=? WHERE id=?',(status,error,row['id']))
        print(f"#{row['id']}: {status}"+(f" ({error})" if error else ''))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Avoid logging user data or query strings.
        print(f'{self.client_address[0]} {self.command} {urlsplit(self.path).path}',file=sys.stderr)
    def headers_common(self):
        self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer'); self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self' blob: data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
    def reply_json(self,code,payload):
        b=json.dumps(payload,ensure_ascii=False).encode(); self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.headers_common();self.end_headers();self.wfile.write(b)
    def do_GET(self):
        route=urlsplit(self.path).path
        mapping={'/x5/O_G05_Exterior_Paint.gltf':('x5/O_G05_Exterior_Paint.gltf','model/gltf+json'),'/x5/O_G05_Exterior_non-Paint.gltf':('x5/O_G05_Exterior_non-Paint.gltf','model/gltf+json'),'/x5/O_G05_Headlights.gltf':('x5/O_G05_Headlights.gltf','model/gltf+json'),'/x5/O_G05_Taillights.gltf':('x5/O_G05_Taillights.gltf','model/gltf+json'),'/x5/O_G05_Hood.gltf':('x5/O_G05_Hood.gltf','model/gltf+json'),'/x5/O_G05_Doors_F.gltf':('x5/O_G05_Doors_F.gltf','model/gltf+json'),'/x5/O_G05_Doors_B.gltf':('x5/O_G05_Doors_B.gltf','model/gltf+json'),'/x5/O_G05_Tailgate.gltf':('x5/O_G05_Tailgate.gltf','model/gltf+json'),'/x5/O_G05_Interior_Color.gltf':('x5/O_G05_Interior_Color.gltf','model/gltf+json'),'/x5/O_G05_Interior_non-Color.gltf':('x5/O_G05_Interior_non-Color.gltf','model/gltf+json'),'/x5/O_G05_Seats.gltf':('x5/O_G05_Seats.gltf','model/gltf+json'),'/x5/O_G05_SteeringWheel.gltf':('x5/O_G05_SteeringWheel.gltf','model/gltf+json'),'/x5/O_G05_Emblem.gltf':('x5/O_G05_Emblem.gltf','model/gltf+json'),'/x5/O_G05_LicensePlates.gltf':('x5/O_G05_LicensePlates.gltf','model/gltf+json'),'/x5/O_G05_Wheels.gltf':('x5/O_G05_Wheels.gltf','model/gltf+json'),'/bmw.glb':('bmw.glb','model/gltf-binary'),'/porsche.glb':('porsche.glb','model/gltf-binary'),'/audi.glb':('audi.glb','model/gltf-binary'),'/hatch.glb':('hatch.glb','model/gltf-binary'),'/suv.glb':('suv.glb','model/gltf-binary'),'/coupe.glb':('coupe.glb','model/gltf-binary'),'/wagon.glb':('wagon.glb','model/gltf-binary'),'/sport.glb':('sport.glb','model/gltf-binary'),'/engine.glb':('engine.glb','model/gltf-binary'),'/fleet-viewer.js':('fleet-viewer.js','text/javascript; charset=utf-8'),'/roadster2026.glb':('roadster2026.glb','model/gltf-binary'),'/HDRLoader.js':('HDRLoader.js','text/javascript; charset=utf-8'),'/studio.hdr':('studio.hdr','application/octet-stream'),'/brake.webp':('brake.webp','image/webp'),'/':('index.html','text/html; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/garage.webp':('garage.webp','image/webp'),'/mechanic.webp':('mechanic.webp','image/webp'),'/workshop.webp':('workshop.webp','image/webp'),'/car-viewer.js':('car-viewer.js','text/javascript; charset=utf-8'),'/three.module.js':('three.module.js','text/javascript; charset=utf-8'),'/three.core.js':('three.core.js','text/javascript; charset=utf-8'),'/GLTFLoader.js':('GLTFLoader.js','text/javascript; charset=utf-8'),'/BufferGeometryUtils.js':('BufferGeometryUtils.js','text/javascript; charset=utf-8')}
        if route not in mapping: self.send_error(404); return
        filename,ctype=mapping[route]; data=(PUBLIC/filename).read_bytes();self.send_response(200);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)));self.headers_common();self.end_headers();self.wfile.write(data)
    def do_POST(self):
        path=urlsplit(self.path).path
        if path not in ('/api/booking','/api/support'): self.reply_json(404,{'error':'Страница не найдена.'});return
        if self.headers.get_content_type()!='application/json': self.reply_json(415,{'error':'Неверный формат запроса.'});return
        try: length=int(self.headers.get('Content-Length','0'))
        except ValueError: self.reply_json(400,{'error':'Неверный запрос.'});return
        if length<=0 or length>MAX_BODY: self.reply_json(413,{'error':'Запрос слишком большой.'});return
        now=time.monotonic(); q=rate[self.client_address[0]]
        while q and q[0]<now-600: q.popleft()
        if len(q)>=10: self.reply_json(429,{'error':'Слишком много запросов. Попробуйте позже.'});return
        q.append(now)
        try:
            data=json.loads(self.rfile.read(length));
            if isinstance(data,dict) and data.get('website'): self.reply_json(400,{'error':'Запрос отклонён.'});return
            row=validate('booking' if path.endswith('booking') else 'support',data)
            row_id,status=store_and_notify(row)
            self.reply_json(201,{'ok':True,'id':row_id,'email_sent':status=='sent'})
        except (ValueError,UnicodeDecodeError,json.JSONDecodeError) as exc: self.reply_json(400,{'error':str(exc) if isinstance(exc,ValueError) and not isinstance(exc,json.JSONDecodeError) else 'Проверьте заполнение полей.'})
        except Exception as exc:
            print('Ошибка обработки:',type(exc).__name__,file=sys.stderr);self.reply_json(500,{'error':'Не удалось сохранить обращение. Попробуйте позже.'})

def main():
    if len(sys.argv)>1 and sys.argv[1]=='retry': retry_unsent();return
    if len(sys.argv)>1 and sys.argv[1]=='list':
        with db_connect() as db:
            for row in db.execute('SELECT id,kind,created_at,name,phone,email,car,service,message,email_status,email_error FROM requests ORDER BY id DESC'):
                print(json.dumps(dict(row),ensure_ascii=False))
        return
    db_connect().close()
    host=os.getenv('HOST','127.0.0.1'); port=int(os.getenv('PORT','8000'))
    server=ThreadingHTTPServer((host,port),Handler)
    print(f'Сайт запущен: http://{host}:{port} (остановить: Ctrl+C)',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__=='__main__': main()
