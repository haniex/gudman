"""WSGI-точка входа для PythonAnywhere; сама бизнес-логика общая с server.py."""
import os, json, time
from pathlib import Path
from collections import defaultdict, deque

# Конфигурация почты хранится отдельно от кода и недоступна через веб-сервер.
config_file = Path.home() / '.tochka_config.json'
if config_file.exists():
    with config_file.open(encoding='utf-8') as f:
        for key, value in json.load(f).items():
            if key in ('SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD','MAIL_TO','SMTP_FROM'):
                os.environ.setdefault(key, str(value))
import server

FILES = {'/bmw.glb':('bmw.glb','model/gltf-binary'),'/porsche.glb':('porsche.glb','model/gltf-binary'),'/audi.glb':('audi.glb','model/gltf-binary'),'/x5/O_G05_Exterior_Paint.gltf':('x5/O_G05_Exterior_Paint.gltf','model/gltf+json'),'/x5/O_G05_Exterior_non-Paint.gltf':('x5/O_G05_Exterior_non-Paint.gltf','model/gltf+json'),'/x5/O_G05_Headlights.gltf':('x5/O_G05_Headlights.gltf','model/gltf+json'),'/x5/O_G05_Taillights.gltf':('x5/O_G05_Taillights.gltf','model/gltf+json'),'/x5/O_G05_Hood.gltf':('x5/O_G05_Hood.gltf','model/gltf+json'),'/x5/O_G05_Doors_F.gltf':('x5/O_G05_Doors_F.gltf','model/gltf+json'),'/x5/O_G05_Doors_B.gltf':('x5/O_G05_Doors_B.gltf','model/gltf+json'),'/x5/O_G05_Tailgate.gltf':('x5/O_G05_Tailgate.gltf','model/gltf+json'),'/x5/O_G05_Interior_Color.gltf':('x5/O_G05_Interior_Color.gltf','model/gltf+json'),'/x5/O_G05_Interior_non-Color.gltf':('x5/O_G05_Interior_non-Color.gltf','model/gltf+json'),'/x5/O_G05_Seats.gltf':('x5/O_G05_Seats.gltf','model/gltf+json'),'/x5/O_G05_SteeringWheel.gltf':('x5/O_G05_SteeringWheel.gltf','model/gltf+json'),'/x5/O_G05_Emblem.gltf':('x5/O_G05_Emblem.gltf','model/gltf+json'),'/x5/O_G05_LicensePlates.gltf':('x5/O_G05_LicensePlates.gltf','model/gltf+json'),'/x5/O_G05_Wheels.gltf':('x5/O_G05_Wheels.gltf','model/gltf+json'),'/hatch.glb':('hatch.glb','model/gltf-binary'),'/suv.glb':('suv.glb','model/gltf-binary'),'/coupe.glb':('coupe.glb','model/gltf-binary'),'/wagon.glb':('wagon.glb','model/gltf-binary'),'/sport.glb':('sport.glb','model/gltf-binary'),'/engine.glb':('engine.glb','model/gltf-binary'),'/fleet-viewer.js':('fleet-viewer.js','text/javascript; charset=utf-8'),'/roadster2026.glb':('roadster2026.glb','model/gltf-binary'),'/HDRLoader.js':('HDRLoader.js','text/javascript; charset=utf-8'),'/studio.hdr':('studio.hdr','application/octet-stream'),'/brake.webp':('brake.webp','image/webp'),'/': ('index.html','text/html; charset=utf-8'),
 '/style.css': ('style.css','text/css; charset=utf-8'), '/app.js': ('app.js','text/javascript; charset=utf-8'),
 '/car-viewer.js': ('car-viewer.js','text/javascript; charset=utf-8'), '/three.module.js': ('three.module.js','text/javascript; charset=utf-8'),
 '/three.core.js': ('three.core.js','text/javascript; charset=utf-8'), '/GLTFLoader.js': ('GLTFLoader.js','text/javascript; charset=utf-8'),
 '/BufferGeometryUtils.js': ('BufferGeometryUtils.js','text/javascript; charset=utf-8'), 
 '/garage.webp': ('garage.webp','image/webp'), '/mechanic.webp': ('mechanic.webp','image/webp'), '/workshop.webp': ('workshop.webp','image/webp')}
_rates=defaultdict(deque)
SECURITY=[('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),('X-Frame-Options','DENY'),('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self' blob: data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")]
def respond(start_response,status,body,content_type='application/json; charset=utf-8'):
    if isinstance(body,dict): body=json.dumps(body,ensure_ascii=False).encode()
    start_response(status,[('Content-Type',content_type),('Content-Length',str(len(body))),('Cache-Control','no-store')]+SECURITY)
    return [body]

def application(environ,start_response):
    path=environ.get('PATH_INFO','/');method=environ.get('REQUEST_METHOD','GET')
    if method in ('GET','HEAD') and path in FILES:
        filename,kind=FILES[path]
        data=(server.PUBLIC / filename).read_bytes()
        start_response('200 OK',[('Content-Type',kind),('Content-Length',str(len(data)))]+SECURITY)
        return [b'' if method=='HEAD' else data]
    if method!='POST' or path not in ('/api/booking','/api/support'):
        return respond(start_response,'404 Not Found',{'error':'Страница не найдена.'})
    if environ.get('CONTENT_TYPE','').split(';')[0].strip()!='application/json':
        return respond(start_response,'415 Unsupported Media Type',{'error':'Неверный формат запроса.'})
    try: length=int(environ.get('CONTENT_LENGTH','0'))
    except ValueError: length=0
    if length<=0 or length>server.MAX_BODY:
        return respond(start_response,'413 Payload Too Large',{'error':'Неверный размер запроса.'})
    ip=environ.get('REMOTE_ADDR','unknown'); now=time.monotonic(); q=_rates[ip]
    while q and q[0]<now-600: q.popleft()
    if len(q)>=10: return respond(start_response,'429 Too Many Requests',{'error':'Слишком много запросов. Попробуйте позже.'})
    q.append(now)
    try:
        data=json.loads(environ['wsgi.input'].read(length))
        if isinstance(data,dict) and data.get('website'): return respond(start_response,'400 Bad Request',{'error':'Запрос отклонён.'})
        row=server.validate('booking' if path.endswith('booking') else 'support',data)
        row_id,status=server.store_and_notify(row)
        return respond(start_response,'201 Created',{'ok':True,'id':row_id,'email_sent':status=='sent'})
    except (ValueError,UnicodeDecodeError) as e:
        return respond(start_response,'400 Bad Request',{'error':str(e) if not isinstance(e,json.JSONDecodeError) else 'Проверьте заполнение полей.'})
    except Exception as e:
        print('Ошибка обработки:',type(e).__name__,file=environ['wsgi.errors'])
        return respond(start_response,'500 Internal Server Error',{'error':'Не удалось сохранить обращение. Попробуйте позже.'})
