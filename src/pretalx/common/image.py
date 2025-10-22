# SPDX-FileCopyrightText: 2024-present Tobias Kunze
# SPDX-License-Identifier: AGPL-3.0-only WITH LicenseRef-Pretalx-AGPL-3.0-Terms

from contextlib import suppress
from functools import partial
from io import BytesIO
from pathlib import Path

from csp.decorators import csp_update
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps
from PIL.Image import MAX_IMAGE_PIXELS, DecompressionBombError, Resampling

THUMBNAIL_SIZES = {
    "tiny": (64, 64),
    "default": (460, 460),
}
FORMAT_MAP = {
    ".jpg": "JPEG",
    ".png": "PNG",
}
MAX_DIMENSIONS = (
    settings.IMAGE_DEFAULT_MAX_WIDTH,
    settings.IMAGE_DEFAULT_MAX_HEIGHT,
)

gravatar_csp = partial(
    csp_update,
    {
        "img-src": "https://www.gravatar.com",
        "connect-src": ("'self'", "https://www.gravatar.com"),
    },
)


def validate_image(f):
    if f is None:
        return

    if hasattr(f, "temporary_file_path"):
        file = f.temporary_file_path()
    elif hasattr(f, "read"):
        if hasattr(f, "seek") and callable(f.seek):
            f.seek(0)
        file = BytesIO(f.read())
    else:
        file = BytesIO(f["content"])

    try:
        try:
            image = Image.open(file, formats=settings.PILLOW_FORMATS_QUESTIONS_IMAGE)
            # verify() must be called immediately after the constructor.
            image.verify()
        except DecompressionBombError:
            raise ValidationError(
                _(
                    "The file you uploaded has a very large number of pixels, please upload a picture with smaller dimensions."
                )
            )

        # load() is a potential DoS vector (see Django bug #18520), so we verify the size first
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise ValidationError(
                _(
                    "The file you uploaded has a very large number of pixels, please upload a picture with smaller dimensions."
                )
            )
    except Exception as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(
            _(
                "Upload a valid image. The file you uploaded was either not an image or a corrupted image."
            )
        ) from exc
    if hasattr(f, "seek") and callable(f.seek):
        f.seek(0)


def load_img(image):
    extension = ".jpg"
    try:
        img = Image.open(image)
    except Exception:
        return None, None
    if img.mode.lower() in ("rgba", "la", "pa"):
        extension = ".png"
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img, extension


def process_image(*, image, generate_thumbnail=False):
    """
    This function receives an image that has been uploaded, and processes it
    by reducing its file size and stripping its metadata.
    Image must be an ImageFieldFile, e.g. user.avatar.
    """
    img, extension = load_img(image)
    if not img:
        return
    img_without_exif = Image.new(img.mode, img.size)
    img_without_exif.putdata(img.getdata())
    img_without_exif = ImageOps.exif_transpose(img_without_exif)
    img_without_exif.thumbnail(MAX_DIMENSIONS, resample=Resampling.LANCZOS)

    # Overwrite the original image with the processed one
    path = Path(image.path)
    fmt = FORMAT_MAP[extension]
    save_path = path.with_suffix(extension)
    img_byte_array = BytesIO()
    img_without_exif.save(
        img_byte_array,
        quality="web_high" if extension == ".jpg" else 95,
        format=fmt,
    )
    image_field = getattr(image.instance, image.field.name)
    image_field.save(save_path, ContentFile(img_byte_array.getvalue()))
    image_field.instance.save()
    if save_path != path:
        path.unlink()

    if generate_thumbnail:
        for size in THUMBNAIL_SIZES:
            create_thumbnail(image, size, fmt=fmt, extension=extension)


def get_thumbnail_field_name(image, size):
    thumbnail_field_name = f"{image.field.name}_thumbnail"
    if size != "default":
        thumbnail_field_name += f"_{size}"
    return thumbnail_field_name


def create_thumbnail(image, size, extension=None, fmt=None):
    if size not in THUMBNAIL_SIZES:
        return
    thumbnail_field_name = get_thumbnail_field_name(image, size)
    if not image.instance._meta.get_field(thumbnail_field_name):
        return

    img = None
    with suppress(Exception):
        img, ext = load_img(image)
    if not img:
        return
    img.thumbnail(THUMBNAIL_SIZES[size], resample=Resampling.LANCZOS)
    thumbnail_field = getattr(image.instance, thumbnail_field_name)
    extension = extension or ext
    thumbnail_name = Path(image.name).stem + f"_thumbnail_{size}" + extension
    # Write the image to a BytesIO object
    img_byte_array = BytesIO()
    img.save(img_byte_array, format=fmt or img.format)
    thumbnail_field.save(
        thumbnail_name,
        ContentFile(img_byte_array.getvalue()),
    )
    return thumbnail_field


def get_thumbnail(image, size):
    thumbnail_field_name = get_thumbnail_field_name(image, size)
    if not (image.instance._meta.get_field(thumbnail_field_name)):
        return image

    thumbnail_field = getattr(image.instance, thumbnail_field_name)
    if not thumbnail_field or not thumbnail_field.storage.exists(thumbnail_field.path):
        return create_thumbnail(image, size)
    return thumbnail_field
