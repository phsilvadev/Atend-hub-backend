from io import BytesIO
from uuid import uuid4
import pytest
from PIL import Image
from fastapi import HTTPException
from app.models.products import Product
from app.models.auth import User
from app.core.config import get_settings
from app.integrations.firebase import product_images as storage
from app.services import product_images as encoder

class MemoryBucket:
    """Only an SDK double: real HTTP auth, image decoder and SQL routes are exercised."""
    def __init__(self):
        self.objects = {}; self.deleted = []; self.counter = 0; self.fail = False
    def blob(self, key, generation=None):
        owner = self
        class Blob:
            cache_control = None
            def upload_from_string(self, contents, **kwargs):
                if owner.fail: raise RuntimeError('SECRET-CREDENTIAL-MUST-NOT-LEAK')
                assert kwargs['content_type'] == 'image/webp' and kwargs['if_generation_match'] == 0
                assert self.cache_control == 'private, no-store'
                owner.counter += 1; self.generation = owner.counter
                owner.objects[(key, str(self.generation))] = contents
            def download_as_bytes(self, **kwargs):
                return owner.objects[(key, str(generation))]
            def delete(self, **kwargs):
                assert kwargs['if_generation_match'] == int(generation)
                owner.deleted.append(key)
                owner.objects.pop((key, str(generation)), None)
        return Blob()

def png():
    buffer = BytesIO(); Image.new('RGB', (32, 24), '#e4b762').save(buffer, format='PNG')
    return buffer.getvalue()

def prepare(client, database, signup, monkeypatch):
    monkeypatch.setenv('FIREBASE_STORAGE_BUCKET', 'test-only.firebasestorage.app'); get_settings.cache_clear()
    identity = client.post('/api/v1/auth/register', json=signup).json()
    product_id = str(uuid4())
    with database() as db:
        db.add(Product(id=product_id, company_id=identity['company']['id'], erp_id='1', code='MT30', name='Metalon 30x30', description='', category='Metalon', active=True, has_variations=False, synced_at=1))
        db.commit()
    memory = MemoryBucket()
    monkeypatch.setattr(storage, '_bucket', lambda name: memory)
    return identity, product_id, memory

def upload(client, product_id, data=None, version=0, mime='image/png'):
    return client.post(f'/api/v1/products/{product_id}/image?version={version}', content=png() if data is None else data, headers={'Content-Type': mime})

def test_upload_private_read_replace_and_preserve_during_sync(client, database, signup, monkeypatch):
    identity, product_id, memory = prepare(client, database, signup, monkeypatch)
    assert client.get('/api/v1/products').json()['items'][0]['has_image'] is False
    assert client.get(f'/api/v1/products/{product_id}/image').status_code == 404
    result = upload(client, product_id)
    assert result.status_code == 200, result.text
    assert result.json()['image_version'] == 1 and result.json()['has_image'] is True
    assert 'companies/' not in result.text and 'generation' not in result.text
    listing = client.get('/api/v1/products').json()
    assert listing['image_upload_enabled'] is True and listing['items'][0]['has_image'] is True
    with database() as db:
        row = db.get(Product, product_id)
        old_key = row.image_object
        assert old_key.startswith(f"companies/{identity['company']['id']}/products/{product_id}/")
    image = client.get(f'/api/v1/products/{product_id}/image')
    assert image.status_code == 200 and image.headers['content-type'] == 'image/webp'
    assert 'no-store' in image.headers['cache-control']
    with Image.open(BytesIO(image.content)) as decoded:
        assert decoded.format == 'WEBP' and decoded.size == (32, 24) and not decoded.getexif()
    assert upload(client, product_id, version=0).status_code == 409
    assert len(memory.objects) == 1
    assert upload(client, product_id, version=1).status_code == 200
    assert old_key in memory.deleted and len(memory.objects) == 1
    # Run the actual ERP publication loop; product's own image remains untouched.
    from app.models.gestaoclick import GestaoClickConnection
    from app.api import products as products_api
    from app.integrations.gestaoclick import SERVER
    get_settings.cache_clear()
    # No credentials are needed by our adapter double; opaque saved value is decoded only locally.
    monkeypatch.setattr(products_api, 'decrypt', lambda *args: {})
    monkeypatch.setattr(products_api, 'product_page', lambda *args: ([{'erp_id':'1','code':'MT30','name':'Nome atualizado','description':'','category':'Metalon','active':True,'has_variations':False}], 1, 1))
    with database() as db:
        db.add(GestaoClickConnection(company_id=identity['company']['id'], base_url=SERVER, encrypted_credentials='test-only', version=1, updated_at=1, stores=[], selected_store_id='2'))
        db.commit()
    run = client.post('/api/v1/integrations/gestaoclick/products-sync/start', json={'version':1}).json()
    assert client.post('/api/v1/integrations/gestaoclick/products-sync/next', json={'run_id':run['run_id']}).status_code == 200
    product = client.get('/api/v1/products').json()['items'][0]
    assert product['has_image'] is True and product['image_version'] == 2 and product['name'] == 'Nome atualizado'

@pytest.mark.parametrize('data,mime,status', [
    (b'<svg><script>evil()</script></svg>', 'image/svg+xml', 415),
    (b'not-an-image', 'image/png', 422),
    (b'', 'image/png', 413),
    (png(), 'image/jpeg', 422),
    (b'x' * (5 * 1024 * 1024 + 1), 'image/png', 413),
])
def test_upload_rejects_invalid_files_without_storage_calls(client, database, signup, monkeypatch, data, mime, status):
    _, product_id, memory = prepare(client, database, signup, monkeypatch)
    assert upload(client, product_id, data=data, mime=mime).status_code == status
    assert memory.objects == {}

def test_missing_config_and_storage_failure_preserve_old_image(client, database, signup, monkeypatch):
    _, product_id, memory = prepare(client, database, signup, monkeypatch)
    assert upload(client, product_id).status_code == 200
    memory.fail = True
    failed = upload(client, product_id, version=1)
    assert failed.status_code == 503 and 'SECRET' not in failed.text
    assert len(memory.objects) == 1
    assert client.get('/api/v1/products').json()['items'][0]['image_version'] == 1
    monkeypatch.setenv('FIREBASE_STORAGE_BUCKET', ''); get_settings.cache_clear()
    assert client.get('/api/v1/products').json()['image_upload_enabled'] is False
    assert upload(client, product_id, version=1).status_code == 503

def test_roles_tenant_isolation_and_session_required(client, database, signup, monkeypatch):
    identity, product_id, memory = prepare(client, database, signup, monkeypatch)
    assert upload(client, product_id).status_code == 200
    with database() as db:
        db.get(User, identity['user']['id']).role = 'seller'; db.commit()
    assert client.get(f'/api/v1/products/{product_id}/image').status_code == 200
    assert upload(client, product_id, version=1).status_code == 403
    client.post('/api/v1/auth/logout')
    assert client.get(f'/api/v1/products/{product_id}/image').status_code == 401
    assert client.post('/api/v1/auth/register', json={**signup,'email':'other-images@example.com'}).status_code == 201
    assert upload(client, product_id).status_code == 404
    assert client.get(f'/api/v1/products/{product_id}/image').status_code == 404
    assert len(memory.objects) == 1

def test_revocation_during_upload_cleans_staged_object(client, database, signup, monkeypatch):
    identity, product_id, memory = prepare(client, database, signup, monkeypatch)
    original = storage.put_image
    def revoked(*args):
        result = original(*args)
        with database() as db:
            db.get(User, identity['user']['id']).active = False; db.commit()
        return result
    monkeypatch.setattr(storage, 'put_image', revoked)
    assert upload(client, product_id).status_code == 403
    assert memory.objects == {} and len(memory.deleted) == 1
    with database() as db:
        assert db.get(Product, product_id).image_object is None

def test_concurrent_replacement_cannot_overwrite_newer_image(client, database, signup, monkeypatch):
    _, product_id, memory = prepare(client, database, signup, monkeypatch)
    original = storage.put_image
    def changed(*args):
        result = original(*args)
        with database() as db:
            db.get(Product, product_id).image_version += 1; db.commit()
        return result
    monkeypatch.setattr(storage, 'put_image', changed)
    assert upload(client, product_id).status_code == 409
    assert memory.objects == {} and len(memory.deleted) == 1

def test_encoder_pixel_limits_animation_and_metadata(monkeypatch):
    monkeypatch.setattr(encoder, 'MAX_PIXELS', 10)
    with pytest.raises(HTTPException) as error: encoder.prepare_image(png(), 'image/png')
    assert error.value.status_code == 422
    monkeypatch.setattr(encoder, 'MAX_PIXELS', 20_000_000)
    buffer = BytesIO()
    Image.new('RGB', (10, 10), 'red').save(buffer, format='WEBP', save_all=True, append_images=[Image.new('RGB', (10, 10), 'blue')], duration=100, loop=0)
    with pytest.raises(HTTPException): encoder.prepare_image(buffer.getvalue(), 'image/webp')

def test_storage_key_and_generation_are_restricted(monkeypatch):
    monkeypatch.setattr(storage, 'bucket', lambda: pytest.fail('Should not contact Firebase'))
    for key, generation in [('https://attacker.example/img.png', '1'), ('companies/other/products/secret/file.webp', '1'), (f'companies/c/products/p/{uuid4()}.webp', 'invalid')]:
        with pytest.raises(storage.StorageUnavailable): storage.read_image('c', 'p', key, generation)


def test_firebase_identity_file_is_server_only(monkeypatch):
    monkeypatch.setenv('GOOGLE_APPLICATION_CREDENTIALS', '/outside-repository/server-account.json')
    get_settings.cache_clear()
    identity, app, expected_bucket = object(), object(), object()
    calls = []
    def certificate(path):
        calls.append(path)
        return identity
    def initialize(credential, options, name):
        assert credential is identity and options == {'storageBucket': 'factory-test.firebasestorage.app'}
        assert name.startswith('product-images-')
        return app
    monkeypatch.setattr(storage.credentials, 'Certificate', certificate)
    monkeypatch.setattr(storage.firebase_admin, 'initialize_app', initialize)
    def get_bucket(**kwargs):
        assert kwargs == {'app': app}
        return expected_bucket
    monkeypatch.setattr(storage.storage, 'bucket', get_bucket)
    storage._bucket.cache_clear()
    try:
        assert storage._bucket('factory-test.firebasestorage.app') is expected_bucket
        assert calls == ['/outside-repository/server-account.json']
    finally:
        storage._bucket.cache_clear()
