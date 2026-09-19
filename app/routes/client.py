from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from app.models.order import Order
from app.models.ticket import Ticket
from app.models.message import Message
from app.extensions import db, socketio
from app.sockets import is_close_command, close_ticket_and_notify, CLOSE_MANUAL_MESSAGE

bp = Blueprint('client', __name__, url_prefix='/client')

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'Admin':
        return redirect(url_for('admin.dashboard'))

    orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
    tickets = Ticket.query.filter_by(user_id=current_user.id).order_by(Ticket.created_at.desc()).all()
    return render_template('client/dashboard.html', orders=orders, tickets=tickets)

@bp.route('/tickets', methods=['GET'])
@login_required
def tickets():
    my_tickets = Ticket.query.filter_by(user_id=current_user.id).order_by(Ticket.created_at.desc()).all()
    return render_template('client/tickets.html', tickets=my_tickets)

@bp.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
def view_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.user_id != current_user.id:
        abort(404)

    if request.method == 'POST':
        body = (request.form.get('body') or '').strip()

        if body and is_close_command(body):
            close_ticket_and_notify(ticket.id, CLOSE_MANUAL_MESSAGE)
            flash('Conversación cerrada.')
            return redirect(url_for('client.tickets'))

        if body:
            msg = Message(ticket_id=ticket.id, sender_id=current_user.id, body=body)
            db.session.add(msg)
            db.session.commit()
            socketio.emit('new_message', {
                'ticket_id': ticket.id,
                'sender_id': current_user.id,
                'sender_name': current_user.name,
                'body': body,
                'timestamp': msg.timestamp.strftime('%H:%M') if msg.timestamp else '',
                'is_admin': False,
            }, room=f'ticket_{ticket.id}')
            socketio.emit('admin_alert', {
                'kind': 'message',
                'ticket_id': ticket.id,
                'subject': ticket.subject,
                'preview': body[:80],
                'sender_name': current_user.name,
            }, room='admin_notifications')
        return redirect(url_for('client.view_ticket', ticket_id=ticket.id))

    messages = Message.query.filter_by(ticket_id=ticket.id).order_by(Message.timestamp).all()
    return render_template('client/chat.html', ticket=ticket, messages=messages)

@bp.route('/order/new', methods=['POST'])
@login_required
def create_order():
    plan_name = request.form.get('plan_name')
    amount = request.form.get('amount')

    new_order = Order(
        customer_id=current_user.id,
        plan_name=plan_name,
        amount=float(amount) if amount else 99.0,
        status='Active'
    )
    db.session.add(new_order)
    db.session.commit()
    flash('Order created successfully! Check your dashboard.')
    return redirect(url_for('client.dashboard'))

@bp.route('/ticket/new', methods=['POST'])
@login_required
def create_ticket():
    subject = request.form.get('subject')
    description = request.form.get('description')

    new_ticket = Ticket(
        user_id=current_user.id,
        subject=subject,
        description=description,
        status='Open'
    )
    db.session.add(new_ticket)
    db.session.commit()
    flash('Support ticket submitted successfully.')
    return redirect(url_for('client.tickets'))
