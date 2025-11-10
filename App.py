# =================================================================
# Fichier: app.py (Interface Streamlit et Connexion Sheets)
# =================================================================
import streamlit as st
import gspread 
import gspread_dataframe as gd 
import pandas as pd 
import time
import random 
import io 
import json # Ajout de json ici
from typing import List, Dict, Any, Tuple
# Le fichier scraper_iphone.py doit être dans le même dossier !
from scraper_iphone import scrape_model_page, export_to_csv 

# --- CONFIGURATION GOOGLE SHEETS ---

# ID de votre feuille de calcul (extrait de l'URL)
SPREADSHEET_ID = "1RQCsS2G_N-KQ-TzuEdY7f3X_7shHhm7w2AjPwaESe84" 
# Nom de l'onglet (IMPORTANT : sensible à la casse)
SHEET_NAME = "Configuration_Liens_Scraper" 

# Noms de colonnes cibles
COL_MODEL = 'MODELE'
COL_URL = 'URL'

# Délai fixe après chaque scraping (pour ne pas surcharger le site cible)
SCRAPING_DELAY_SECONDS = 2.0


# --- FONCTION DE LECTURE DES LIENS DEPUIS SHEETS (AVEC gspread-dataframe) ---

@st.cache_data(ttl=600, show_spinner="Chargement et vérification des liens depuis Google Sheets...") 
def load_model_urls_from_sheets():
    """
    Se connecte à Google Sheets et charge la liste des URLs à scraper.
    Utilise la méthode robuste io.StringIO pour contourner les problèmes de formatage
    de la clé privée dans l'environnement Streamlit.
    """
    
    if 'gcp_service_account' not in st.secrets:
        print("DEBUG: Secret 'gcp_service_account' non trouvé dans st.secrets.")
        st.error("🛑 Erreur d'authentification: La section '[gcp_service_account]' est manquante dans secrets.toml.")
        return []
    
    try:
        creds_json = st.secrets['gcp_service_account']
        
        # FIX pour l'erreur 'AttrDict is not JSON serializable' : convertir l'objet secret en dictionnaire standard
        creds_dict = dict(creds_json)
        
        json_string = json.dumps(creds_dict)
        
        # Utilisation d'un objet de type fichier en mémoire (StringIO)
        creds_file_like = io.StringIO(json_string)
        
        # --- CORRECTION DE L'ERREUR CLÉ ---
        # gspread.service_account utilise 'filename' pour lire un objet de type fichier,
        # et non 'file_path' (qui était la source de l'erreur).
        gc = gspread.service_account(filename=creds_file_like)
        
        print("DEBUG: Connexion à Google Sheets réussie via StringIO (méthode robuste).")
        
    except Exception as e:
        print(f"DEBUG: Erreur lors de l'authentification : {e}")
        st.error(f"🛑 Erreur critique d'authentification. Veuillez vérifier que la clé privée dans secrets.toml ne contient aucun caractère invisible. Erreur : {e}")
        return []

    # --- LECTURE DES DONNÉES ---
    try:
        # Ouvrir la feuille de calcul
        wks = gc.open_by_id(SPREADSHEET_ID).worksheet(SHEET_NAME)
        
        # Lire les données dans un DataFrame
        df = gd.get_as_dataframe(wks, usecols=[COL_MODEL, COL_URL], header=0)
        
        # Nettoyage et filtrage
        df = df.dropna(subset=[COL_MODEL, COL_URL]).reset_index(drop=True)
        # Supprime les lignes où l'URL n'est pas une chaîne valide ou est vide
        df = df[df[COL_URL].astype(str).str.startswith('http')].reset_index(drop=True)
        
        print(f"DEBUG: {len(df)} liens valides chargés depuis la feuille '{SHEET_NAME}'.")

        # Convertir en liste de tuples (MODÈLE, URL)
        model_urls_to_scrape: List[Tuple[str, str]] = list(zip(
            df[COL_MODEL].astype(str).tolist(), 
            df[COL_URL].astype(str).tolist()
        ))
        
        return model_urls_to_scrape
    
    except gspread.exceptions.WorksheetNotFound:
        print(f"DEBUG: Erreur de feuille: L'onglet '{SHEET_NAME}' est introuvable.")
        st.error(f"🛑 Erreur: L'onglet Google Sheets **'{SHEET_NAME}'** est introuvable. Vérifiez l'orthographe (sensible à la casse).")
        return []
    except Exception as e:
        print(f"DEBUG: Erreur lors de la lecture de la feuille: {e}")
        st.error(f"🛑 Erreur lors du chargement des données depuis Google Sheets : {e}")
        return []


# --- INTERFACE STREAMLIT PRINCIPALE ---

st.set_page_config(
    page_title="VisioDirect Scraper",
    page_icon="📱",
    layout="wide"
)

st.title("💰 Outil de Repricing & Scraping de Composants iPhone")
st.markdown("Cet outil se connecte à Google Sheets, scrape les prix pour les liens fournis, et applique votre stratégie de marge.")

# --- SIDEBAR (PARAMÈTRES DE REPRICING) ---

st.sidebar.title("🛠️ Paramètres de Repricing")

# 1. Marge brute (Multiplicateur)
st.sidebar.subheader("1. Marge Brute")
marge_brute = st.sidebar.slider(
    "Multiplicateur de Marge Brute (1.x)",
    min_value=1.1, 
    max_value=2.5, 
    value=1.60, 
    step=0.01,
    help="Exemple : 1.60 pour 60% de marge brute sur le prix fournisseur HT."
)
st.sidebar.info(f"Marge Nette : **{((marge_brute - 1) * 100):.0f}%**")

# 2. Frais fixes (Main d'Œuvre)
st.sidebar.subheader("2. Frais Fixes M.O.")
frais_mo = st.sidebar.number_input(
    "Frais de Main d'Œuvre fixes (€ HT)",
    min_value=0.0,
    value=20.0,
    step=1.0,
    format="%.2f",
    help="Ces frais HT sont ajoutés à chaque composant pour calculer le prix intermédiaire."
)

# 3. TVA
st.sidebar.subheader("3. Taux de TVA")
tva_coeff = st.sidebar.slider(
    "Coefficient TVA (1.xx)",
    min_value=1.00,
    max_value=1.30,
    value=1.20,
    step=0.01,
    help="Exemple : 1.20 pour 20% de TVA. Ce coefficient est appliqué à la fin pour le Prix Client TTC."
)


# --- LOGIQUE PRINCIPALE ---

if st.button("▶️ Démarrer le Scraping et le Repricing"):
    
    # 1. Chargement des URLs
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
                label=" ⬇️ Télécharger le CSV final",
                data=csv_output,
                file_name="resultats_catalogue_iphone.csv",
                mime="text/csv",
                key='download-csv-key',
                use_container_width=True
            )
            
            st.success("Fichier CSV généré. Vous pouvez le télécharger ci-dessus.")
        else:
            log_status.error("❌ Échec de l'exportation du CSV. Aucune donnée n'a été récupérée.")
