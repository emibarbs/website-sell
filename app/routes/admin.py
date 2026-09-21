from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import current_user
from app.models.user import User
from app.models.order import Order
from app.models.ticket import Ticket
from app.models.message import Message
from app.models.setting import Setting
from app.extensions import db, socketio
from app.services.stripe_service import sync_plan_price
from app.services.upload_service import save_chat_attachment, AttachmentError
from app.sockets import is_close_command, close_ticket_and_notify, CLOSE_MANUAL_MESSAGE

bp = Blueprint('admin', __name__, url_prefix='/admin')

PLAN_LABELS = {'plan1': 'Plan 1', 'plan2': 'Plan 2'}


@bp.before_request
def require_admin():
    """Cierra el panel de administración a cualquiera que no tenga rol Admin en la base de datos."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=request.path))
    if not current_user.is_admin:
        flash('Acceso restringido: esta sección es solo para administradores.')
        return redirect(url_for('client.dashboard'))


@bp.route('/dashboard')
def dashboard():
    total_revenue = db.session.query(db.func.coalesce(db.func.sum(Order.amount), 0.0)).scalar()
    stats = {
        'total_revenue': round(total_revenue or 0, 2),
        'user_count': User.query.count(),
        'order_count': Order.query.count(),
        'open_tickets': Ticket.query.filter(Ticket.status != 'Closed').count(),
    }
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    recent_tickets = Ticket.query.order_by(Ticket.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html', stats=stats, recent_orders=recent_orders, recent_tickets=recent_tickets)


@bp.route('/tickets')
def tickets():
    all_tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
    return render_template('admin/tickets.html', tickets=all_tickets)


@bp.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
def view_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    if request.method == 'POST':
        new_status = request.form.get('status')
        body = (request.form.get('body') or '').strip()

        if body and is_close_command(body):
            close_ticket_and_notify(ticket.id, CLOSE_MANUAL_MESSAGE)
            flash('Conversación cerrada y eliminada.')
            return redirect(url_for('admin.tickets'))

        attachment_data = None
        try:
            attachment_data = save_chat_attachment(
                current_app, request.files.get('attachment'), ticket.id
            )
        except AttachmentError as e:
            flash(str(e), 'danger')
            return redirect(url_for('admin.view_ticket', ticket_id=ticket.id))

        if body or attachment_data:
            msg = Message(ticket_id=ticket.id, sender_id=current_user.id, body=body or None)
            if attachment_data:
                msg.attachment_filename = attachment_data['attachment_filename']
                msg.attachment_original_name = attachment_data['attachment_original_name']
                msg.attachment_mime = attachment_data['attachment_mime']
                msg.attachment_size = attachment_data['attachment_size']
            db.session.add(msg)
            db.session.flush()
            socketio.emit('new_message', {
                'ticket_id': ticket.id,
                'sender_id': current_user.id,
                'sender_name': current_user.name,
                'body': msg.body or '',
                'timestamp': msg.timestamp.strftime('%H:%M') if msg.timestamp else '',
                'is_admin': True,
                'attachment_url': url_for('static', filename=f'uploads/chat/{ticket.id}/{msg.attachment_filename}') if msg.has_attachment else None,
                'attachment_name': msg.attachment_original_name,
                'attachment_is_image': msg.attachment_is_image,
            }, room=f'ticket_{ticket.id}')

        if new_status and new_status != ticket.status:
            ticket.status = new_status

        db.session.commit()
        flash('Respuesta enviada.')
        return redirect(url_for('admin.view_ticket', ticket_id=ticket.id))

    messages = Message.query.filter_by(ticket_id=ticket.id).order_by(Message.timestamp).all()
    return render_template('admin/chat.html', ticket=ticket, messages=messages)


@bp.route('/ticket/close/<int:ticket_id>', methods=['POST'])
def close_ticket(ticket_id):
    """Cierra la conversación y la elimina (junto con sus mensajes) de forma
    definitiva. Antes este endpoint solo marcaba el ticket como 'Closed' sin
    borrarlo, dejando conversaciones "cerradas" que nunca se eliminaban.
    Ahora reutiliza la misma lógica que el comando de texto "close conversation",
    para que cerrar desde el botón del panel de administración funcione
    siempre y de forma consistente."""
    ticket = Ticket.query.get_or_404(ticket_id)
    close_ticket_and_notify(ticket.id, CLOSE_MANUAL_MESSAGE)
    flash('Conversación cerrada y eliminada correctamente.')
    return redirect(url_for('admin.tickets'))


@bp.route('/orders')
def orders():
    all_orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=all_orders)


@bp.route('/customers')
def customers():
    all_customers = User.query.filter_by(role='Client').order_by(User.created_at.desc()).all()
    return render_template('admin/customers.html', customers=all_customers)


@bp.route('/customer/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    user_to_delete = User.query.get_or_404(user_id)
    
    # Evitar que el administrador se elimine a sí mismo accidentalmente
    if user_to_delete.id == current_user.id:
        flash('No puedes eliminar tu propia cuenta de administrador.', 'danger')
        return redirect(url_for('admin.customers'))
        
    db.session.delete(user_to_delete)
    db.session.commit()
    
    flash('El usuario ha sido eliminado correctamente.', 'success')
    return redirect(url_for('admin.customers'))


@bp.route('/pricing', methods=['GET', 'POST'])
def pricing_settings():
    if request.method == 'POST':
        for plan_key, label in PLAN_LABELS.items():
            raw_price = request.form.get(f'{plan_key}_price')
            if not raw_price:
                continue
            try:
                new_price = float(raw_price)
            except ValueError:
                flash(f'Precio inválido para {label}.')
                continue

            try:
                sync_plan_price(plan_key, label, new_price)
                flash(f'{label} actualizado a ${new_price:.2f} USD y sincronizado con Stripe.')
            except Exception as e:
                flash(f'No se pudo sincronizar {label} con Stripe: {e}')

        return redirect(url_for('admin.pricing_settings'))

    p1 = Setting.query.filter_by(key_name='plan1_price').first()
    p2 = Setting.query.filter_by(key_name='plan2_price').first()
    return render_template(
        'admin/pricing.html',
        plan1_price=p1.key_value if p1 else '297',
        plan2_price=p2.key_value if p2 else '597',
    )


# Compatibilidad retro: formulario legado de un solo plan por request (usado desde el dashboard)
@bp.route('/update-price', methods=['POST'])
def update_price():
    plan_name = request.form.get('plan_name')
    new_price = request.form.get('new_price')
    plan_key = 'plan1' if plan_name == PLAN_LABELS['plan1'] else 'plan2'
    try:
        sync_plan_price(plan_key, plan_name, float(new_price))
        flash(f'Successfully updated {plan_name} to ${new_price} USD on Stripe.')
    except Exception as e:
        flash(f'Failed to sync {plan_name} with Stripe: {e}')
    return redirect(url_for('admin.pricing_settings'))
