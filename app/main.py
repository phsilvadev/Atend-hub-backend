import logging
from urllib.parse import urlsplit
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.api.gestaoclick import router as gestaoclick_router
from app.api.products import router as products_router
from app.api.product_images import router as product_images_router
from app.api.client_auth import router as client_auth_router
from app.api.routes import router
from app.api.whatsapp_official import router as official_router
from app.api.whatsapp_qr import router as qr_router, QR_WEBHOOK_PATH
from app.api.whatsapp import router as whatsapp_router, WEBHOOK_PATH
from app.api.conversations import router as conversations_router
from app.api.platform_companies import router as companies_router
from app.api.knowledge import router as platform_router, public_router as knowledge_router
from app.core.config import get_settings
from app.core.database import get_db

from app.api.platform_settings import router as platform_settings_router

app = FastAPI(title='AtendeHub Auth API', version='0.1.0')
app.include_router(router)
app.include_router(platform_settings_router)
app.include_router(client_auth_router)
app.include_router(gestaoclick_router)
app.include_router(products_router)
app.include_router(product_images_router)
app.include_router(whatsapp_router)
app.include_router(qr_router)
app.include_router(official_router)
app.include_router(conversations_router)
app.include_router(platform_router)
app.include_router(knowledge_router)
app.include_router(companies_router)
logger = logging.getLogger('atendehub')

@app.middleware('http')
async def security(request: Request, call_next):
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'} and not (request.method == 'POST' and request.url.path in {WEBHOOK_PATH, QR_WEBHOOK_PATH}):
        origin = request.headers.get('origin')
        if not origin and request.headers.get('referer'):
            parsed = urlsplit(request.headers['referer'])
            origin = f'{parsed.scheme}://{parsed.netloc}'
        if origin not in get_settings().allowed_origins:
            return JSONResponse({'detail': 'Origem não permitida.'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    return response

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse({'detail': 'Dados inválidos. Confira os campos e os limites informados.'}, status_code=422)

@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logger.error('request_failed', extra={'error_type': type(exc).__name__})
    return JSONResponse({'detail': 'Não foi possível concluir a operação.'}, status_code=500)

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/health/ready')
def readiness(db=Depends(get_db)):
    # No configuration values or database error text in health responses.
    from sqlalchemy import text
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    try:
        db.execute(text('SELECT 1'))
        current = db.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        if current != ScriptDirectory.from_config(Config('alembic.ini')).get_current_head():
            raise ValueError()
    except Exception:
        return JSONResponse({'status': 'not_ready'}, status_code=503)
    return {'status': 'ready'}
