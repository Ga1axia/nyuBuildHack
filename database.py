from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    analyses = db.relationship('Analysis', backref='user', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))
    subcategory = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Analysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    savings_level = db.Column(db.String(20), nullable=False)
    total_monthly_savings = db.Column(db.Float)
    analysis_data = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all() 