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
SITE_URL = os.environ.get('SITE_URL', 'https://labmathscsmaubmar.org')
API_KEY = os.environ.get('API_KEY', 'labmath_api_secret_2024')

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

# --- MODÈLES SIMPLIFIÉS (SANS date_modification) ---
class Activite(db.Model):
    __tablename__ = 'activites'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    contenu = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    auteur = db.Column(db.String(100))
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    est_publie = db.Column(db.Boolean, default=True)
    # Synchronisation
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
    # Synchronisation
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
    est_active = db.Column(db.Boolean, default=True)
    # Synchronisation
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
    est_active = db.Column(db.Boolean, default=True)
    # Synchronisation
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='pending')
    sync_message = db.Column(db.Text)

# --- FONCTIONS DE SYNCHRONISATION ---
def get_api_headers():
    return {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
    }

def check_site_connection():
    if not API_KEY:
        return False, "Clé API non configurée"
    try:
        response = requests.get(f"{SITE_URL}/api/health", timeout=5)
        return response.status_code == 200, "Connecté" if response.status_code == 200 else f"Erreur {response.status_code}"
    except:
        return False, "Site inaccessible"

def sync_activite_to_site(activite):
    if not API_KEY or not activite.est_publie:
        return False, "Non synchronisé"
    try:
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
        response = requests.post(f"{SITE_URL}/api/activites/{activite.id}", json=data, headers=get_api_headers(), timeout=10)
        if response.status_code in [200, 201]:
            activite.last_sync = datetime.utcnow()
            activite.sync_status = 'success'
            db.session.commit()
            return True, "Synchronisé"
        return False, f"Erreur {response.status_code}"
    except Exception as e:
        activite.sync_status = 'failed'
        activite.sync_message = str(e)[:100]
        db.session.commit()
        return False, str(e)[:50]

def sync_realisation_to_site(realisation):
    if not API_KEY:
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
        response = requests.post(f"{SITE_URL}/api/realisations/{realisation.id}", json=data, headers=get_api_headers(), timeout=10)
        if response.status_code in [200, 201]:
            realisation.last_sync = datetime.utcnow()
            realisation.sync_status = 'success'
            db.session.commit()
            return True, "Synchronisé"
        return False, f"Erreur {response.status_code}"
    except Exception as e:
        realisation.sync_status = 'failed'
        realisation.sync_message = str(e)[:100]
        db.session.commit()
        return False, str(e)[:50]

def sync_annonce_to_site(annonce):
    if not API_KEY or not annonce.est_active:
        return False, "Non synchronisé"
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
        response = requests.post(f"{SITE_URL}/api/annonces/{annonce.id}", json=data, headers=get_api_headers(), timeout=10)
        if response.status_code in [200, 201]:
            annonce.last_sync = datetime.utcnow()
            annonce.sync_status = 'success'
            db.session.commit()
            return True, "Synchronisé"
        return False, f"Erreur {response.status_code}"
    except Exception as e:
        annonce.sync_status = 'failed'
        annonce.sync_message = str(e)[:100]
        db.session.commit()
        return False, str(e)[:50]

def sync_offre_to_site(offre):
    if not API_KEY or not offre.est_active:
        return False, "Non synchronisé"
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
        response = requests.post(f"{SITE_URL}/api/offres/{offre.id}", json=data, headers=get_api_headers(), timeout=10)
        if response.status_code in [200, 201]:
            offre.last_sync = datetime.utcnow()
            offre.sync_status = 'success'
            db.session.commit()
            return True, "Synchronisé"
        return False, f"Erreur {response.status_code}"
    except Exception as e:
        offre.sync_status = 'failed'
        offre.sync_message = str(e)[:100]
        db.session.commit()
        return False, str(e)[:50]

def delete_from_site(model_type, item_id):
    if not API_KEY:
        return False, "Clé API non configurée"
    try:
        url = f"{SITE_URL}/api/{model_type}s/{item_id}"
        response = requests.delete(url, headers=get_api_headers(), timeout=10)
        return response.status_code in [200, 204], "Supprimé" if response.status_code in [200, 204] else f"Erreur {response.status_code}"
    except Exception as e:
        return False, str(e)[:50]

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

# --- ROUTES DASHBOARD (SIMPLE ET SANS ERREUR) ---
@app.route('/dashboard')
@login_required
def dashboard():
    try:
        # Statistiques simples
        stats = {
            'activities_count': Activite.query.count(),
            'realisations_count': Realisation.query.count(),
            'annonces_count': Annonce.query.count(),
            'offres_count': Offre.query.count(),
            'activities_published': Activite.query.filter_by(est_publie=True).count(),
            'annonces_active': Annonce.query.filter_by(est_active=True).count(),
            'offres_active': Offre.query.filter_by(est_active=True).count(),
        }
        
        # Vérification connexion
        site_connected, site_message = check_site_connection()
        stats['site_connected'] = site_connected
        stats['site_message'] = site_message
        
        # 5 derniers éléments
        recent_activities = Activite.query.order_by(Activite.date_creation.desc()).limit(5).all()
        recent_annonces = Annonce.query.order_by(Annonce.date_creation.desc()).limit(5).all()
        
        return render_template('dashboard.html',
                              stats=stats,
                              now=datetime.utcnow(),
                              site_url=SITE_URL,
                              recent_activities=recent_activities,
                              recent_annonces=recent_annonces)
    except Exception as e:
        flash(f'Erreur: {str(e)}', 'danger')
        return render_template('dashboard_simple.html',
                              error=str(e),
                              now=datetime.utcnow())

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
            nouvelle = Activite(
                titre=request.form.get('titre'),
                description=request.form.get('description'),
                contenu=request.form.get('contenu'),
                image_url=request.form.get('image_url'),
                auteur=session.get('username', 'Admin'),
                est_publie=request.form.get('est_publie') == 'true',
                sync_status='pending'
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            if nouvelle.est_publie:
                success, message = sync_activite_to_site(nouvelle)
                if success:
                    flash('✅ Activité créée et synchronisée!', 'success')
                else:
                    flash(f'⚠️ Activité créée mais synchronisation échouée: {message}', 'warning')
            else:
                flash('📝 Activité créée (non publiée)', 'info')
            
            return redirect(url_for('activites'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur: {str(e)}', 'danger')
    
    return render_template('edit_activite.html', action='nouveau', activite=None)

@app.route('/activite/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_activite(id):
    activite = Activite.query.get_or_404(id)
    if request.method == 'POST':
        try:
            ancien_publie = activite.est_publie
            activite.titre = request.form.get('titre')
            activite.description = request.form.get('description')
            activite.contenu = request.form.get('contenu')
            activite.image_url = request.form.get('image_url')
            activite.est_publie = request.form.get('est_publie') == 'true'
            activite.sync_status = 'pending'
            db.session.commit()
            
            if activite.est_publie:
                success, message = sync_activite_to_site(activite)
                flash('✅ Activité mise à jour et synchronisée!' if success else f'⚠️ {message}', 
                      'success' if success else 'warning')
            elif ancien_publie and not activite.est_publie:
                delete_from_site('activite', activite.id)
                flash('📝 Activité dépubliée', 'info')
            
            return redirect(url_for('activites'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur: {str(e)}', 'danger')
    
    return render_template('edit_activite.html', action='modifier', activite=activite)

@app.route('/activite/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_activite(id):
    activite = Activite.query.get_or_404(id)
    try:
        if activite.est_publie:
            delete_from_site('activite', id)
        db.session.delete(activite)
        db.session.commit()
        flash('✅ Activité supprimée', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur: {str(e)}', 'danger')
    return redirect(url_for('activites'))

@app.route('/activite/<int:id>/sync', methods=['POST'])
@login_required
def sync_activite_route(id):
    activite = Activite.query.get_or_404(id)
    success, message = sync_activite_to_site(activite)
    flash(f'✅ Synchronisation réussie' if success else f'❌ {message}', 
          'success' if success else 'danger')
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
                date_realisation=date_realisation,
                sync_status='pending'
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            success, message = sync_realisation_to_site(nouvelle)
            flash('✅ Réalisation créée et synchronisée!' if success else f'⚠️ {message}', 
                  'success' if success else 'warning')
            
            return redirect(url_for('realisations'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur: {str(e)}', 'danger')
    
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
            realisation.sync_status = 'pending'
            
            if request.form.get('date_realisation'):
                realisation.date_realisation = datetime.strptime(request.form.get('date_realisation'), '%Y-%m-%d').date()
            else:
                realisation.date_realisation = None
            
            db.session.commit()
            
            success, message = sync_realisation_to_site(realisation)
            flash('✅ Réalisation mise à jour et synchronisée!' if success else f'⚠️ {message}', 
                  'success' if success else 'warning')
            
            return redirect(url_for('realisations'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur: {str(e)}', 'danger')
    
    return render_template('edit_realisation.html', action='modifier', realisation=realisation)

@app.route('/realisation/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_realisation(id):
    realisation = Realisation.query.get_or_404(id)
    try:
        delete_from_site('realisation', id)
        db.session.delete(realisation)
        db.session.commit()
        flash('✅ Réalisation supprimée', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur: {str(e)}', 'danger')
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
            
            nouvelle = Annonce(
                titre=request.form.get('titre'),
                contenu=request.form.get('contenu'),
                type_annonce=request.form.get('type_annonce'),
                date_debut=date_debut,
                date_fin=date_fin,
                est_active=request.form.get('est_active') == 'true',
                sync_status='pending'
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            if nouvelle.est_active:
                success, message = sync_annonce_to_site(nouvelle)
                flash('✅ Annonce créée et synchronisée!' if success else f'⚠️ {message}', 
                      'success' if success else 'warning')
            else:
                flash('📝 Annonce créée (non active)', 'info')
            
            return redirect(url_for('annonces'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur: {str(e)}', 'danger')
    
    return render_template('edit_annonce.html', action='nouveau', annonce=None)

@app.route('/annonce/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_annonce(id):
    annonce = Annonce.query.get_or_404(id)
    if request.method == 'POST':
        try:
            ancien_actif = annonce.est_active
            annonce.titre = request.form.get('titre')
            annonce.contenu = request.form.get('contenu')
            annonce.type_annonce = request.form.get('type_annonce')
            annonce.est_active = request.form.get('est_active') == 'true'
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
            
            if annonce.est_active:
                success, message = sync_annonce_to_site(annonce)
                flash('✅ Annonce mise à jour et synchronisée!' if success else f'⚠️ {message}', 
                      'success' if success else 'warning')
            elif ancien_actif and not annonce.est_active:
                delete_from_site('annonce', annonce.id)
                flash('📝 Annonce désactivée', 'info')
            
            return redirect(url_for('annonces'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur: {str(e)}', 'danger')
    
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
        flash('✅ Annonce supprimée', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur: {str(e)}', 'danger')
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
            
            nouvelle = Offre(
                titre=request.form.get('titre'),
                description=request.form.get('description'),
                type_offre=request.form.get('type_offre'),
                lieu=request.form.get('lieu'),
                date_limite=date_limite,
                est_active=request.form.get('est_active') == 'true',
                sync_status='pending'
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            if nouvelle.est_active:
                success, message = sync_offre_to_site(nouvelle)
                flash('✅ Offre créée et synchronisée!' if success else f'⚠️ {message}', 
                      'success' if success else 'warning')
            else:
                flash('📝 Offre créée (non active)', 'info')
            
            return redirect(url_for('offres'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur: {str(e)}', 'danger')
    
    return render_template('edit_offre.html', action='nouveau', offre=None)

@app.route('/offre/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_offre(id):
    offre = Offre.query.get_or_404(id)
    if request.method == 'POST':
        try:
            ancien_actif = offre.est_active
            offre.titre = request.form.get('titre')
            offre.description = request.form.get('description')
            offre.type_offre = request.form.get('type_offre')
            offre.lieu = request.form.get('lieu')
            offre.est_active = request.form.get('est_active') == 'true'
            offre.sync_status = 'pending'
            
            if request.form.get('date_limite'):
                offre.date_limite = datetime.strptime(request.form.get('date_limite'), '%Y-%m-%d').date()
            else:
                offre.date_limite = None
            
            db.session.commit()
            
            if offre.est_active:
                success, message = sync_offre_to_site(offre)
                flash('✅ Offre mise à jour et synchronisée!' if success else f'⚠️ {message}', 
                      'success' if success else 'warning')
            elif ancien_actif and not offre.est_active:
                delete_from_site('offre', offre.id)
                flash('📝 Offre désactivée', 'info')
            
            return redirect(url_for('offres'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur: {str(e)}', 'danger')
    
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
        flash('✅ Offre supprimée', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur: {str(e)}', 'danger')
    return redirect(url_for('offres'))

# --- ROUTES API POUR LE SITE PRINCIPAL ---
@app.route('/api/health')
def api_health():
    site_connected, site_message = check_site_connection()
    return jsonify({
        'status': 'ok',
        'service': 'labmath-admin',
        'timestamp': datetime.utcnow().isoformat(),
        'site_connected': site_connected,
        'site_message': site_message
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

# --- INITIALISATION ---
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Créer les tables
    db.create_all()
    
    # Supprimer les colonnes problématiques
    try:
        db.engine.execute('ALTER TABLE realisations DROP COLUMN IF EXISTS date_modification')
        db.engine.execute('ALTER TABLE activites DROP COLUMN IF EXISTS date_modification')
        db.engine.execute('ALTER TABLE annonces DROP COLUMN IF EXISTS date_modification')
        db.engine.execute('ALTER TABLE offres DROP COLUMN IF EXISTS date_modification')
        print("✅ Colonnes problématiques supprimées")
    except:
        pass
    
    print("✅ Base de données initialisée")
    print(f"🌐 Site principal: {SITE_URL}")
    print(f"🔑 API Key: {'Configurée' if API_KEY else 'Non configurée'}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)