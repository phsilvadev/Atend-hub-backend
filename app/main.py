import logging
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.api.routes import router
from app.core.config import get_settings

app = FastAPI(title='AtendeHub Auth API', version='0.1.0')
app.include_router(router)
logger = logging.getLogger('atendehub')

@app.middleware('http')
async def security(request: Request, call_next):
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
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
