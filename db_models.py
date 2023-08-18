from app import db


class Alert(db.Model):
    __tablename__ = 'alerts'

    ticker = db.Column(db.String(4), primary_key=True)
    userid = db.Column(db.Integer, primary_key=True)
    percentage = db.Column(db.Float, nullable=False)
    callback_url = db.Column(db.String(256), nullable=False)



