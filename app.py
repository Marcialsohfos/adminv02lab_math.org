from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import os
from functools import wraps
import requests
import json

# Création de l'application Flask
app = Flask(__name__)
CORS(app)  # Autorise les requêtes cross-origin

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '32015@1a')

# Correction impérative pour PostgreSQL sur Render
database_url = os.environ.get('DATABASE_URL', 'sqlite:///labmath_db.sqlite')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Initialisation de la base de données
db = SQLAlchemy(app)

# Configuration pour l'API du site principal
SITE_URL = os.environ.get('SITE_URL', 'https://labmath-scsmaubmar-org.onrender.com')
API_KEY = os.environ.get('API_KEY', 'votre_api_key_secrete')

# --- DÉCORATEUR SÉCURITÉ ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- MODÈLES ---
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
    sync_id = db.Column(db.String(100))  # ID de synchronisation sur le site principal

class Realisation(db.Model):
    __tablename__ = 'realisations'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    categorie = db.Column(db.String(100))
    date_realisation = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    sync_id = db.Column(db.String(100))

class Annonce(db.Model):
    __tablename__ = 'annonces'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    contenu = db.Column(db.Text)
    type_annonce = db.Column(db.String(50))
    date_debut = db.Column(db.DateTime)
    date_fin = db.Column(db.DateTime)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    est_active = db.Column(db.Boolean, default=True)
    sync_id = db.Column(db.String(100))

class Offre(db.Model):
    __tablename__ = 'offres'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type_offre = db.Column(db.String(50))
    lieu = db.Column(db.String(100))
    date_limite = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    est_active = db.Column(db.Boolean, default=True)
    sync_id = db.Column(db.String(100))

# --- FONCTIONS DE SYNCHRONISATION ---

def sync_activite(activite):
    """Synchronise une activité avec le site principal"""
    try:
        headers = {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json'
        }
        
        # Préparer les données
        data = {
            'id': activite.id,
            'titre': activite.titre,
            'description': activite.description,
            'contenu': activite.contenu,
            'image_url': activite.image_url or '',
            'auteur': activite.auteur or 'Admin',
            'date_creation': activite.date_creation.isoformat() if activite.date_creation else datetime.utcnow().isoformat(),
            'est_publie': activite.est_publie
        }
        
        # URL de l'API du site principal
        api_url = f"{SITE_URL}/api/activites"
        if activite.sync_id:
            api_url = f"{api_url}/{activite.sync_id}"
        
        # Envoyer la requête
        response = requests.post(
            api_url,
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            if result.get('success') and result.get('id'):
                activite.sync_id = str(result['id'])
                db.session.commit()
                return True, "Activité synchronisée avec succès"
            else:
                return False, f"Erreur de synchronisation: {result.get('message', 'Erreur inconnue')}"
        else:
            return False, f"Erreur HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"Erreur de connexion: {str(e)}"

def sync_realisation(realisation):
    """Synchronise une réalisation avec le site principal"""
    try:
        headers = {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json'
        }
        
        data = {
            'id': realisation.id,
            'titre': realisation.titre,
            'description': realisation.description,
            'image_url': realisation.image_url or '',
            'categorie': realisation.categorie or '',
            'date_realisation': realisation.date_realisation.isoformat() if realisation.date_realisation else None,
            'date_creation': realisation.date_creation.isoformat() if realisation.date_creation else datetime.utcnow().isoformat()
        }
        
        api_url = f"{SITE_URL}/api/realisations"
        if realisation.sync_id:
            api_url = f"{api_url}/{realisation.sync_id}"
        
        response = requests.post(
            api_url,
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            if result.get('success') and result.get('id'):
                realisation.sync_id = str(result['id'])
                db.session.commit()
                return True, "Réalisation synchronisée avec succès"
            else:
                return False, f"Erreur de synchronisation: {result.get('message', 'Erreur inconnue')}"
        else:
            return False, f"Erreur HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"Erreur de connexion: {str(e)}"

def sync_annonce(annonce):
    """Synchronise une annonce avec le site principal"""
    try:
        headers = {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json'
        }
        
        data = {
            'id': annonce.id,
            'titre': annonce.titre,
            'contenu': annonce.contenu,
            'type_annonce': annonce.type_annonce or 'info',
            'date_debut': annonce.date_debut.isoformat() if annonce.date_debut else None,
            'date_fin': annonce.date_fin.isoformat() if annonce.date_fin else None,
            'date_creation': annonce.date_creation.isoformat() if annonce.date_creation else datetime.utcnow().isoformat(),
            'est_active': annonce.est_active
        }
        
        api_url = f"{SITE_URL}/api/annonces"
        if annonce.sync_id:
            api_url = f"{api_url}/{annonce.sync_id}"
        
        response = requests.post(
            api_url,
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            if result.get('success') and result.get('id'):
                annonce.sync_id = str(result['id'])
                db.session.commit()
                return True, "Annonce synchronisée avec succès"
            else:
                return False, f"Erreur de synchronisation: {result.get('message', 'Erreur inconnue')}"
        else:
            return False, f"Erreur HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"Erreur de connexion: {str(e)}"

def sync_offre(offre):
    """Synchronise une offre avec le site principal"""
    try:
        headers = {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json'
        }
        
        data = {
            'id': offre.id,
            'titre': offre.titre,
            'description': offre.description,
            'type_offre': offre.type_offre or 'autre',
            'lieu': offre.lieu or '',
            'date_limite': offre.date_limite.isoformat() if offre.date_limite else None,
            'date_creation': offre.date_creation.isoformat() if offre.date_creation else datetime.utcnow().isoformat(),
            'est_active': offre.est_active
        }
        
        api_url = f"{SITE_URL}/api/offres"
        if offre.sync_id:
            api_url = f"{api_url}/{offre.sync_id}"
        
        response = requests.post(
            api_url,
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            if result.get('success') and result.get('id'):
                offre.sync_id = str(result['id'])
                db.session.commit()
                return True, "Offre synchronisée avec succès"
            else:
                return False, f"Erreur de synchronisation: {result.get('message', 'Erreur inconnue')}"
        else:
            return False, f"Erreur HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"Erreur de connexion: {str(e)}"

def delete_from_site(model, sync_id):
    """Supprime un élément du site principal"""
    try:
        if not sync_id:
            return True, "Aucun ID de synchronisation"
            
        headers = {
            'X-API-Key': API_KEY
        }
        
        # Déterminer l'endpoint en fonction du modèle
        if model == 'activite':
            endpoint = 'activites'
        elif model == 'realisation':
            endpoint = 'realisations'
        elif model == 'annonce':
            endpoint = 'annonces'
        elif model == 'offre':
            endpoint = 'offres'
        else:
            return False, "Modèle inconnu"
        
        api_url = f"{SITE_URL}/api/{endpoint}/{sync_id}"
        
        response = requests.delete(
            api_url,
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 204]:
            return True, "Élément supprimé du site principal"
        else:
            return False, f"Erreur HTTP {response.status_code} lors de la suppression"
            
    except Exception as e:
        return False, f"Erreur de connexion: {str(e)}"

# --- ROUTES AUTHENTIFICATION ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
        
        if username == admin_user and password == admin_pass:
            session['user_id'] = 1
            session['username'] = username
            flash('Connexion réussie!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Identifiants incorrects', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Vous avez été déconnecté', 'info')
    return redirect(url_for('login'))

# --- ROUTES DASHBOARD ---

@app.route('/dashboard')
@login_required
def dashboard():
    stats = {
        'activities_count': Activite.query.count(),
        'realisations_count': Realisation.query.count(),
        'annonces_count': Annonce.query.count(),
        'offres_count': Offre.query.count(),
        'activities_published': Activite.query.filter_by(est_publie=True).count(),
        'annonces_active': Annonce.query.filter_by(est_active=True).count(),
        'offres_active': Offre.query.filter_by(est_active=True).count()
    }
    
    # Vérification de la connexion au site principal
    try:
        response = requests.get(f"{SITE_URL}/api/health", timeout=5)
        stats['site_connected'] = response.status_code == 200
    except:
        stats['site_connected'] = False
    
    return render_template('dashboard.html', 
                          stats=stats, 
                          now=datetime.utcnow(),
                          site_url=SITE_URL)

# --- ROUTES ACTIVITÉS ---

@app.route('/activites')
@login_required
def activites():
    activites_list = Activite.query.order_by(Activite.date_creation.desc()).all()
    return render_template('activites.html', activites=activites_list)

@app.route('/activite/nouveau', methods=['GET', 'POST'])
@login_required
def nouvel_activite():
    if request.method == 'POST':
        try:
            est_publie = request.form.get('est_publie') == 'true'
            
            nouvelle = Activite(
                titre=request.form.get('titre'),
                description=request.form.get('description'),
                contenu=request.form.get('contenu'),
                image_url=request.form.get('image_url'),
                auteur=session.get('username', 'Admin'),
                est_publie=est_publie
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            # Synchroniser avec le site principal si publié
            if est_publie:
                success, message = sync_activite(nouvelle)
                if success:
                    flash(f'Activité créée et synchronisée avec le site!', 'success')
                else:
                    flash(f'Activité créée mais erreur de synchronisation: {message}', 'warning')
            else:
                flash('Activité créée (non publiée)!', 'success')
                
            return redirect(url_for('activites'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création: {str(e)}', 'danger')
    
    return render_template('edit_activite.html', action='nouveau', activite=None)

@app.route('/activite/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_activite(id):
    activite = Activite.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            ancien_etat = activite.est_publie
            activite.titre = request.form.get('titre')
            activite.description = request.form.get('description')
            activite.contenu = request.form.get('contenu')
            activite.image_url = request.form.get('image_url')
            activite.est_publie = request.form.get('est_publie') == 'true'
            activite.date_modification = datetime.utcnow()
            
            db.session.commit()
            
            # Synchroniser avec le site principal
            if activite.est_publie:
                success, message = sync_activite(activite)
                if success:
                    flash(f'Activité mise à jour et synchronisée!', 'success')
                else:
                    flash(f'Activité mise à jour mais erreur de synchronisation: {message}', 'warning')
            elif ancien_etat and not activite.est_publie and activite.sync_id:
                # Si on dépublie, supprimer du site
                success, message = delete_from_site('activite', activite.sync_id)
                if success:
                    activite.sync_id = None
                    db.session.commit()
                    flash('Activité dépublée et retirée du site', 'info')
                else:
                    flash(f'Activité dépublée mais erreur de retrait du site: {message}', 'warning')
            else:
                flash('Activité mise à jour (non publiée)!', 'success')
                
            return redirect(url_for('activites'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return render_template('edit_activite.html', action='modifier', activite=activite)

@app.route('/activite/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_activite(id):
    activite = Activite.query.get_or_404(id)
    try:
        # Supprimer du site principal d'abord
        if activite.sync_id:
            delete_from_site('activite', activite.sync_id)
        
        # Supprimer de la base locale
        db.session.delete(activite)
        db.session.commit()
        flash('Activité supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('activites'))

@app.route('/activite/<int:id>/sync', methods=['POST'])
@login_required
def sync_activite_route(id):
    activite = Activite.query.get_or_404(id)
    if activite.est_publie:
        success, message = sync_activite(activite)
        if success:
            flash(message, 'success')
        else:
            flash(message, 'warning')
    else:
        flash('Impossible de synchroniser une activité non publiée', 'warning')
    return redirect(url_for('activites'))

# --- ROUTES RÉALISATIONS ---

@app.route('/realisations')
@login_required
def realisations():
    realisations_list = Realisation.query.order_by(Realisation.date_creation.desc()).all()
    return render_template('realisations.html', realisations=realisations_list)

@app.route('/realisation/nouveau', methods=['GET', 'POST'])
@login_required
def nouvelle_realisation():
    if request.method == 'POST':
        try:
            date_realisation = None
            if request.form.get('date_realisation'):
                date_realisation = datetime.strptime(request.form.get('date_realisation'), '%Y-%m-%d').date()
            
            nouvelle = Realisation(
                titre=request.form.get('titre'),
                description=request.form.get('description'),
                image_url=request.form.get('image_url'),
                categorie=request.form.get('categorie'),
                date_realisation=date_realisation
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            # Synchroniser avec le site principal
            success, message = sync_realisation(nouvelle)
            if success:
                flash(f'Réalisation créée et synchronisée avec le site!', 'success')
            else:
                flash(f'Réalisation créée mais erreur de synchronisation: {message}', 'warning')
                
            return redirect(url_for('realisations'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création: {str(e)}', 'danger')
    
    return render_template('edit_realisation.html', action='nouveau', realisation=None)

@app.route('/realisation/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_realisation(id):
    realisation = Realisation.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            realisation.titre = request.form.get('titre')
            realisation.description = request.form.get('description')
            realisation.image_url = request.form.get('image_url')
            realisation.categorie = request.form.get('categorie')
            
            if request.form.get('date_realisation'):
                realisation.date_realisation = datetime.strptime(request.form.get('date_realisation'), '%Y-%m-%d').date()
            else:
                realisation.date_realisation = None
            
            db.session.commit()
            
            # Synchroniser avec le site principal
            success, message = sync_realisation(realisation)
            if success:
                flash(f'Réalisation mise à jour et synchronisée!', 'success')
            else:
                flash(f'Réalisation mise à jour mais erreur de synchronisation: {message}', 'warning')
                
            return redirect(url_for('realisations'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return render_template('edit_realisation.html', action='modifier', realisation=realisation)

@app.route('/realisation/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_realisation(id):
    realisation = Realisation.query.get_or_404(id)
    try:
        # Supprimer du site principal d'abord
        if realisation.sync_id:
            delete_from_site('realisation', realisation.sync_id)
        
        db.session.delete(realisation)
        db.session.commit()
        flash('Réalisation supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('realisations'))

# --- ROUTES ANNONCES ---

@app.route('/annonces')
@login_required
def annonces():
    annonces_list = Annonce.query.order_by(Annonce.date_creation.desc()).all()
    return render_template('annonces.html', annonces=annonces_list)

@app.route('/annonce/nouveau', methods=['GET', 'POST'])
@login_required
def nouvelle_annonce():
    if request.method == 'POST':
        try:
            date_debut = None
            date_fin = None
            
            if request.form.get('date_debut'):
                date_debut = datetime.strptime(request.form.get('date_debut'), '%Y-%m-%dT%H:%M')
            if request.form.get('date_fin'):
                date_fin = datetime.strptime(request.form.get('date_fin'), '%Y-%m-%dT%H:%M')
            
            est_active = request.form.get('est_active') == 'true'
            
            nouvelle = Annonce(
                titre=request.form.get('titre'),
                contenu=request.form.get('contenu'),
                type_annonce=request.form.get('type_annonce'),
                date_debut=date_debut,
                date_fin=date_fin,
                est_active=est_active
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            # Synchroniser avec le site principal si active
            if est_active:
                success, message = sync_annonce(nouvelle)
                if success:
                    flash(f'Annonce créée et synchronisée avec le site!', 'success')
                else:
                    flash(f'Annonce créée mais erreur de synchronisation: {message}', 'warning')
            else:
                flash('Annonce créée (non active)!', 'success')
                
            return redirect(url_for('annonces'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création: {str(e)}', 'danger')
    
    return render_template('edit_annonce.html', action='nouveau', annonce=None)

@app.route('/annonce/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_annonce(id):
    annonce = Annonce.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            ancien_etat = annonce.est_active
            annonce.titre = request.form.get('titre')
            annonce.contenu = request.form.get('contenu')
            annonce.type_annonce = request.form.get('type_annonce')
            annonce.est_active = request.form.get('est_active') == 'true'
            
            if request.form.get('date_debut'):
                annonce.date_debut = datetime.strptime(request.form.get('date_debut'), '%Y-%m-%dT%H:%M')
            else:
                annonce.date_debut = None
            
            if request.form.get('date_fin'):
                annonce.date_fin = datetime.strptime(request.form.get('date_fin'), '%Y-%m-%dT%H:%M')
            else:
                annonce.date_fin = None
            
            db.session.commit()
            
            # Synchroniser avec le site principal
            if annonce.est_active:
                success, message = sync_annonce(annonce)
                if success:
                    flash(f'Annonce mise à jour et synchronisée!', 'success')
                else:
                    flash(f'Annonce mise à jour mais erreur de synchronisation: {message}', 'warning')
            elif ancien_etat and not annonce.est_active and annonce.sync_id:
                # Si on désactive, supprimer du site
                success, message = delete_from_site('annonce', annonce.sync_id)
                if success:
                    annonce.sync_id = None
                    db.session.commit()
                    flash('Annonce désactivée et retirée du site', 'info')
                else:
                    flash(f'Annonce désactivée mais erreur de retrait du site: {message}', 'warning')
            else:
                flash('Annonce mise à jour (non active)!', 'success')
                
            return redirect(url_for('annonces'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return render_template('edit_annonce.html', action='modifier', annonce=annonce)

@app.route('/annonce/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_annonce(id):
    annonce = Annonce.query.get_or_404(id)
    try:
        # Supprimer du site principal d'abord
        if annonce.sync_id:
            delete_from_site('annonce', annonce.sync_id)
        
        db.session.delete(annonce)
        db.session.commit()
        flash('Annonce supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('annonces'))

# --- ROUTES OFFRES ---

@app.route('/offres')
@login_required
def offres():
    offres_list = Offre.query.order_by(Offre.date_creation.desc()).all()
    return render_template('offres.html', offres=offres_list)

@app.route('/offre/nouveau', methods=['GET', 'POST'])
@login_required
def nouvelle_offre():
    if request.method == 'POST':
        try:
            date_limite = None
            if request.form.get('date_limite'):
                date_limite = datetime.strptime(request.form.get('date_limite'), '%Y-%m-%d').date()
            
            est_active = request.form.get('est_active') == 'true'
            
            nouvelle = Offre(
                titre=request.form.get('titre'),
                description=request.form.get('description'),
                type_offre=request.form.get('type_offre'),
                lieu=request.form.get('lieu'),
                date_limite=date_limite,
                est_active=est_active
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            # Synchroniser avec le site principal si active
            if est_active:
                success, message = sync_offre(nouvelle)
                if success:
                    flash(f'Offre créée et synchronisée avec le site!', 'success')
                else:
                    flash(f'Offre créée mais erreur de synchronisation: {message}', 'warning')
            else:
                flash('Offre créée (non active)!', 'success')
                
            return redirect(url_for('offres'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création: {str(e)}', 'danger')
    
    return render_template('edit_offre.html', action='nouveau', offre=None)

@app.route('/offre/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_offre(id):
    offre = Offre.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            ancien_etat = offre.est_active
            offre.titre = request.form.get('titre')
            offre.description = request.form.get('description')
            offre.type_offre = request.form.get('type_offre')
            offre.lieu = request.form.get('lieu')
            offre.est_active = request.form.get('est_active') == 'true'
            
            if request.form.get('date_limite'):
                offre.date_limite = datetime.strptime(request.form.get('date_limite'), '%Y-%m-%d').date()
            else:
                offre.date_limite = None
            
            db.session.commit()
            
            # Synchroniser avec le site principal
            if offre.est_active:
                success, message = sync_offre(offre)
                if success:
                    flash(f'Offre mise à jour et synchronisée!', 'success')
                else:
                    flash(f'Offre mise à jour mais erreur de synchronisation: {message}', 'warning')
            elif ancien_etat and not offre.est_active and offre.sync_id:
                # Si on désactive, supprimer du site
                success, message = delete_from_site('offre', offre.sync_id)
                if success:
                    offre.sync_id = None
                    db.session.commit()
                    flash('Offre désactivée et retirée du site', 'info')
                else:
                    flash(f'Offre désactivée mais erreur de retrait du site: {message}', 'warning')
            else:
                flash('Offre mise à jour (non active)!', 'success')
                
            return redirect(url_for('offres'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return render_template('edit_offre.html', action='modifier', offre=offre)

@app.route('/offre/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_offre(id):
    offre = Offre.query.get_or_404(id)
    try:
        # Supprimer du site principal d'abord
        if offre.sync_id:
            delete_from_site('offre', offre.sync_id)
        
        db.session.delete(offre)
        db.session.commit()
        flash('Offre supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('offres'))

# --- ROUTES DE SYNCHRONISATION MANUELLE ---

@app.route('/sync/all')
@login_required
def sync_all():
    """Synchronise tous les éléments avec le site principal"""
    try:
        # Synchroniser les activités publiées
        activites = Activite.query.filter_by(est_publie=True).all()
        for activite in activites:
            sync_activite(activite)
        
        # Synchroniser les réalisations
        realisations = Realisation.query.all()
        for realisation in realisations:
            sync_realisation(realisation)
        
        # Synchroniser les annonces actives
        annonces = Annonce.query.filter_by(est_active=True).all()
        for annonce in annonces:
            sync_annonce(annonce)
        
        # Synchroniser les offres actives
        offres = Offre.query.filter_by(est_active=True).all()
        for offre in offres:
            sync_offre(offre)
        
        flash('Tous les éléments ont été synchronisés avec le site principal!', 'success')
    except Exception as e:
        flash(f'Erreur lors de la synchronisation: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

# --- ROUTES API POUR LE SITE PRINCIPAL ---

@app.route('/api/health')
def api_health():
    """Endpoint de santé pour vérifier que l'API fonctionne"""
    return jsonify({
        'status': 'ok',
        'service': 'labmath-admin',
        'timestamp': datetime.utcnow().isoformat()
    })

# --- GESTION DES ERREURS ---

@app.errorhandler(404)
def page_not_found(e):
    if 'user_id' in session:
        return render_template('404.html'), 404
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_server_error(e):
    if 'user_id' in session:
        return render_template('500.html', error=str(e)), 500
    return redirect(url_for('login'))

# --- INITIALISATION ---
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.create_all()
    
    # Créer les tables si elles n'existent pas
    try:
        db.create_all()
        print("Base de données initialisée avec succès")
    except Exception as e:
        print(f"Erreur lors de l'initialisation de la base de données: {str(e)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)