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

# Correction impérative pour PostgreSQL sur Render
database_url = os.environ.get('DATABASE_URL', 'sqlite:///labmath_db.sqlite')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Initialisation de la base de données
db = SQLAlchemy(app)

# Configuration pour l'API du site principal (conservée pour info)
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

# --- MODÈLES SANS SYNC_ID ---
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
    # sync_id = db.Column(db.String(100))  # SUPPRIMÉ - Cause l'erreur

class Realisation(db.Model):
    __tablename__ = 'realisations'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    categorie = db.Column(db.String(100))
    date_realisation = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    # sync_id = db.Column(db.String(100))  # SUPPRIMÉ

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
    # sync_id = db.Column(db.String(100))  # SUPPRIMÉ

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
    # sync_id = db.Column(db.String(100))  # SUPPRIMÉ

# --- FONCTIONS DE SYNCHRONISATION (DÉSACTIVÉES) ---

def sync_activite(activite):
    """Synchronisation désactivée - mode maintenance"""
    return True, "Synchronisation désactivée (mode maintenance)"

def sync_realisation(realisation):
    """Synchronisation désactivée - mode maintenance"""
    return True, "Synchronisation désactivée (mode maintenance)"

def sync_annonce(annonce):
    """Synchronisation désactivée - mode maintenance"""
    return True, "Synchronisation désactivée (mode maintenance)"

def sync_offre(offre):
    """Synchronisation désactivée - mode maintenance"""
    return True, "Synchronisation désactivée (mode maintenance)"

def delete_from_site(model, sync_id):
    """Suppression désactivée - mode maintenance"""
    return True, "Suppression désactivée (mode maintenance)"

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
            'offres_active': Offre.query.filter_by(est_active=True).count()
        }
        
        # Vérification de la connexion au site principal (optionnelle)
        site_connected = False
        try:
            response = requests.get(f"{SITE_URL}/api/health", timeout=3)
            site_connected = response.status_code == 200
        except:
            site_connected = False
        
        stats['site_connected'] = site_connected
        
        # Récupérer les 5 derniers éléments
        recent_activities = Activite.query.order_by(Activite.date_creation.desc()).limit(5).all()
        recent_annonces = Annonce.query.order_by(Annonce.date_creation.desc()).limit(5).all()
        
        return render_template('dashboard.html',
                              stats=stats,
                              now=datetime.utcnow(),
                              site_url=SITE_URL,
                              recent_activities=recent_activities,
                              recent_annonces=recent_annonces)
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
            
            # Message simplifié sans synchronisation
            if est_publie:
                flash('Activité créée et publiée!', 'success')
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
            activite.titre = request.form.get('titre')
            activite.description = request.form.get('description')
            activite.contenu = request.form.get('contenu')
            activite.image_url = request.form.get('image_url')
            activite.est_publie = request.form.get('est_publie') == 'true'
            activite.date_modification = datetime.utcnow()
            
            db.session.commit()
            
            flash('Activité mise à jour avec succès!', 'success')
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
    flash('Synchronisation désactivée (mode maintenance)', 'info')
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
            
            flash('Réalisation créée avec succès!', 'success')
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
            
            flash('Réalisation mise à jour avec succès!', 'success')
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
            
            if est_active:
                flash('Annonce créée et active!', 'success')
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
            
            flash('Annonce mise à jour avec succès!', 'success')
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
            
            if est_active:
                flash('Offre créée et active!', 'success')
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
            
            flash('Offre mise à jour avec succès!', 'success')
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
        db.session.delete(offre)
        db.session.commit()
        flash('Offre supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('offres'))

# --- ROUTES DE SYNCHRONISATION MANUELLE (DÉSACTIVÉES) ---

@app.route('/sync/all')
@login_required
def sync_all():
    flash('Synchronisation désactivée (mode maintenance)', 'info')
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
    db.session.rollback()
    if 'user_id' in session:
        return render_template('500.html', error=str(e)), 500
    return redirect(url_for('login'))

# --- INITIALISATION ---
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Créer les tables SANS sync_id
    try:
        db.create_all()
        print("✅ Base de données initialisée avec succès (mode maintenance)")
        print("📁 Dossier templates:", app.template_folder)
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation: {str(e)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))

    app.run(host='0.0.0.0', port=port, debug=True)
