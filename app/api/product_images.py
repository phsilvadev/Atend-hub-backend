"""Authenticated tenant image upload/read. Firebase objects remain private."""
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.api.dependencies import Context, admin_context, active_tenant, current_context
from app.api.gestaoclick import authorize_fresh
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import now, throttle
from app.models.auth import Company
from app.models.products import Product
from app.services.auth import audit
from app.services.product_images import prepare_image, FORMATS
from app.integrations.firebase import product_images as storage

router = APIRouter(prefix='/api/v1/products', tags=['Imagens de produtos'])
logger = logging.getLogger('atendehub')

def lookup(db, company_id, product_id):
    row = db.scalar(select(Product).where(Product.id == str(product_id), Product.company_id == company_id))
    if not row:
        raise HTTPException(404, 'Produto não encontrado.')
    return row

def cleanup(company_id, product_id, key, generation):
    if not key:
        return
    try:
        storage.delete_image(company_id, product_id, key, generation)
    except storage.StorageUnavailable:
        # Never log object names, credentials or SDK error payloads.
        logger.warning('product_image_cleanup_pending')

@router.post('/{product_id}/image')
async def upload_image(product_id: UUID, request: Request, version: int = Query(ge=0), context: Context = Depends(admin_context), db: Session = Depends(get_db)):
    company_id, product_id = context.company.id, str(product_id)
    row = lookup(db, company_id, product_id)
    if row.image_version != version:
        raise HTTPException(409, 'A imagem foi alterada. Recarregue o produto antes de enviar.')
    if not get_settings().firebase_storage_bucket:
        raise HTTPException(503, 'O armazenamento de imagens ainda não foi configurado pela plataforma.')
    throttle(db, f'product-image:{company_id}', 20)
    content_type = request.headers.get('content-type', '').split(';')[0].lower()
    if content_type not in FORMATS:
        raise HTTPException(415, 'Envie uma imagem JPG, PNG ou WebP.')
    length = request.headers.get('content-length')
    if length is not None and (not length.isdecimal() or int(length) > storage.MAX_BYTES):
        raise HTTPException(413, 'Envie uma imagem de até 5 MB.')
    contents = bytearray()
    async for chunk in request.stream():
        if len(contents) + len(chunk) > storage.MAX_BYTES:
            raise HTTPException(413, 'Envie uma imagem de até 5 MB.')
        contents.extend(chunk)
    db.commit()  # No write transaction while decoding/uploading.
    clean = await run_in_threadpool(prepare_image, bytes(contents), content_type)
    try:
        key, generation = await run_in_threadpool(storage.put_image, company_id, product_id, clean)
    except storage.StorageUnavailable:
        raise HTTPException(503, 'Não foi possível enviar ao Firebase. A imagem anterior foi preservada.') from None
    try:
        db.execute(update(Company).where(Company.id == company_id).values(name=Company.name))
        authorize_fresh(db, context)
        row = lookup(db, company_id, product_id)
        if row.image_version != version:
            raise HTTPException(409, 'Outro envio atualizou a imagem. Recarregue o produto.')
        old_key, old_generation = row.image_object, row.image_generation
        row.image_object, row.image_generation = key, generation
        row.image_version += 1
        row.image_updated_at = now()
        audit(db, context.user, 'product.image_uploaded')
        db.commit()
        result = {'company_id': company_id, 'product_id': product_id, 'has_image': True, 'image_version': row.image_version, 'image_updated_at': row.image_updated_at}
    except Exception:
        db.rollback()
        await run_in_threadpool(cleanup, company_id, product_id, key, generation)
        raise
    await run_in_threadpool(cleanup, company_id, product_id, old_key, old_generation)
    return result

@router.get('/{product_id}/image')
async def read_image(product_id: UUID, request: Request, context: Context = Depends(active_tenant), db: Session = Depends(get_db)):
    company_id, product_id = context.company.id, str(product_id)
    row = lookup(db, company_id, product_id)
    if not row.image_object:
        raise HTTPException(404, 'Produto sem imagem.')
    key, generation = row.image_object, row.image_generation
    db.commit()
    try:
        contents = await run_in_threadpool(storage.read_image, company_id, product_id, key, generation)
    except storage.StorageUnavailable:
        raise HTTPException(503, 'Não foi possível carregar a imagem.') from None
    db.expire_all()
    active_tenant(current_context(request, db))
    if contents is None:
        raise HTTPException(404, 'Imagem indisponível.')
    return Response(contents, media_type='image/webp', headers={'Cache-Control': 'private, no-store', 'Content-Disposition': 'inline; filename="produto.webp"', 'X-Content-Type-Options': 'nosniff'})
