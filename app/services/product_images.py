"""Decode, bound, orient and re-encode images; never trust extensions or MIME alone."""
from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException
from app.integrations.firebase.product_images import MAX_BYTES

FORMATS = {'image/jpeg': 'JPEG', 'image/png': 'PNG', 'image/webp': 'WEBP'}
MAX_PIXELS = 20_000_000

def prepare_image(contents, content_type):
    if content_type not in FORMATS:
        raise HTTPException(415, 'Envie uma imagem JPG, PNG ou WebP.')
    if not contents or len(contents) > MAX_BYTES:
        raise HTTPException(413, 'Envie uma imagem de até 5 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(contents)) as source:
                if source.format != FORMATS[content_type] or source.width * source.height > MAX_PIXELS or max(source.size) > 10000 or getattr(source, 'n_frames', 1) != 1:
                    raise ValueError()
                source.verify()
            with Image.open(BytesIO(contents)) as source:
                source.load()
                image = ImageOps.exif_transpose(source).convert('RGBA')
                image.thumbnail((1600, 1600))
                # New pixels remove EXIF/GPS/ICC/XMP and any original appended data.
                clean = Image.new('RGBA', image.size)
                clean.paste(image)
                output = BytesIO()
                clean.save(output, format='WEBP', quality=85)
                result = output.getvalue()
                if len(result) > MAX_BYTES:
                    raise ValueError()
                return result
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, 'Imagem inválida. Use uma imagem estática de até 20 megapixels em JPG, PNG ou WebP.') from None
