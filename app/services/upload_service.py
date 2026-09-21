"""Manejo de adjuntos enviados en el chat de tickets (imagenes y documentos).

Los archivos se guardan en app/static/uploads/chat/<ticket_id>/ con un nombre
unico y seguro. NOTA IMPORTANTE: en Railway el sistema de archivos es efimero,
es decir que estos adjuntos pueden perderse si el servicio se reinicia o se
redepliega. Para conservarlos de forma permanente en produccion, lo ideal a
futuro es moverlos a un almacenamiento externo (S3, Cloudinary, un volumen
persistente de Railway, etc). Mientras tanto, este almacenamiento local es
funcional y suficiente para operar.
"""
import os
import uuid
from werkzeug.utils import secure_filename

MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024  # 5 MB

ALLOWED_EXTENSIONS = {
    # Imagenes
    'png', 'jpg', 'jpeg', 'gif', 'webp',
    # Documentos
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv', 'zip',
}

ALLOWED_MIME_PREFIXES = ('image/',)
ALLOWED_MIME_EXACT = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain',
    'text/csv',
    'application/zip',
    'application/x-zip-compressed',
    'application/octet-stream',  # algunos navegadores no detectan el tipo real
}


class AttachmentError(ValueError):
    """Error de validacion de adjunto pensado para mostrarse directo al usuario."""
    pass


def _get_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


def _upload_root(app, ticket_id):
    root = os.path.join(app.static_folder, 'uploads', 'chat', str(ticket_id))
    os.makedirs(root, exist_ok=True)
    return root


def save_chat_attachment(app, file_storage, ticket_id):
    """Valida y guarda un adjunto de chat. Devuelve un dict con los metadatos
    a guardar en Message, o None si no se envio ningun archivo.
    Lanza AttachmentError si el archivo no es valido (tamaño o tipo)."""
    if not file_storage or not file_storage.filename:
        return None

    original_name = file_storage.filename
    extension = _get_extension(original_name)
    if extension not in ALLOWED_EXTENSIONS:
        raise AttachmentError(
            f'Tipo de archivo no permitido (.{extension or "?"}). '
            'Formatos permitidos: imágenes, PDF, Word, Excel, PowerPoint, TXT, CSV o ZIP.'
        )

    mimetype = (file_storage.mimetype or '').lower()
    if mimetype and not (
        mimetype in ALLOWED_MIME_EXACT or mimetype.startswith(ALLOWED_MIME_PREFIXES)
    ):
        raise AttachmentError('Tipo de archivo no permitido.')

    # Medir tamaño real sin cargar todo en memoria de golpe innecesariamente
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)

    if size <= 0:
        return None
    if size > MAX_ATTACHMENT_SIZE:
        raise AttachmentError('El archivo supera el límite de 5 MB.')

    safe_original = secure_filename(original_name) or 'archivo'
    stored_name = f"{uuid.uuid4().hex}_{safe_original}"

    dest_dir = _upload_root(app, ticket_id)
    file_storage.save(os.path.join(dest_dir, stored_name))

    return {
        'attachment_filename': stored_name,
        'attachment_original_name': original_name[:255],
        'attachment_mime': mimetype or 'application/octet-stream',
        'attachment_size': size,
    }
