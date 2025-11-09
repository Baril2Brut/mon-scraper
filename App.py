# =================================================================
# Fichier: App.py (Interface Streamlit et Connexion Sheets)
# =================================================================
import streamlit as st
import gspread 
import gspread_dataframe as gd 
import pandas as pd 
import time
import random
import json # <-- NÉCESSAIRE pour charger la chaîne JSON du secret
from typing import List, Dict, Any, Tuple
# Le fichier scraper_iphone.py doit être dans le même dossier !
from scraper_iphone import scrape_model_page, export_to_csv 

# --- CONFIGURATION GOOGLE SHEETS ---

# ID de votre feuille de calcul (extrait de l'URL)
SPREADSHEET_ID = "1RQCsS2G_N-KQ-TzuEdY7f3X_7shXhm7w2AjPwaESe84" 
# Nom de l'onglet (IMPORTANT : sensible à la casse)
SHEET_NAME = "Configuration_Liens_Scraper" # J'utilise le nom que l'application recherche

# Noms de colonnes cibles
COL_MODEL = 'MODELE'
COL_URL = 'URL'


# --- FONCTION DE LECTURE DES LIENS DEPUIS SHEETS (AVEC gspread-dataframe) ---

@st.cache_data(ttl=600, show_spinner="Chargement et vérification des liens depuis Google Sheets...") 
def load_model_urls_from_sheets():
    """
    Se connecte à Google Sheets et charge la liste des URLs à scraper.
    Utilise la méthode la plus robuste : lire les secrets TOML à plat.
    """
    
    # Clés requises pour le compte de service
    REQUIRED_GCP_KEYS = ["type", "project_id", "private_key_id", "private_key", "client_email", "client_id", "auth_uri", "token_uri", "auth_provider_x509_cert_url", "client_x509_cert_url", "universe_domain"]
    
    service_account_info: Dict[str, str] = {}

    try:
        # Tenter la méthode la plus robuste : lire les clés individuelles (structure plate dans secrets.toml)
        if all(key in st.secrets for key in REQUIRED_GCP_KEYS):
             print("DEBUG: Utilisation des secrets GCP via la structure TOML plate.")
             for key in REQUIRED_GCP_KEYS:
                 service_account_info[key] = st.secrets[key]
        
        # Fallback pour l'ancienne méthode (chaîne JSON sous la clé 'gcp_service_account')
        elif 'gcp_service_account' in st.secrets and isinstance(st.secrets['gcp_service_account'], str):
            print("DEBUG: Utilisation des secrets GCP via la chaîne JSON ('gcp_service_account').")
            json_key_string = st.secrets["gcp_service_account"]
            # Ceci est la ligne qui échoue avec 'Invalid control character'
            service_account_info = json.loads(json_key_string)
            
        else:
             st.error("🛑 Le secret de service GCP n'est pas configuré. Vérifiez que toutes les clés sont présentes.")
             return []

        if not service_account_info:
            st.error("🛑 Le secret de service GCP n'est pas configuré. Vérifiez que toutes les clés sont présentes.")
            return []

        # Connexion à Google Sheets via le compte de service
        # Cette ligne est le point de vérité pour le secret TOML.
        gc = gspread.service_account_from_dict(service_account_info)
        print("DEBUG: Connexion gspread réussie.")

        # 3. Ouvrir le document et l'onglet
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        print(f"DEBUG: Feuille de calcul '{SHEET_NAME}' ouverte.")

        # 4. Lecture des données
        df = gd.get_as_dataframe(worksheet, header=1) # On assume que la première ligne est l'en-tête
        # ... (reste du code de lecture)

        print(f"DEBUG: Données chargées. {len(df)} lignes trouvées.")

        # 5. Nettoyage et filtrage des URLs valides
        df = df.dropna(subset=[COL_MODEL, COL_URL]).reset_index(drop=True)
        # S'assurer que les URLs commencent par l'URL de base ou le protocole
        df = df[df[COL_URL].str.startswith('http', na=False) | df[COL[URL].str.startswith('/', na=False)]]
        
        model_urls_to_scrape = list(zip(df[COL_MODEL], df[COL_URL]))

        if not model_urls_to_scrape:
            st.warning("⚠️ La feuille est vide ou ne contient aucun lien valide à scraper.")
        
        print(f"DEBUG: **{len(model_urls_to_scrape)}** liens modèles à scraper trouvés après filtrage.")
        return model_urls_to_scrape

    except RuntimeError as re:
        # Erreur spécifique levée pour le problème de parsing JSON
        st.error(f"❌ Échec critique du chargement des secrets. Veuillez utiliser le format TOML simple (clé=valeur). Erreur : {re}")
        return []

    except Exception as e:
        print(f"DEBUG: Échec de la connexion Sheets. Erreur : {e}")
        # Message d'erreur ajusté pour l'étape de debug
        st.error(f"❌ Échec de la connexion Sheets. Vérifiez les permissions de partage et le Secret TOML. Erreur : {e}")
        return []


# --- INTERFACE STREAMLIT ---

st.set_page_config(
    page_title="iPhone Spares Scraper",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🤖 iPhone Spares Scraper & Repricing")
st.subheader("Extraction des composants et calcul automatique des prix de vente.")


# --- CONFIGURATION DANS LA BARRE LATÉRALE ---

st.sidebar.header("Paramètres de Repricing")

# 1. Marge Brute (multiplicateur)
marge_brute = st.sidebar.slider(
    'Marge Brute (Multiplicateur)', 
    min_value=1.0, 
    max_value=3.0, 
    value=1.6, 
    step=0.01,
    help="Multiplie le prix d'achat HT pour obtenir le prix de vente HT avant Frais/TVA (ex: 1.6 = 60% de marge brute)."
)

# 2. Frais fixes de Main d'Œuvre
frais_mo = st.sidebar.slider(
    "Frais Fixes de Main d'Œuvre (€)", 
    min_value=0.0, 
    max_value=50.0, 
    value=20.0, 
    step=0.5,
    help="Montant fixe ajouté au prix après l'application de la marge brute (ex: 20.0 €)."
)

# 3. Coefficient TVA
tva_coeff = st.sidebar.slider(
    'Coefficient TVA', 
    min_value=1.0, 
    max_value=1.3, 
    value=1.2, 
    step=0.01,
    help="Coefficient appliqué pour obtenir le prix TTC (ex: 1.2 = 20% de TVA)."
)

st.sidebar.info("Cliquez sur 'Lancer le Scraping' pour appliquer ces paramètres.")


# --- BOUTON DE DÉMARRAGE ---

if st.button("▶️ Lancer le Scraping", type="primary"):
    
    model_urls_to_scrape = load_model_urls_from_sheets()
    
    if not model_urls_to_scrape:
        st.error("🛑 Impossible de lancer : Aucun lien valide n'a pu être chargé depuis Google Sheets.")
    else:
        st.info(f"🚀 Démarrage du scraping de **{len(model_urls_to_scrape)}** modèles...")
        
        toutes_les_donnees: List[Dict[str, Any]] = []
        log_status = st.status('Scraping et traitement en cours...', expanded=True)
        
        # 2. Boucle et appelle la fonction de scraping
        for model_name, model_url in model_urls_to_scrape:
            # Délai entre les modèles
            time.sleep(random.uniform(2.0, 5.0)) 
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
                label=" ⬇️ Télécharger le CSV final",
                data=csv_output,
                file_name="resultats_catalogue_iphone.csv",
                mime="text/csv",
                type="secondary"
            )
        else:
            log_status.error("❌ Échec de la génération du CSV.")
