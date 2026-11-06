"""Explicit, resumable imports. Publish only after every ERP page is validated."""
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.orm import Session
from app.api.dependencies import Context, admin_context, active_tenant
from app.api.gestaoclick import Version, decrypt, authorize_fresh
from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import now, throttle
from app.models.auth import Company
from app.models.gestaoclick import GestaoClickConnection
from app.models.products import Product, ProductSync, ProductSyncItem
from app.schemas.auth import StrictInput
from app.services.auth import audit
from app.integrations.gestaoclick import product_page, ERPError

router = APIRouter(prefix='/api/v1', tags=['Produtos'])

def progress(row, company_id):
    return {'company_id': company_id, 'run_id': row.run_id if row else None,
            'status': row.status if row else 'idle', 'processed': row.processed if row else 0,
            'pages_done': row.next_page - 1 if row else 0, 'total_pages': row.total_pages if row else None,
            'started_at': row.started_at if row else None, 'completed_at': row.completed_at if row else None,
            'last_success_at': row.last_success_at if row else None, 'error_code': row.error_code if row else None}

@router.get('/integrations/gestaoclick/products-sync')
def sync_status(context: Context = Depends(admin_context), db: Session = Depends(get_db)):
    return progress(db.get(ProductSync, context.company.id), context.company.id)

@router.post('/integrations/gestaoclick/products-sync/start')
def start(data: Version, context: Context = Depends(admin_context), db: Session = Depends(get_db)):
    company_id = context.company.id
    throttle(db, f'gestaoclick:products:start:{company_id}', 10)
    db.execute(update(Company).where(Company.id == company_id).values(name=Company.name))
    connection = db.get(GestaoClickConnection, company_id)
    if not connection or not connection.encrypted_credentials or connection.version != data.version or not connection.selected_store_id:
        raise HTTPException(409, 'Salve as credenciais e selecione a loja antes de sincronizar.')
    row = db.get(ProductSync, company_id)
    if row and row.status == 'running' and now() - row.started_at < 3600:
        raise HTTPException(409, 'Já existe uma sincronização em andamento. Continue o processamento.')
    last_success = row.last_success_at if row else None
    db.execute(delete(ProductSyncItem).where(ProductSyncItem.company_id == company_id))
    if not row:
        row = ProductSync(company_id=company_id)
        db.add(row)
    row.run_id = str(uuid4())
    row.credential_version = connection.version
    row.store_id = connection.selected_store_id
    row.status = 'running'
    row.next_page = 1
    row.total_pages = None
    row.processed = 0
    row.started_at = now()
    row.completed_at = None
    row.last_success_at = last_success
    row.error_code = None
    row.lease_until = None
    audit(db, context.user, 'gestaoclick.products_sync_started')
    db.commit()
    return progress(row, company_id)

class Continue(StrictInput):
    run_id: str = Field(pattern=r'^[a-f0-9-]{36}$')

@router.post('/integrations/gestaoclick/products-sync/next')
def next_page(data: Continue, context: Context = Depends(admin_context), db: Session = Depends(get_db)):
    company_id = context.company.id
    db.execute(update(Company).where(Company.id == company_id).values(name=Company.name))
    row = db.get(ProductSync, company_id)
    connection = db.get(GestaoClickConnection, company_id)
    if not row or row.run_id != data.run_id:
        raise HTTPException(404, 'Sincronização não encontrada.')
    if row.status != 'running':
        return progress(row, company_id)
    if row.lease_until and row.lease_until > now():
        raise HTTPException(429, 'Aguarde o processamento da página atual.', headers={'Retry-After': '1'})
    if not connection or not connection.encrypted_credentials or connection.version != row.credential_version or connection.selected_store_id != row.store_id:
        row.status = 'failed'; row.error_code = 'configuration_changed'; row.completed_at = now()
        db.execute(delete(ProductSyncItem).where(ProductSyncItem.company_id == company_id))
        db.commit()
        raise HTTPException(409, 'A configuração mudou. Inicie uma nova sincronização.')
    credentials = decrypt(connection.encrypted_credentials, company_id, connection.base_url)
    url, store_id, page, version = connection.base_url, row.store_id, row.next_page, row.credential_version
    row.lease_until = now() + 30
    lease = row.lease_until
    db.commit()
    error = None
    try:
        items, pages, total = product_page(url, credentials, store_id, page)
    except ERPError as exc:
        error = exc
    db.execute(update(Company).where(Company.id == company_id).values(name=Company.name))
    authorize_fresh(db, context)
    row = db.get(ProductSync, company_id)
    connection = db.get(GestaoClickConnection, company_id)
    if not row or row.run_id != data.run_id or row.next_page != page or row.lease_until != lease or row.status != 'running':
        raise HTTPException(409, 'O processamento foi atualizado. Recarregue o progresso.')
    if not connection or not connection.encrypted_credentials or connection.version != version or connection.selected_store_id != store_id:
        error = ERPError('configuration_changed', 'A configuração mudou. Inicie uma nova sincronização.', 409)
    if not error and row.total_pages is not None and row.total_pages != pages:
        error = ERPError('catalog_changed', 'O catálogo mudou durante a consulta. Inicie novamente.', 409)
    if not error:
        ids = [item['erp_id'] for item in items]
        existing = db.scalar(select(func.count()).select_from(ProductSyncItem).where(ProductSyncItem.company_id == company_id, ProductSyncItem.erp_id.in_(ids))) if ids else 0
        if len(set(ids)) != len(ids) or existing or (page < pages and not items) or row.processed + len(items) > total:
            error = ERPError('catalog_changed', 'Paginação inconsistente. Inicie uma nova sincronização.', 409)
    if error:
        row.status = 'failed'; row.error_code = error.code; row.completed_at = now(); row.lease_until = None
        db.execute(delete(ProductSyncItem).where(ProductSyncItem.company_id == company_id))
        audit(db, context.user, 'gestaoclick.products_sync_failed')
        db.commit()
        raise HTTPException(error.status, error.message)
    for item in items:
        db.add(ProductSyncItem(company_id=company_id, erp_id=item['erp_id'], data=item))
    row.processed += len(items)
    row.total_pages = pages
    row.next_page += 1
    row.lease_until = now() + 1  # At most one page per second, including other browser tabs.
    if page == pages:
        if row.processed != total:
            row.status = 'failed'; row.error_code = 'catalog_changed'; row.completed_at = now()
            db.execute(delete(ProductSyncItem).where(ProductSyncItem.company_id == company_id))
            db.commit()
            raise HTTPException(409, 'O total do catálogo mudou. Inicie novamente.')
        db.flush()
        catalog = {product.erp_id: product for product in db.scalars(select(Product).where(Product.company_id == company_id))}
        for staged in db.scalars(select(ProductSyncItem).where(ProductSyncItem.company_id == company_id)):
            product = catalog.get(staged.erp_id)
            if not product:
                product = Product(id=str(uuid4()), company_id=company_id, erp_id=staged.erp_id)
                db.add(product)
            for key, value in staged.data.items():
                setattr(product, key, value)
            product.synced_at = now()
        row.status = 'completed'; row.completed_at = now(); row.last_success_at = now(); row.lease_until = None
        db.execute(delete(ProductSyncItem).where(ProductSyncItem.company_id == company_id))
        audit(db, context.user, 'gestaoclick.products_synced')
    db.commit()
    return progress(row, company_id)

@router.get('/products')
def list_products(q: str = Query('', max_length=120), page: int = Query(1, ge=1), context: Context = Depends(active_tenant), db: Session = Depends(get_db)):
    conditions = [Product.company_id == context.company.id]
    if q.strip():
        escaped = q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        conditions.append(or_(Product.name.ilike(f'%{escaped}%', escape='\\'), Product.code.ilike(f'%{escaped}%', escape='\\')))
    total = db.scalar(select(func.count()).select_from(Product).where(*conditions))
    rows = db.scalars(select(Product).where(*conditions).order_by(Product.name, Product.id).offset((page - 1) * 20).limit(20))
    return {'company_id': context.company.id, 'total': total, 'page': page, 'page_size': 20, 'image_upload_enabled': bool(get_settings().firebase_storage_bucket), 'items': [
        {**{key: getattr(row, key) for key in ['id', 'erp_id', 'code', 'name', 'description', 'category', 'active', 'has_variations', 'synced_at', 'image_version', 'image_updated_at']}, 'has_image': bool(row.image_object)} for row in rows]}
