from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Group(db.Model):
    __tablename__ = 'group'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    members = db.relationship('Member', backref='group', lazy=True)
    pin = db.Column(db.String(10), unique=True, nullable=False)
    created_time = db.Column(db.DateTime, default=datetime.utcnow)


class Member(db.Model):
    __tablename__ = 'member'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    pin = db.Column(db.String(10), nullable=False)


# טבלת קשר (מזהה משתתף ומזהה קבוצה)
user_group = db.Table(
    "user_group",
    db.Column("member_id", db.Integer, db.ForeignKey("member.id"), primary_key=True),
    db.Column("group_id", db.Integer, db.ForeignKey("group.id"), primary_key=True),
)