from datetime import datetime, timedelta
from flask_login import current_user
from flask_socketio import join_room, emit
from app.extensions import socketio, db
from app.models.ticket import Ticket
from app.models.message import Message

ADMIN_ROOM = 'admin_notifications'
WIDGET_TICKET_SUBJECT = 'Live Chat Support'

CLOSE_COMMAND = 'close conversation'
CLOSE_MANUAL_MESSAGE = (
    'This conversation was closed ("close conversation"). / '
    'Esta conversacion fue cerrada a peticion ("close conversation").'
)
TIMEOUT_MINUTES = 5
CHECK_INTERVAL_SECONDS = 30
CLOSE_TIMEOUT_MESSAGE = (
    "We closed this conversation because you didn't reply within 5 minutes. "
    "Start a new chat if you still need help. / "
    "Cerramos esta conversacion porque no respondiste en 5 minutos. "
    "Inicia un nuevo chat si aun necesitas ayuda."
)


def is_close_command(text):
    return (text or '').strip().lower() == CLOSE_COMMAND


@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated and current_user.is_admin:
        join_room(ADMIN_ROOM)


def _can_access_ticket(ticket):
    if not current_user.is_authenticated:
        return False
    return current_user.is_admin or ticket.user_id == current_user.id


@socketio.on('join_ticket')
def handle_join_ticket(data):
    ticket_id = (data or {}).get('ticket_id')
    ticket = Ticket.query.get(ticket_id) if ticket_id else None
    if not ticket or not _can_access_ticket(ticket):
        return
    join_room(f'ticket_{ticket.id}')


def _persist_and_broadcast(ticket, body, sender):
    msg = Message(ticket_id=ticket.id, sender_id=sender.id, body=body)
    db.session.add(msg)
    db.session.commit()

    payload = {
        'ticket_id': ticket.id,
        'sender_id': sender.id,
        'sender_name': sender.name,
        'body': msg.body,
        'timestamp': msg.timestamp.strftime('%H:%M'),
        'is_admin': sender.is_admin,
    }
    emit('new_message', payload, room=f'ticket_{ticket.id}')

    if not sender.is_admin:
        emit('admin_alert', {
            'kind': 'message',
            'ticket_id': ticket.id,
            'subject': ticket.subject,
            'preview': body[:80],
            'sender_name': sender.name,
        }, room=ADMIN_ROOM)

    return msg


def close_ticket_and_notify(ticket_id, reason):
    """Notifica el cierre de una conversacion (por comando o por timeout) y la elimina
    junto con todos sus mensajes (Ticket.messages tiene cascade='all, delete-orphan')."""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return
    room = f'ticket_{ticket.id}'
    socketio.emit('ticket_closed', {'ticket_id': ticket.id, 'reason': reason}, room=room)
    socketio.emit('admin_alert', {
        'kind': 'ticket_closed',
        'ticket_id': ticket.id,
        'subject': ticket.subject,
        'preview': reason,
    }, room=ADMIN_ROOM)
    db.session.delete(ticket)
    db.session.commit()


@socketio.on('send_message')
def handle_send_message(data):
    if not current_user.is_authenticated:
        return
    body = ((data or {}).get('body') or '').strip()
    ticket_id = (data or {}).get('ticket_id')
    if not body or not ticket_id:
        return

    ticket = Ticket.query.get(ticket_id)
    if not ticket or not _can_access_ticket(ticket):
        return

    if is_close_command(body):
        close_ticket_and_notify(ticket.id, CLOSE_MANUAL_MESSAGE)
        return

    _persist_and_broadcast(ticket, body, current_user)


@socketio.on('widget_message')
def handle_widget_message(data):
    """Mensajes enviados desde la burbuja de chat flotante (widget) del sitio."""
    if not current_user.is_authenticated:
        return
    body = ((data or {}).get('body') or '').strip()
    if not body:
        return

    existing_ticket = (
        Ticket.query.filter_by(user_id=current_user.id, subject=WIDGET_TICKET_SUBJECT)
        .filter(Ticket.status != 'Closed')
        .order_by(Ticket.created_at.desc())
        .first()
    )

    if is_close_command(body):
        if existing_ticket:
            close_ticket_and_notify(existing_ticket.id, CLOSE_MANUAL_MESSAGE)
        return

    ticket = existing_ticket
    if not ticket:
        ticket = Ticket(
            user_id=current_user.id,
            subject=WIDGET_TICKET_SUBJECT,
            description='Conversacion iniciada desde el chat en vivo del sitio.',
            status='Open',
        )
        db.session.add(ticket)
        db.session.commit()

    join_room(f'ticket_{ticket.id}')
    _persist_and_broadcast(ticket, body, current_user)
    emit('widget_ticket_ready', {'ticket_id': ticket.id})


def _check_stale_tickets():
    from app.models.user import User

    cutoff = datetime.utcnow() - timedelta(minutes=TIMEOUT_MINUTES)
    open_tickets = Ticket.query.filter(Ticket.status != 'Closed').all()
    for ticket in open_tickets:
        last_msg = (
            Message.query.filter_by(ticket_id=ticket.id)
            .order_by(Message.timestamp.desc())
            .first()
        )
        if not last_msg or not last_msg.timestamp:
            continue
        sender = User.query.get(last_msg.sender_id)
        # Solo se cierra por inactividad si quien espera respuesta es el cliente
        # (el ultimo mensaje lo mando un Admin y el cliente no contesto a tiempo).
        if not sender or not sender.is_admin:
            continue
        if last_msg.timestamp <= cutoff:
            close_ticket_and_notify(ticket.id, CLOSE_TIMEOUT_MESSAGE)


TICKET_RETENTION_DAYS = 30
PURGE_CHECK_INTERVAL_SECONDS = 3600  # revisa la purga mensual una vez por hora


def _purge_old_tickets():
    """Borra chats (tickets + sus mensajes) con mas de 30 dias de antiguedad.
    Los pedidos (Order) y su numero de orden viven en su propia tabla, sin relacion
    con Ticket/Message, asi que NO se tocan: el cliente conserva su compra y numero
    de pedido en su panel aunque el historial de chat de ese pedido ya se haya borrado."""
    cutoff = datetime.utcnow() - timedelta(days=TICKET_RETENTION_DAYS)
    old_tickets = Ticket.query.filter(Ticket.created_at <= cutoff).all()
    for ticket in old_tickets:
        db.session.delete(ticket)
    if old_tickets:
        db.session.commit()


def start_stale_ticket_watcher(app):
    """Hilo en segundo plano que:
    1) cierra y elimina tickets abandonados por el cliente 5 minutos despues de la
       ultima respuesta del admin, y
    2) una vez por hora purga los chats (tickets + mensajes) con mas de 30 dias."""
    def _loop():
        last_purge = datetime.utcnow()
        while True:
            socketio.sleep(CHECK_INTERVAL_SECONDS)
            with app.app_context():
                try:
                    _check_stale_tickets()
                except Exception as e:
                    app.logger.error(f"Error revisando tickets inactivos: {e}")

                if (datetime.utcnow() - last_purge).total_seconds() >= PURGE_CHECK_INTERVAL_SECONDS:
                    last_purge = datetime.utcnow()
                    try:
                        _purge_old_tickets()
                    except Exception as e:
                        app.logger.error(f"Error purgando chats antiguos: {e}")

    socketio.start_background_task(_loop)
