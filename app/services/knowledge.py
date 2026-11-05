import hashlib
import json
import re
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.core.security import now
from app.models.knowledge import KnowledgeImport, KnowledgeEntry, KnowledgeRevision, KnowledgeApproval
from app.services.platform_auth import audit

# Assisted redaction, never a guarantee of anonymization. Publication always needs review.
IDENTIFIERS=[r'https?://\S+',r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b',r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b',r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b',r'(?<![\w-])(?:\+?55[ ()-]*)?(?:\(\d{2}\)[ -]*|\d{2}[ -]+)?(?:9\d{4}[- ]\d{4}|[2-5]\d{3}[- ]\d{4})(?![\w-])',r'(?<![\w-])\d{10,14}(?![\w-])']
PUBLICATION_BLOCK=r'(?i)R\$|\b(?:desconto|frete|pagamento|prazo|estoque|entrega|retirada)\b[^\n.!?]{0,40}\d+|\b(?:frete|entrega)\b.{0,20}\b(?:grátis|gratuito|amanhã|hoje)\b|\b(?:temos|restam)\s+\d+\b'
COMMERCIAL=r'(?i)R\$|\b(?:desconto|frete|pagamento|boleto|pix|negociad[oa]|condiç(?:ão|ões) comercial)\b'

def sanitize(text,terms):
    if re.search(COMMERCIAL,text):
        return '[CONDIÇÃO COMERCIAL REMOVIDA]',1
    count=0
    for term in sorted(terms,key=len,reverse=True):
        text,found=re.subn(r'(?<!\w)'+re.escape(term)+r'(?!\w)','[IDENTIFICADOR REMOVIDO]',text,flags=re.IGNORECASE);count+=found
    for pattern in IDENTIFIERS:
        text,found=re.subn(pattern,'[DADO REMOVIDO]',text,flags=re.IGNORECASE);count+=found
    return text,count

def get_entry(db,entry_id):
    entry=db.get(KnowledgeEntry,str(entry_id))
    if not entry: raise HTTPException(404,'Conteúdo não encontrado.')
    return entry

def revision_output(revision):
    return {field:getattr(revision,field) for field in ['revision','title','body','kind','source_reference','category','created_at']}

def entry_output(db,entry,public=False):
    number=entry.published_revision if public else entry.current_revision
    revision=db.get(KnowledgeRevision,(entry.id,number))
    result={'id':entry.id,'scope':'platform',**revision_output(revision)}
    if not public:
        result.update(version=entry.version,current_revision=entry.current_revision,published_revision=entry.published_revision,active=entry.active,import_id=entry.import_id)
    return result

def create_entry(db,admin,data,import_id=None):
    entry=KnowledgeEntry(import_id=import_id,created_at=now(),version=1,current_revision=1,active=False)
    db.add(entry);db.flush()
    db.add(KnowledgeRevision(entry_id=entry.id,revision=1,admin_id=admin.id,created_at=now(),**data))
    audit(db,admin,'knowledge.draft.created',entry.id)
    return entry

def change_entry(db,admin,entry_id,data):
    entry=get_entry(db,entry_id)
    number=entry.current_revision+1
    result=db.execute(update(KnowledgeEntry).where(KnowledgeEntry.id == entry.id,KnowledgeEntry.version == data.version).values(version=KnowledgeEntry.version+1,current_revision=number))
    if result.rowcount != 1:
        db.rollback();raise HTTPException(409,'Conteúdo atualizado por outra pessoa. Recarregue antes de editar.')
    db.add(KnowledgeRevision(entry_id=entry.id,revision=number,admin_id=admin.id,created_at=now(),**data.model_dump(exclude={'version'})))
    audit(db,admin,'knowledge.draft.updated',entry.id);db.commit();db.refresh(entry)
    return entry

def publish(db,admin,entry_id,data):
    entry=get_entry(db,entry_id)
    current=db.get(KnowledgeRevision,(entry.id,entry.current_revision))
    text='\n'.join([current.title,current.body,current.source_reference])
    if re.search(PUBLICATION_BLOCK,text) or any(re.search(pattern,text,re.IGNORECASE) for pattern in IDENTIFIERS[1:]):
        raise HTTPException(422,'Remova dados identificáveis e condições comerciais particulares antes de publicar.')
    result=db.execute(update(KnowledgeEntry).where(KnowledgeEntry.id == entry.id,KnowledgeEntry.version == data.version).values(version=KnowledgeEntry.version+1,published_revision=entry.current_revision,active=True))
    if result.rowcount != 1:
        db.rollback();raise HTTPException(409,'Versão desatualizada. Recarregue e revise o conteúdo atual.')
    db.add(KnowledgeApproval(entry_id=entry.id,revision=entry.current_revision,admin_id=admin.id,review_note=data.review_note.strip(),created_at=now()))
    audit(db,admin,'knowledge.published',entry.id);db.commit();db.refresh(entry)
    return entry

def deactivate(db,admin,entry_id,version):
    entry=get_entry(db,entry_id)
    result=db.execute(update(KnowledgeEntry).where(KnowledgeEntry.id == entry.id,KnowledgeEntry.version == version).values(active=False,version=KnowledgeEntry.version+1))
    if result.rowcount != 1:
        db.rollback();raise HTTPException(409,'Versão desatualizada.')
    audit(db,admin,'knowledge.deactivated',entry.id);db.commit();db.refresh(entry)
    return entry

def import_output(db,batch):
    ids=list(db.scalars(select(KnowledgeEntry.id).where(KnowledgeEntry.import_id == batch.id)).all())
    return {'id':batch.id,'authorization_reference':batch.authorization_reference,'sanitized_messages':batch.sanitized_messages,'redactions':batch.redactions,'candidate_ids':ids,'requires_manual_review':True,'method':'adjacent_turns_v1','created_at':batch.created_at}

def import_turns(db,admin,data):
    fingerprint=hashlib.sha256(json.dumps(data.model_dump(mode='json'),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    existing=db.scalar(select(KnowledgeImport).where(KnowledgeImport.admin_id == admin.id,KnowledgeImport.request_id == str(data.request_id)))
    if existing:
        if existing.request_hash != fingerprint: raise HTTPException(409,'Solicitação de importação reutilizada com conteúdo diferente.')
        return existing
    messages=[];total=0
    for turn in data.messages:
        text,count=sanitize(turn.text,data.redaction_terms)
        messages.append({'role':turn.role,'text':text[:12000],'truncated':len(text)>12000});total+=count
    batch=KnowledgeImport(admin_id=admin.id,request_id=str(data.request_id),request_hash=fingerprint,authorization_reference=data.authorization_reference,sanitized_messages=messages,redactions=total,created_at=now())
    db.add(batch)
    try:
        db.flush()
        for question,answer in zip(messages,messages[1:]):
            if question['role'] != 'customer' or answer['role'] != 'agent' or '[CONDIÇÃO COMERCIAL REMOVIDA]' in (question['text'],answer['text']):
                continue
            title=question['text'].strip()[:180]
            if len(title)<3: continue
            create_entry(db,admin,dict(title=title,body=f"Pergunta: {question['text']}\nResposta: {answer['text']}",kind='faq',category='Ferro e aço',source_reference=f'Conversa autorizada, importação {batch.id}'),batch.id)
        audit(db,admin,'knowledge.imported',batch.id);db.commit()
    except IntegrityError:
        db.rollback()
        existing=db.scalar(select(KnowledgeImport).where(KnowledgeImport.admin_id == admin.id,KnowledgeImport.request_id == str(data.request_id)))
        if existing and existing.request_hash == fingerprint: return existing
        raise HTTPException(409,'Importação concorrente. Recarregue antes de tentar novamente.')
    return batch
