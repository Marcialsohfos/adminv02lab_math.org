from app import db
from datetime import datetime

class Activite(db.Model):
    __tablename__ = 'activites'
    
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    contenu = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    auteur = db.Column(db.String(100))
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_modification = db.Column(db.DateTime, onupdate=datetime.utcnow)
    est_publie = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'titre': self.titre,
            'description': self.description,
            'contenu': self.contenu,
            'image_url': self.image_url,
            'auteur': self.auteur,
            'date_creation': self.date_creation.isoformat() if self.date_creation else None,
            'est_publie': self.est_publie
        }

class Realisation(db.Model):
    __tablename__ = 'realisations'
    
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    categorie = db.Column(db.String(100))
    date_realisation = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

class Annonce(db.Model):
    __tablename__ = 'annonces'
    
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    contenu = db.Column(db.Text)
    type_annonce = db.Column(db.String(50))  # 'urgence', 'info', 'evenement'
    date_debut = db.Column(db.DateTime)
    date_fin = db.Column(db.DateTime)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    est_active = db.Column(db.Boolean, default=True)

class Offre(db.Model):
    __tablename__ = 'offres'
    
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type_offre = db.Column(db.String(50))  # 'emploi', 'stage', 'formation'
    lieu = db.Column(db.String(100))
    date_limite = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    est_active = db.Column(db.Boolean, default=True)

# Créer les tables
def create_tables():
    db.create_all()