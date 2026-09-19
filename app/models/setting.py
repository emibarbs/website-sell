from app.extensions import db

class Setting(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key_name = db.Column(db.String(50), unique=True, nullable=False)
    key_value = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<Setting {self.key_name}={self.key_value}>'
