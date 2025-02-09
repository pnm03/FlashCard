# models.py
from your_app import db

class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    english = db.Column(db.String(200))
    description = db.Column(db.String(500))
    ipa = db.Column(db.String(100))
    image = db.Column(db.String(300))
    audio_auto = db.Column(db.String(300))
    audio_user = db.Column(db.String(300))
    mistake_count = db.Column(db.Integer, default=0)
    # Các trường khác nếu có

    def to_dict(self):
        return {
            "english": self.english,
            "description": self.description,
            "definitions": self.get_definitions(),  # Giả sử bạn có phương thức xử lý cho definitions
            "ipa": self.ipa,
            "image": self.image,
            "audio_auto": self.audio_auto,
            "audio_user": self.audio_user,
            "mistake_count": self.mistake_count,
        }

class Subdeck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    # Giả sử một subdeck có nhiều card
    cards = db.relationship('Card', backref='subdeck', lazy=True)

    def to_dict(self):
        return {
            "name": self.name,
            "cards": [card.to_dict() for card in self.cards]
        }

class BigDeck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    # Giả sử một big deck có nhiều subdeck
    subdecks = db.relationship('Subdeck', backref='big_deck', lazy=True)

    def to_dict(self):
        return {
            "name": self.name,
            "subdecks": {subdeck.name: subdeck.to_dict() for subdeck in self.subdecks}
        }
