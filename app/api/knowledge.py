from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import select, func, or_, and_
from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import throttle, now
from app.api.dependencies import active_tenant
from app.schemas.auth import LoginInput
from app.schemas.knowledge import KnowledgeInput, KnowledgeEdit, PublishInput, VersionInput, ImportInput
from app.models.knowledge import KnowledgeEntry, KnowledgeRevision, KnowledgeImport
from app.services import platform_auth as auth, knowledge as service, turnstile

router=APIRouter(prefix='/api/v1/platform',tags=['Plataforma e base comum'])
public_router=APIRouter(prefix='/api/v1/knowledge',tags=['Conhecimento publicado'])

@router.post('/auth/login')
def login(data:LoginInput,request:Request,response:Response,db=Depends(get_db),settings=Depends(get_settings)):
    ip=request.client.host if request.client else 'unknown'
    throttle(db,f'platform.login.ip:{ip}',50);throttle(db,f'platform.login.email:{data.email}',10)
    turnstile.verify(db,settings,data.challenge_token,'platform_login')
    admin,token=auth.login(db,data)
    response.set_cookie(auth.PLATFORM_COOKIE,token,max_age=auth.LIFETIME,httponly=True,secure=settings.cookie_secure,samesite='lax',path='/api/v1/platform')
    return {'id':admin.id,'name':admin.name,'role':'platform_admin'}

@router.get('/auth/me')
def me(context=Depends(auth.platform_context)):
    return {'id':context.admin.id,'name':context.admin.name,'role':'platform_admin'}

@router.post('/auth/logout',status_code=204)
def logout(response:Response,context=Depends(auth.platform_context),db=Depends(get_db),settings=Depends(get_settings)):
    context.session.revoked=True;auth.audit(db,context.admin,'platform.logout');db.commit()
    response.delete_cookie(auth.PLATFORM_COOKIE,path='/api/v1/platform',httponly=True,secure=settings.cookie_secure,samesite='lax')

async def import_body(request:Request):
    chunks=[];size=0
    async for chunk in request.stream():
        size+=len(chunk)
        if size>524288: raise HTTPException(413,'Arquivo excede 512 KiB.')
        chunks.append(chunk)
    try:
        return ImportInput.model_validate_json(b''.join(chunks))
    except ValidationError:
        raise HTTPException(422,'Arquivo JSON inválido. Confira autorização, mensagens e limites.') from None

@router.post('/knowledge/imports',status_code=201)
def import_file(context=Depends(auth.platform_context),data=Depends(import_body),db=Depends(get_db)):
    return service.import_output(db,service.import_turns(db,context.admin,data))

@router.get('/knowledge/imports')
def imports(offset:int=Query(default=0,ge=0),limit:int=Query(default=20,ge=1,le=50),context=Depends(auth.platform_context),db=Depends(get_db)):
    batches=db.scalars(select(KnowledgeImport).order_by(KnowledgeImport.created_at.desc(),KnowledgeImport.id).offset(offset).limit(limit)).all()
    return {'items':[service.import_output(db,batch) for batch in batches]}

@router.get('/knowledge/imports/{batch_id}')
def get_import(batch_id:UUID,context=Depends(auth.platform_context),db=Depends(get_db)):
    batch=db.get(KnowledgeImport,str(batch_id))
    if not batch: raise HTTPException(404,'Importação não encontrada.')
    return service.import_output(db,batch)

@router.get('/knowledge')
def entries(offset:int=Query(default=0,ge=0),limit:int=Query(default=20,ge=1,le=50),
            q:str=Query(default='',max_length=100),
            status:Literal['all','review','published','inactive']='all',
            kind:Literal['all','faq','technical_document','synonym','approved_answer']='all',
            category:str=Query(default='',max_length=80),
            context=Depends(auth.platform_context),db=Depends(get_db)):
    base=select(KnowledgeEntry).join(KnowledgeRevision,
        (KnowledgeRevision.entry_id == KnowledgeEntry.id)&(KnowledgeRevision.revision == KnowledgeEntry.current_revision))
    review=or_(KnowledgeEntry.published_revision.is_(None),
               and_(KnowledgeEntry.active.is_(True),KnowledgeEntry.current_revision != KnowledgeEntry.published_revision))
    published=and_(KnowledgeEntry.active.is_(True),KnowledgeEntry.current_revision == KnowledgeEntry.published_revision)
    inactive=and_(KnowledgeEntry.active.is_(False),KnowledgeEntry.published_revision.is_not(None))
    count=lambda query: db.scalar(select(func.count()).select_from(query.subquery()))
    summary={'total':count(base),'review':count(base.where(review)),
             'published':count(base.where(published)),'inactive':count(base.where(inactive))}
    categories=list(db.scalars(select(KnowledgeRevision.category).join(KnowledgeEntry,
        (KnowledgeRevision.entry_id == KnowledgeEntry.id)&(KnowledgeRevision.revision == KnowledgeEntry.current_revision))
        .distinct().order_by(KnowledgeRevision.category)).all())
    query=base
    if q.strip(): query=query.where(or_(*[field.icontains(q.strip(),autoescape=True) for field in
        (KnowledgeRevision.title,KnowledgeRevision.body,KnowledgeRevision.source_reference)]))
    if status != 'all': query=query.where({'review':review,'published':published,'inactive':inactive}[status])
    if kind != 'all': query=query.where(KnowledgeRevision.kind == kind)
    if category: query=query.where(KnowledgeRevision.category == category)
    total=count(query)
    rows=db.scalars(query.order_by(KnowledgeEntry.created_at.desc(),KnowledgeEntry.id).offset(offset).limit(limit)).all()
    return {'items':[service.entry_output(db,row) for row in rows], 'total':total,'summary':summary,'categories':categories}

@router.post('/knowledge',status_code=201)
def create(data:KnowledgeInput,context=Depends(auth.platform_context),db=Depends(get_db)):
    entry=service.create_entry(db,context.admin,data.model_dump());db.commit()
    return service.entry_output(db,entry)

@router.get('/knowledge/{entry_id}')
def detail(entry_id:UUID,context=Depends(auth.platform_context),db=Depends(get_db)):
    return service.entry_output(db,service.get_entry(db,entry_id))

@router.patch('/knowledge/{entry_id}')
def edit(entry_id:UUID,data:KnowledgeEdit,context=Depends(auth.platform_context),db=Depends(get_db)):
    return service.entry_output(db,service.change_entry(db,context.admin,entry_id,data))

@router.get('/knowledge/{entry_id}/revisions')
def revisions(entry_id:UUID,context=Depends(auth.platform_context),db=Depends(get_db)):
    entry=service.get_entry(db,entry_id)
    rows=db.scalars(select(KnowledgeRevision).where(KnowledgeRevision.entry_id == entry.id).order_by(KnowledgeRevision.revision)).all()
    return {'items':[service.revision_output(row) for row in rows]}

@router.post('/knowledge/{entry_id}/publish')
def publish(entry_id:UUID,data:PublishInput,context=Depends(auth.platform_context),db=Depends(get_db)):
    return service.entry_output(db,service.publish(db,context.admin,entry_id,data))

@router.post('/knowledge/{entry_id}/deactivate')
def deactivate(entry_id:UUID,data:VersionInput,context=Depends(auth.platform_context),db=Depends(get_db)):
    return service.entry_output(db,service.deactivate(db,context.admin,entry_id,data.version))

@public_router.get('')
def published(q:str=Query(default='',max_length=100),offset:int=Query(default=0,ge=0),limit:int=Query(default=20,ge=1,le=50),context=Depends(active_tenant),db=Depends(get_db)):
    query=select(KnowledgeEntry).join(KnowledgeRevision,(KnowledgeRevision.entry_id == KnowledgeEntry.id)&(KnowledgeRevision.revision == KnowledgeEntry.published_revision)).where(KnowledgeEntry.active.is_(True),KnowledgeEntry.published_revision.is_not(None))
    if q.strip(): query=query.where(KnowledgeRevision.body.icontains(q.strip(),autoescape=True)|KnowledgeRevision.title.icontains(q.strip(),autoescape=True))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.scalars(query.order_by(KnowledgeEntry.id).offset(offset).limit(limit)).all()
    return {'items':[service.entry_output(db,row,True) for row in rows],'total':total}

@public_router.get('/{entry_id}')
def published_detail(entry_id:UUID,context=Depends(active_tenant),db=Depends(get_db)):
    entry=service.get_entry(db,entry_id)
    if not entry.active or entry.published_revision is None: raise HTTPException(404,'Conteúdo não encontrado.')
    return service.entry_output(db,entry,True)


@router.get("/auth/challenge")
def challenge_configuration(settings=Depends(get_settings)):
    return turnstile.configuration(settings)
