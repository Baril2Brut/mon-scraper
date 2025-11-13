# =================================================================
# Fichier: app.py (Interface Streamlit et Connexion Sheets)
# =================================================================
import streamlit as st
import gspread
import json
import base64
import gspread_dataframe as gd 
import pandas as pd 
import time
from typing import List, Dict, Any
# Le fichier scraper_iphone.py doit être dans le même dossier !
from scraper_iphone import scrape_model_page, export_to_csv 

# --- CONFIGURATION GOOGLE SHEETS ---

# ID de votre feuille de calcul (extrait de l'URL)
SPREADSHEET_ID = "1RQCsS2G_N-KQ-TzuEdY7f3X_7shXhm7w2AjPwaESe84" 
# Nom de l'onglet (IMPORTANT : sensible à la casse)
SHEET_NAME = "Configuration_Liens_Scraper" 

# Noms de colonnes cibles
COL_MODEL = 'MODELE'
COL_URL = 'URL'

# Délais de scraping (pour être plus doux avec le site)
SCRAPING_DELAY_SECONDS = 2.0


# --- FONCTION DE LECTURE DES LIENS DEPUIS SHEETS (VERSION SIMPLIFIÉE) ---

@st.cache_data(ttl=600, show_spinner="Chargement et vérification des liens depuis Google Sheets...") 
def load_model_urls_from_sheets():
    """
    Se connecte à Google Sheets et charge la liste des URLs à scraper.
    Utilise la clé de service depuis st.secrets.
    """
    
    # --- 1. Lecture et Décodage Base64 de la Clé ---
    if 'gcp_encoded_key' not in st.secrets:
        st.error("🛑 Clé 'gcp_encoded_key' manquante dans secrets.toml")
        print("ERROR: Secret 'gcp_encoded_key' not found.")
        return []

    encoded_key = st.secrets['gcp_encoded_key']

    try:
        # Décodage Base64
        service_account_info_bytes = base64.b64decode(encoded_key)
        service_account_info_str = service_account_info_bytes.decode('utf-8')
        creds_dict = json.loads(service_account_info_str)
        print("DEBUG: Clé de service décodée avec succès.")
    except Exception as e:
        st.error(f"🛑 Erreur de décodage. Erreur : {e}")
        print(f"ERROR: Decoding error. {e}")
        return []

    # --- 2. Authentification gspread ---
    try:
        # Authentification avec le dictionnaire chargé en mémoire
        gc = gspread.service_account_from_dict(creds_dict)
        print("DEBUG: Authentification gspread réussie.")

        # Ouverture de la feuille
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(SHEET_NAME)
        print(f"DEBUG: Ouverture de la feuille '{SHEET_NAME}' réussie.")
        
        # Lecture en DataFrame
        df = gd.get_as_dataframe(ws)

        # Nettoyage et filtrage : retire les lignes vides ou sans URL
        df = df.dropna(subset=[COL_MODEL, COL_URL], how='all')
        df = df[df[COL_URL].astype(str).str.startswith('http')].copy()

        # Retourne les paires (MODELE, URL)
        model_urls = list(zip(
            df[COL_MODEL].astype(str).tolist(),
            df[COL_URL].astype(str).tolist()
        ))
        
        print(f"DEBUG: {len(model_urls)} URLs valides chargées.")
        return model_urls
        
    except gspread.exceptions.NoValidUrlKeyFound:
        st.error("🛑 Erreur : L'ID de la feuille de calcul (SPREADSHEET_ID) n'est pas valide ou les autorisations ne sont pas définies.")
        print("ERROR: Invalid Spreadsheet ID or permissions are wrong.")
        return []
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"🛑 Erreur : L'onglet '{SHEET_NAME}' n'existe pas dans la feuille de calcul.")
        print(f"ERROR: Worksheet '{SHEET_NAME}' not found.")
        return []
    except Exception as e:
        st.error(f"🛑 Échec de la connexion à Google Sheets. Vérifiez les autorisations du compte de service. Erreur : {e}")
        print(f"ERROR: Google Sheets connection failed. {e}")
        return []


# --- LOGIQUE DE L'APPLICATION STREAMLIT ---

st.set_page_config(
    page_title="Scraper de Catalogue iPhone (VisioDirect)", 
    layout="wide"
)

# Sidebar pour les paramètres (Repricing)
st.sidebar.title("🛠️ Paramètres de Repricing")

# Valeurs par défaut des paramètres du scraper (synchronisées avec scraper_iphone.py)
DEFAULT_MARGE = 1.60
DEFAULT_FRAIS_MO = 20.0
DEFAULT_TVA = 1.20

marge_brute = st.sidebar.slider(
    'Marge Brute (Multiplicateur)', 
    min_value=1.1, max_value=2.5, 
    value=DEFAULT_MARGE, step=0.01,
    help=f"Ex: 1.60 = 60% de marge sur le coût fournisseur HT."
)
frais_mo = st.sidebar.number_input(
    "Frais de Main d'Œuvre Fixes (€ HT)", 
    min_value=0.0, 
    value=DEFAULT_FRAIS_MO, 
    step=5.0
)
tva_coeff = st.sidebar.slider(
    'Coefficient TVA (Multiplicateur)', 
    min_value=1.0, max_value=1.3, 
    value=DEFAULT_TVA, step=0.01,
    help=f"Ex: 1.20 = 20% de TVA pour convertir HT en TTC."
)
st.sidebar.markdown("---")

# Fonction pour le bouton de lancement
if st.sidebar.button("⚙️ Lancer le Scraping"):
    # Réinitialise le cache pour forcer la relecture des secrets (important si les secrets sont modifiés)
    load_model_urls_from_sheets.clear()
    
    st.title("🤖 Scraper de Catalogue Pièces Détachées")
    st.markdown("---")
    
    # 1. Chargement des liens
    model_urls_to_scrape = load_model_urls_from_sheets()

    if not model_urls_to_scrape:
        st.error("🛑 Impossible de lancer : Aucun lien valide n'a pu être chargé depuis Google Sheets.")
    else:
        st.info(f"🚀 Démarrage du scraping de **{len(model_urls_to_scrape)}** modèles...")
        
        toutes_les_donnees: List[Dict[str, Any]] = []
        log_status = st.status('Scraping et traitement en cours...', expanded=True)
        
        # 2. Boucle et appelle la fonction de scraping
        for model_name, model_url in model_urls_to_scrape:
            # Délai fixe pour être poli avec le serveur
            time.sleep(SCRAPING_DELAY_SECONDS) 
            scrape_model_page(model_name, model_url, toutes_les_donnees, log_status) 
        
        log_status.update(label="Traitement final des données...", state="running", expanded=True)
        
        # 3. Exportation et Repricing (utilise les paramètres du sidebar)
        csv_output = export_to_csv(
            toutes_les_donnees, 
            marge_brute, 
            frais_mo, 
            tva_coeff
        )
        
        if csv_output:
            log_status.success(f"🎉 Processus terminé ! **{len(toutes_les_donnees)}** composants extraits et calculés.")
            
            st.download_button(
                label="📥 Télécharger le CSV final",
                data=csv_output,
                file_name="resultats_catalogue_iphone.csv",
                mime="text/csv;charset=utf-8-sig",
                use_container_width=True
            )
        else:
            log_status.error("❌ Échec de la génération du CSV. Le scraping n'a retourné aucune donnée.")
            
# Interface par défaut
if 'gcp_service_account' not in st.secrets:
    st.title("🤖 Scraper de Catalogue Pièces Détachées (Configuration requise)")
    st.warning("Veuillez configurer votre clé de service Google dans le fichier `.streamlit/secrets.toml`")
    st.markdown("### Format requis dans secrets.toml :")
    st.code('''[gcp_service_account]
type = "service_account"
project_id = "votre-project-id"
private_key_id = "votre-private-key-id"
private_key = """-----BEGIN PRIVATE KEY-----
...votre clé privée...
-----END PRIVATE KEY-----"""
client_email = "votre-email@project.iam.gserviceaccount.com"
client_id = "votre-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
universe_domain = "googleapis.com"''', language='toml')
elif st.session_state.get('scraped', False) is False:
    st.title("🤖 Scraper de Catalogue Pièces Détachées")
    st.info("Cliquez sur **Lancer le Scraping** dans la barre latérale pour démarrer le processus.")
    # On fait un appel initial pour vérifier l'authentification et afficher les erreurs plus tôt
    load_model_urls_from_sheets()
