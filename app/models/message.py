from app.extensions import db
from datetime import datetime

class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Adjunto opcional (imagen o documento) enviado en el chat del ticket.
    attachment_filename = db.Column(db.String(255), nullable=True)       # nombre seguro guardado en disco
    attachment_original_name = db.Column(db.String(255), nullable=True)  # nombre original mostrado al usuario
    attachment_mime = db.Column(db.String(100), nullable=True)
    attachment_size = db.Column(db.Integer, nullable=True)               # bytes

    ticket = db.relationship('Ticket', back_populates='messages')
    sender = db.relationship('User')

    @property
    def has_attachment(self):
        return bool(self.attachment_filename)

    @property
    def attachment_is_image(self):
        return bool(self.attachment_mime and self.attachment_mime.startswith('image/'))

    def __repr__(self):
        return f'<Message ticket={self.ticket_id} sender={self.sender_id}>'
