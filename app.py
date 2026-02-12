from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import os
from functools import wraps
import requests
import json

# Création de l'application Flask
app = Flask(__name__,
            template_folder='templates',
            static_folder='static')
CORS(app)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '32015@1a')

# Correction pour PostgreSQL sur Render
database_url = os.environ.get('DATABASE_URL', 'sqlite:///labmath_db.sqlite')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Initialisation de la base de données
db = SQLAlchemy(app)

# --- CONFIGURATION API DU SITE PRINCIPAL ---
# UTILISEZ L'URL CORRECTE DE VOTRE SITE PRINCIPAL
SITE_URL = os.environ.get('SITE_URL', 'https://labmathscsmaubmar.org')  # À MODIFIER
API_KEY = os.environ.get('API_KEY', 'labmath_api_secret_2024')  # MÊME CLÉ QUE DANS api.py
API_TIMEOUT = int(os.environ.get('API_TIMEOUT', 15))

print(f"🌐 Site principal configuré: {SITE_URL}")
print(f"🔑 Clé API configurée: {'Oui' if API_KEY else 'Non'}")

# --- DÉCORATEUR SÉCURITÉ ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- MODÈLES AVEC CHAMPS DE SYNCHRONISATION ---
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
    # Champs de synchronisation
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='pending')
    sync_message = db.Column(db.Text)

class Realisation(db.Model):
    __tablename__ = 'realisations'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    categorie = db.Column(db.String(100))
    date_realisation = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_modification = db.Column(db.DateTime, onupdate=datetime.utcnow)
    # Champs de synchronisation
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='pending')
    sync_message = db.Column(db.Text)

class Annonce(db.Model):
    __tablename__ = 'annonces'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    contenu = db.Column(db.Text)
    type_annonce = db.Column(db.String(50))
    date_debut = db.Column(db.DateTime)
    date_fin = db.Column(db.DateTime)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_modification = db.Column(db.DateTime, onupdate=datetime.utcnow)
    est_active = db.Column(db.Boolean, default=True)
    # Champs de synchronisation
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='pending')
    sync_message = db.Column(db.Text)

class Offre(db.Model):
    __tablename__ = 'offres'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type_offre = db.Column(db.String(50))
    lieu = db.Column(db.String(100))
    date_limite = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_modification = db.Column(db.DateTime, onupdate=datetime.utcnow)
    est_active = db.Column(db.Boolean, default=True)
    # Champs de synchronisation
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='pending')
    sync_message = db.Column(db.Text)

# --- FONCTIONS DE SYNCHRONISATION POUR L'API JSON ---

def get_api_headers():
    """Retourne les headers pour l'API du site principal"""
    return {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
        'User-Agent': 'labmath-admin/1.0'
    }

def check_site_connection():
    """Vérifie la connexion avec le site principal"""
    if not API_KEY:
        return False, "Clé API non configurée"
    
    try:
        response = requests.get(
            f"{SITE_URL}/api/health",
            headers=get_api_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return True, data.get('message', 'Connecté')
        else:
            return False, f"Erreur {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Site principal inaccessible"
    except requests.exceptions.Timeout:
        return False, "Délai d'attente dépassé"
    except Exception as e:
        return False, str(e)[:50]

def sync_activite_to_site(activite):
    """Synchronise une activité vers le site principal (API JSON)"""
    if not API_KEY:
        activite.sync_status = 'failed'
        activite.sync_message = "Clé API non configurée"
        db.session.commit()
        return False, "Clé API non configurée"
    
    if not activite.est_publie:
        activite.sync_status = 'skipped'
        activite.sync_message = "Non publié - synchronisation ignorée"
        db.session.commit()
        return True, "Synchronisation ignorée (non publié)"
    
    try:
        # Préparer les données pour l'API
        data = {
            'id': str(activite.id),
            'titre': activite.titre,
            'description': activite.description or '',
            'contenu': activite.contenu or '',
            'image_url': activite.image_url or '',
            'auteur': activite.auteur or 'Admin',
            'est_publie': activite.est_publie,
            'date_creation': activite.date_creation.isoformat() if activite.date_creation else datetime.utcnow().isoformat()
        }
        
        # Appel à l'API du site principal
        url = f"{SITE_URL}/api/activites/{activite.id}"
        response = requests.post(
            url,
            json=data,
            headers=get_api_headers(),
            timeout=API_TIMEOUT
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            activite.last_sync = datetime.utcnow()
            activite.sync_status = 'success'
            activite.sync_message = f"Synchronisé le {activite.last_sync.strftime('%d/%m/%Y %H:%M')}"
            db.session.commit()
            return True, "Synchronisation réussie"
        else:
            error_msg = f"Erreur API {response.status_code}"
            try:
                error_data = response.json()
                error_msg += f": {error_data.get('message', '')}"
            except:
                error_msg += f": {response.text[:100]}"
            
            activite.sync_status = 'failed'
            activite.sync_message = error_msg
            db.session.commit()
            return False, error_msg
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Erreur de connexion: {str(e)}"
        activite.sync_status = 'failed'
        activite.sync_message = error_msg
        db.session.commit()
        return False, error_msg
    except Exception as e:
        error_msg = f"Erreur: {str(e)}"
        activite.sync_status = 'failed'
        activite.sync_message = error_msg
        db.session.commit()
        return False, error_msg

def sync_realisation_to_site(realisation):
    """Synchronise une réalisation vers le site principal"""
    if not API_KEY:
        realisation.sync_status = 'failed'
        realisation.sync_message = "Clé API non configurée"
        db.session.commit()
        return False, "Clé API non configurée"
    
    try:
        data = {
            'id': str(realisation.id),
            'titre': realisation.titre,
            'description': realisation.description or '',
            'image_url': realisation.image_url or '',
            'categorie': realisation.categorie or '',
            'date_realisation': realisation.date_realisation.isoformat() if realisation.date_realisation else None,
            'date_creation': realisation.date_creation.isoformat() if realisation.date_creation else datetime.utcnow().isoformat()
        }
        
        url = f"{SITE_URL}/api/realisations/{realisation.id}"
        response = requests.post(
            url,
            json=data,
            headers=get_api_headers(),
            timeout=API_TIMEOUT
        )
        
        if response.status_code in [200, 201]:
            realisation.last_sync = datetime.utcnow()
            realisation.sync_status = 'success'
            realisation.sync_message = f"Synchronisé le {realisation.last_sync.strftime('%d/%m/%Y %H:%M')}"
            db.session.commit()
            return True, "Synchronisation réussie"
        else:
            error_msg = f"Erreur API {response.status_code}"
            realisation.sync_status = 'failed'
            realisation.sync_message = error_msg
            db.session.commit()
            return False, error_msg
            
    except Exception as e:
        realisation.sync_status = 'failed'
        realisation.sync_message = str(e)
        db.session.commit()
        return False, str(e)

def sync_annonce_to_site(annonce):
    """Synchronise une annonce vers le site principal"""
    if not API_KEY:
        annonce.sync_status = 'failed'
        annonce.sync_message = "Clé API non configurée"
        db.session.commit()
        return False, "Clé API non configurée"
    
    if not annonce.est_active:
        annonce.sync_status = 'skipped'
        annonce.sync_message = "Non active - synchronisation ignorée"
        db.session.commit()
        return True, "Synchronisation ignorée (non active)"
    
    try:
        data = {
            'id': str(annonce.id),
            'titre': annonce.titre,
            'contenu': annonce.contenu or '',
            'type_annonce': annonce.type_annonce or 'info',
            'date_debut': annonce.date_debut.isoformat() if annonce.date_debut else None,
            'date_fin': annonce.date_fin.isoformat() if annonce.date_fin else None,
            'date_creation': annonce.date_creation.isoformat() if annonce.date_creation else datetime.utcnow().isoformat(),
            'est_active': annonce.est_active
        }
        
        url = f"{SITE_URL}/api/annonces/{annonce.id}"
        response = requests.post(
            url,
            json=data,
            headers=get_api_headers(),
            timeout=API_TIMEOUT
        )
        
        if response.status_code in [200, 201]:
            annonce.last_sync = datetime.utcnow()
            annonce.sync_status = 'success'
            annonce.sync_message = f"Synchronisé le {annonce.last_sync.strftime('%d/%m/%Y %H:%M')}"
            db.session.commit()
            return True, "Synchronisation réussie"
        else:
            error_msg = f"Erreur API {response.status_code}"
            annonce.sync_status = 'failed'
            annonce.sync_message = error_msg
            db.session.commit()
            return False, error_msg
            
    except Exception as e:
        annonce.sync_status = 'failed'
        annonce.sync_message = str(e)
        db.session.commit()
        return False, str(e)

def sync_offre_to_site(offre):
    """Synchronise une offre vers le site principal"""
    if not API_KEY:
        offre.sync_status = 'failed'
        offre.sync_message = "Clé API non configurée"
        db.session.commit()
        return False, "Clé API non configurée"
    
    if not offre.est_active:
        offre.sync_status = 'skipped'
        offre.sync_message = "Non active - synchronisation ignorée"
        db.session.commit()
        return True, "Synchronisation ignorée (non active)"
    
    try:
        data = {
            'id': str(offre.id),
            'titre': offre.titre,
            'description': offre.description or '',
            'type_offre': offre.type_offre or 'autre',
            'lieu': offre.lieu or '',
            'date_limite': offre.date_limite.isoformat() if offre.date_limite else None,
            'date_creation': offre.date_creation.isoformat() if offre.date_creation else datetime.utcnow().isoformat(),
            'est_active': offre.est_active
        }
        
        url = f"{SITE_URL}/api/offres/{offre.id}"
        response = requests.post(
            url,
            json=data,
            headers=get_api_headers(),
            timeout=API_TIMEOUT
        )
        
        if response.status_code in [200, 201]:
            offre.last_sync = datetime.utcnow()
            offre.sync_status = 'success'
            offre.sync_message = f"Synchronisé le {offre.last_sync.strftime('%d/%m/%Y %H:%M')}"
            db.session.commit()
            return True, "Synchronisation réussie"
        else:
            error_msg = f"Erreur API {response.status_code}"
            offre.sync_status = 'failed'
            offre.sync_message = error_msg
            db.session.commit()
            return False, error_msg
            
    except Exception as e:
        offre.sync_status = 'failed'
        offre.sync_message = str(e)
        db.session.commit()
        return False, str(e)

def delete_from_site(model_type, item_id):
    """Supprime un élément du site principal"""
    if not API_KEY:
        return False, "Clé API non configurée"
    
    try:
        endpoints = {
            'activite': f"{SITE_URL}/api/activites/{item_id}",
            'realisation': f"{SITE_URL}/api/realisations/{item_id}",
            'annonce': f"{SITE_URL}/api/annonces/{item_id}",
            'offre': f"{SITE_URL}/api/offres/{item_id}"
        }
        
        url = endpoints.get(model_type)
        if not url:
            return False, "Type de modèle inconnu"
        
        response = requests.delete(
            url,
            headers=get_api_headers(),
            timeout=API_TIMEOUT
        )
        
        if response.status_code in [200, 204]:
            return True, "Suppression synchronisée"
        else:
            return False, f"Erreur {response.status_code}"
            
    except Exception as e:
        return False, f"Erreur: {str(e)}"

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
    try:
        stats = {
            'activities_count': Activite.query.count(),
            'realisations_count': Realisation.query.count(),
            'annonces_count': Annonce.query.count(),
            'offres_count': Offre.query.count(),
            'activities_published': Activite.query.filter_by(est_publie=True).count(),
            'annonces_active': Annonce.query.filter_by(est_active=True).count(),
            'offres_active': Offre.query.filter_by(est_active=True).count(),
            'sync_pending': Activite.query.filter_by(sync_status='pending').count() +
                           Realisation.query.filter_by(sync_status='pending').count() +
                           Annonce.query.filter_by(sync_status='pending').count() +
                           Offre.query.filter_by(sync_status='pending').count(),
            'sync_failed': Activite.query.filter_by(sync_status='failed').count() +
                          Realisation.query.filter_by(sync_status='failed').count() +
                          Annonce.query.filter_by(sync_status='failed').count() +
                          Offre.query.filter_by(sync_status='failed').count()
        }
        
        # Vérification de la connexion au site principal
        site_connected, site_message = check_site_connection()
        stats['site_connected'] = site_connected
        stats['site_message'] = site_message
        
        # Récupérer les 5 derniers éléments
        recent_activities = Activite.query.order_by(Activite.date_creation.desc()).limit(5).all()
        recent_annonces = Annonce.query.order_by(Annonce.date_creation.desc()).limit(5).all()
        
        return render_template('dashboard.html',
                              stats=stats,
                              now=datetime.utcnow(),
                              site_url=SITE_URL,
                              recent_activities=recent_activities,
                              recent_annonces=recent_annonces,
                              api_key_configured=bool(API_KEY))
    except Exception as e:
        flash(f'Erreur lors du chargement du dashboard: {str(e)}', 'danger')
        return render_template('simple_dashboard.html',
                              stats={'activities_count': 0, 'realisations_count': 0, 
                                    'annonces_count': 0, 'offres_count': 0},
                              now=datetime.utcnow(),
                              error=str(e))

# --- ROUTES ACTIVITÉS ---

@app.route('/activites')
@login_required
def activites():
    activites_list = Activite.query.order_by(Activite.date_creation.desc()).all()
    site_connected, _ = check_site_connection()
    return render_template('activites.html', 
                          activites=activites_list,
                          site_connected=site_connected,
                          api_key_configured=bool(API_KEY))

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
                est_publie=est_publie,
                sync_status='pending'
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            # Synchronisation automatique si publié
            if est_publie:
                success, message = sync_activite_to_site(nouvelle)
                if success:
                    flash(f'✅ Activité créée et synchronisée avec le site principal!', 'success')
                else:
                    flash(f'⚠️ Activité créée mais échec de synchronisation: {message}', 'warning')
            else:
                flash('📝 Activité créée (non publiée - pas de synchronisation)', 'info')
                
            return redirect(url_for('activites'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur lors de la création: {str(e)}', 'danger')
    
    return render_template('edit_activite.html', action='nouveau', activite=None)

@app.route('/activite/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_activite(id):
    activite = Activite.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            ancien_etat_publie = activite.est_publie
            nouvel_etat_publie = request.form.get('est_publie') == 'true'
            
            activite.titre = request.form.get('titre')
            activite.description = request.form.get('description')
            activite.contenu = request.form.get('contenu')
            activite.image_url = request.form.get('image_url')
            activite.est_publie = nouvel_etat_publie
            activite.date_modification = datetime.utcnow()
            activite.sync_status = 'pending'
            
            db.session.commit()
            
            # Synchronisation si l'activité est publiée
            if activite.est_publie:
                success, message = sync_activite_to_site(activite)
                if success:
                    flash(f'✅ Activité mise à jour et synchronisée!', 'success')
                else:
                    flash(f'⚠️ Activité mise à jour mais échec de synchronisation: {message}', 'warning')
            else:
                # Si elle n'est plus publiée, essayer de la supprimer du site
                if ancien_etat_publie and not nouvel_etat_publie:
                    delete_from_site('activite', activite.id)
                flash('📝 Activité mise à jour (non publiée)', 'info')
            
            return redirect(url_for('activites'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return render_template('edit_activite.html', action='modifier', activite=activite)

@app.route('/activite/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_activite(id):
    activite = Activite.query.get_or_404(id)
    ancien_etat_publie = activite.est_publie
    
    try:
        # Supprimer du site principal d'abord si publié
        if ancien_etat_publie:
            success, message = delete_from_site('activite', id)
            if not success:
                flash(f'⚠️ {message}', 'warning')
        
        # Supprimer de la base locale
        db.session.delete(activite)
        db.session.commit()
        flash('✅ Activité supprimée avec succès!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('activites'))

@app.route('/activite/<int:id>/sync', methods=['POST'])
@login_required
def sync_activite_route(id):
    activite = Activite.query.get_or_404(id)
    success, message = sync_activite_to_site(activite)
    
    if success:
        flash(f'✅ Synchronisation réussie: {activite.titre}', 'success')
    else:
        flash(f'❌ Échec de synchronisation: {message}', 'danger')
    
    return redirect(url_for('activites'))

# --- ROUTES RÉALISATIONS ---

@app.route('/realisations')
@login_required
def realisations():
    realisations_list = Realisation.query.order_by(Realisation.date_creation.desc()).all()
    site_connected, _ = check_site_connection()
    return render_template('realisations.html', 
                          realisations=realisations_list,
                          site_connected=site_connected,
                          api_key_configured=bool(API_KEY))

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
                date_realisation=date_realisation,
                sync_status='pending'
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            # Synchronisation automatique
            success, message = sync_realisation_to_site(nouvelle)
            if success:
                flash('✅ Réalisation créée et synchronisée!', 'success')
            else:
                flash(f'⚠️ Réalisation créée mais échec de synchronisation: {message}', 'warning')
                
            return redirect(url_for('realisations'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur lors de la création: {str(e)}', 'danger')
    
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
            realisation.date_modification = datetime.utcnow()
            realisation.sync_status = 'pending'
            
            if request.form.get('date_realisation'):
                realisation.date_realisation = datetime.strptime(request.form.get('date_realisation'), '%Y-%m-%d').date()
            else:
                realisation.date_realisation = None
            
            db.session.commit()
            
            # Synchronisation
            success, message = sync_realisation_to_site(realisation)
            if success:
                flash('✅ Réalisation mise à jour et synchronisée!', 'success')
            else:
                flash(f'⚠️ Réalisation mise à jour mais échec de synchronisation: {message}', 'warning')
            
            return redirect(url_for('realisations'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return render_template('edit_realisation.html', action='modifier', realisation=realisation)

@app.route('/realisation/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_realisation(id):
    realisation = Realisation.query.get_or_404(id)
    
    try:
        # Supprimer du site principal
        success, message = delete_from_site('realisation', id)
        if not success:
            flash(f'⚠️ {message}', 'warning')
        
        # Supprimer de la base locale
        db.session.delete(realisation)
        db.session.commit()
        flash('✅ Réalisation supprimée avec succès!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('realisations'))

# --- ROUTES ANNONCES ---

@app.route('/annonces')
@login_required
def annonces():
    annonces_list = Annonce.query.order_by(Annonce.date_creation.desc()).all()
    site_connected, _ = check_site_connection()
    return render_template('annonces.html', 
                          annonces=annonces_list,
                          site_connected=site_connected,
                          api_key_configured=bool(API_KEY))

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
                est_active=est_active,
                sync_status='pending'
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            # Synchronisation si active
            if est_active:
                success, message = sync_annonce_to_site(nouvelle)
                if success:
                    flash('✅ Annonce créée et synchronisée!', 'success')
                else:
                    flash(f'⚠️ Annonce créée mais échec de synchronisation: {message}', 'warning')
            else:
                flash('📝 Annonce créée (non active - pas de synchronisation)', 'info')
                
            return redirect(url_for('annonces'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur lors de la création: {str(e)}', 'danger')
    
    return render_template('edit_annonce.html', action='nouveau', annonce=None)

@app.route('/annonce/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_annonce(id):
    annonce = Annonce.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            ancien_etat = annonce.est_active
            nouvel_etat = request.form.get('est_active') == 'true'
            
            annonce.titre = request.form.get('titre')
            annonce.contenu = request.form.get('contenu')
            annonce.type_annonce = request.form.get('type_annonce')
            annonce.est_active = nouvel_etat
            annonce.date_modification = datetime.utcnow()
            annonce.sync_status = 'pending'
            
            if request.form.get('date_debut'):
                annonce.date_debut = datetime.strptime(request.form.get('date_debut'), '%Y-%m-%dT%H:%M')
            else:
                annonce.date_debut = None
            
            if request.form.get('date_fin'):
                annonce.date_fin = datetime.strptime(request.form.get('date_fin'), '%Y-%m-%dT%H:%M')
            else:
                annonce.date_fin = None
            
            db.session.commit()
            
            # Synchronisation si active
            if annonce.est_active:
                success, message = sync_annonce_to_site(annonce)
                if success:
                    flash('✅ Annonce mise à jour et synchronisée!', 'success')
                else:
                    flash(f'⚠️ Annonce mise à jour mais échec de synchronisation: {message}', 'warning')
            else:
                # Si elle n'est plus active, supprimer du site
                if ancien_etat and not nouvel_etat:
                    delete_from_site('annonce', annonce.id)
                flash('📝 Annonce mise à jour (non active)', 'info')
            
            return redirect(url_for('annonces'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return render_template('edit_annonce.html', action='modifier', annonce=annonce)

@app.route('/annonce/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_annonce(id):
    annonce = Annonce.query.get_or_404(id)
    
    try:
        if annonce.est_active:
            delete_from_site('annonce', id)
        
        db.session.delete(annonce)
        db.session.commit()
        flash('✅ Annonce supprimée avec succès!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('annonces'))

# --- ROUTES OFFRES ---

@app.route('/offres')
@login_required
def offres():
    offres_list = Offre.query.order_by(Offre.date_creation.desc()).all()
    site_connected, _ = check_site_connection()
    return render_template('offres.html', 
                          offres=offres_list,
                          site_connected=site_connected,
                          api_key_configured=bool(API_KEY))

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
                est_active=est_active,
                sync_status='pending'
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            if est_active:
                success, message = sync_offre_to_site(nouvelle)
                if success:
                    flash('✅ Offre créée et synchronisée!', 'success')
                else:
                    flash(f'⚠️ Offre créée mais échec de synchronisation: {message}', 'warning')
            else:
                flash('📝 Offre créée (non active - pas de synchronisation)', 'info')
                
            return redirect(url_for('offres'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur lors de la création: {str(e)}', 'danger')
    
    return render_template('edit_offre.html', action='nouveau', offre=None)

@app.route('/offre/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_offre(id):
    offre = Offre.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            ancien_etat = offre.est_active
            nouvel_etat = request.form.get('est_active') == 'true'
            
            offre.titre = request.form.get('titre')
            offre.description = request.form.get('description')
            offre.type_offre = request.form.get('type_offre')
            offre.lieu = request.form.get('lieu')
            offre.est_active = nouvel_etat
            offre.date_modification = datetime.utcnow()
            offre.sync_status = 'pending'
            
            if request.form.get('date_limite'):
                offre.date_limite = datetime.strptime(request.form.get('date_limite'), '%Y-%m-%d').date()
            else:
                offre.date_limite = None
            
            db.session.commit()
            
            if offre.est_active:
                success, message = sync_offre_to_site(offre)
                if success:
                    flash('✅ Offre mise à jour et synchronisée!', 'success')
                else:
                    flash(f'⚠️ Offre mise à jour mais échec de synchronisation: {message}', 'warning')
            else:
                if ancien_etat and not nouvel_etat:
                    delete_from_site('offre', offre.id)
                flash('📝 Offre mise à jour (non active)', 'info')
            
            return redirect(url_for('offres'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return render_template('edit_offre.html', action='modifier', offre=offre)

@app.route('/offre/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_offre(id):
    offre = Offre.query.get_or_404(id)
    
    try:
        if offre.est_active:
            delete_from_site('offre', id)
        
        db.session.delete(offre)
        db.session.commit()
        flash('✅ Offre supprimée avec succès!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('offres'))

# --- ROUTES DE SYNCHRONISATION MANUELLE ---

@app.route('/sync/all')
@login_required
def sync_all():
    """Synchronise tous les éléments publiés/actifs"""
    if not API_KEY:
        flash('❌ Clé API non configurée. Impossible de synchroniser.', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        # Récupérer tous les éléments à synchroniser
        activites = Activite.query.filter_by(est_publie=True).all()
        realisations = Realisation.query.all()
        annonces = Annonce.query.filter_by(est_active=True).all()
        offres = Offre.query.filter_by(est_active=True).all()
        
        total = len(activites) + len(realisations) + len(annonces) + len(offres)
        success_count = 0
        fail_count = 0
        
        flash(f'🔄 Synchronisation de {total} élément(s)...', 'info')
        
        for activite in activites:
            success, _ = sync_activite_to_site(activite)
            if success: success_count += 1
            else: fail_count += 1
        
        for realisation in realisations:
            success, _ = sync_realisation_to_site(realisation)
            if success: success_count += 1
            else: fail_count += 1
        
        for annonce in annonces:
            success, _ = sync_annonce_to_site(annonce)
            if success: success_count += 1
            else: fail_count += 1
        
        for offre in offres:
            success, _ = sync_offre_to_site(offre)
            if success: success_count += 1
            else: fail_count += 1
        
        flash(f'✅ Synchronisation terminée: {success_count} réussie(s), {fail_count} échec(s)', 
              'success' if fail_count == 0 else 'warning')
        
    except Exception as e:
        flash(f'❌ Erreur lors de la synchronisation: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/sync/retry-failed')
@login_required
def retry_failed():
    """Réessaie de synchroniser uniquement les éléments en échec"""
    try:
        activites = Activite.query.filter_by(sync_status='failed').all()
        realisations = Realisation.query.filter_by(sync_status='failed').all()
        annonces = Annonce.query.filter_by(sync_status='failed').all()
        offres = Offre.query.filter_by(sync_status='failed').all()
        
        total = len(activites) + len(realisations) + len(annonces) + len(offres)
        success_count = 0
        
        for item in activites + realisations + annonces + offres:
            if isinstance(item, Activite):
                success, _ = sync_activite_to_site(item)
            elif isinstance(item, Realisation):
                success, _ = sync_realisation_to_site(item)
            elif isinstance(item, Annonce):
                success, _ = sync_annonce_to_site(item)
            elif isinstance(item, Offre):
                success, _ = sync_offre_to_site(item)
            
            if success:
                success_count += 1
        
        flash(f'✅ {success_count}/{total} éléments resynchronisés avec succès', 'success')
        
    except Exception as e:
        flash(f'❌ Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

# --- ROUTES API POUR LE SITE PRINCIPAL (STATUS) ---

@app.route('/api/health')
def api_health():
    """Endpoint de santé"""
    site_connected, site_message = check_site_connection()
    return jsonify({
        'status': 'ok',
        'service': 'labmath-admin',
        'timestamp': datetime.utcnow().isoformat(),
        'site_connected': site_connected,
        'site_message': site_message,
        'api_configured': bool(API_KEY),
        'site_url': SITE_URL
    })

# --- GESTION DES ERREURS ---

@app.errorhandler(404)
def page_not_found(e):
    if 'user_id' in session:
        return render_template('404.html'), 404
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_server_error(e):
    db.session.rollback()
    if 'user_id' in session:
        return render_template('500.html', error=str(e)), 500
    return redirect(url_for('login'))

# --- INITIALISATION DE LA BASE DE DONNÉES ---

def init_database():
    """Initialise la base de données avec les colonnes de synchronisation"""
    try:
        db.create_all()
        
        # Vérifier et ajouter les colonnes manquantes
        with db.engine.connect() as conn:
            # Pour Activite
            try:
                conn.execute(db.text('ALTER TABLE activites ADD COLUMN last_sync TIMESTAMP'))
            except:
                pass
            try:
                conn.execute(db.text("ALTER TABLE activites ADD COLUMN sync_status VARCHAR(20) DEFAULT 'pending'"))
            except:
                pass
            try:
                conn.execute(db.text('ALTER TABLE activites ADD COLUMN sync_message TEXT'))
            except:
                pass
            
            # Pour Realisation
            try:
                conn.execute(db.text('ALTER TABLE realisations ADD COLUMN last_sync TIMESTAMP'))
            except:
                pass
            try:
                conn.execute(db.text("ALTER TABLE realisations ADD COLUMN sync_status VARCHAR(20) DEFAULT 'pending'"))
            except:
                pass
            try:
                conn.execute(db.text('ALTER TABLE realisations ADD COLUMN sync_message TEXT'))
            except:
                pass
            
            # Pour Annonce
            try:
                conn.execute(db.text('ALTER TABLE annonces ADD COLUMN last_sync TIMESTAMP'))
            except:
                pass
            try:
                conn.execute(db.text("ALTER TABLE annonces ADD COLUMN sync_status VARCHAR(20) DEFAULT 'pending'"))
            except:
                pass
            try:
                conn.execute(db.text('ALTER TABLE annonces ADD COLUMN sync_message TEXT'))
            except:
                pass
            
            # Pour Offre
            try:
                conn.execute(db.text('ALTER TABLE offres ADD COLUMN last_sync TIMESTAMP'))
            except:
                pass
            try:
                conn.execute(db.text("ALTER TABLE offres ADD COLUMN sync_status VARCHAR(20) DEFAULT 'pending'"))
            except:
                pass
            try:
                conn.execute(db.text('ALTER TABLE offres ADD COLUMN sync_message TEXT'))
            except:
                pass
            
            conn.commit()
            
    except Exception as e:
        print(f"⚠️ Note: {e}")

# --- INITIALISATION ---
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_database()
    print("✅ Base de données initialisée")
    print(f"📁 Dossier templates: {app.template_folder}")
    print(f"🌐 Site principal: {SITE_URL}")
    print(f"🔑 API Key: {'Configurée' if API_KEY else 'Non configurée'}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)