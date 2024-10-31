# models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Campaign(db.Model):
    __tablename__ = 'campaigns'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    csv_file_path = db.Column(db.String, nullable=False)  # Ensure this field is defined
    subject = db.Column(db.String, nullable=False)
    body = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<Campaign {self.name}>'

class EmailLog(db.Model):
    __tablename__ = 'email_logs'
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    campaign = db.relationship('Campaign', backref=db.backref('email_logs', lazy=True))
