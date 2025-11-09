# =================================================================
# Fichier: app.py (Interface Streamlit et Connexion Sheets)
# =================================================================
import streamlit as st
import gspread 
import pandas as pd 
import time
import random
from typing import List, Dict, Any, Tuple
# Le fichier scraper_iphone.py doit être dans le même dossier !
from scraper_iphone import scrape_model_page, export_to_csv 

# --- CONFIGURATION GOOGLE SHEETS (CORRIGÉE avec ID) ---

# ID de votre feuille de calcul (extrait de l'URL)
SPREADSHEET_ID = "1RQCsS2G_N-KQ-TzuEdY7f3X_7shXhm7w2AjPwaESe84" 
# Nom de l'onglet, confirmé par votre capture d'écran (IMPORTANT : sensible à la casse)
SHEET_NAME = "Feuille 1" 

# --- FONCTION DE LECTURE DES LIENS DEPUIS SHEETS ---

@st.cache_data(ttl=600) 
def load_model_urls_from_sheets():
    """Se connecte à Google Sheets et charge la liste des URLs à scraper."""
    
    if 'gcp_service_account' not in st.secrets:
        st.sidebar.error("❌ Secret 'gcp_service_account' manquant. L'application ne peut pas se connecter.")
        return None

    try:
        # 1. Connexion à Google Sheets via le secret
        gc = gspread.service_account_from_dict(st.secrets['gcp_service_account']) 
        
        # 2. Ouverture de la feuille de calcul par ID (méthode plus fiable)
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # 3. Sélection de l'onglet
        worksheet = sh.worksheet(SHEET_NAME) 

        # 4. Lecture des données dans une liste de dictionnaires
        df = pd.DataFrame(worksheet.get_all_records())
        
        # 5. Définition des noms de colonnes (doivent correspondre EXACTEMENT)
        COL_MODEL = 'Nom du Modele' 
        COL_URL = 'URL de la Categorie' 
        
        if COL_MODEL not in df.columns or COL_URL not in df.columns:
            st.error(f"❌ Colonnes '{COL_MODEL}' ou '{COL_URL}' introuvables dans la feuille '{SHEET_NAME}'.")
            return None
            
        # 6. Extraction et validation des URLs
        model_urls_list = []
        for index, row in df.iterrows():
            model_name = row[COL_MODEL]
            url = row[COL_URL]
            
            # La ligne ne doit pas être vide et l'URL doit commencer par http/https
            if model_name and str(url).strip().lower().startswith("http"):
                model_urls_list.append((model_name, str(url).strip()))

        
        if not model_urls_list:
            # Cette erreur se déclenche si toutes les lignes sont invalides ou si le tableau est vide
            st.error("🛑 Impossible de lancer : La liste de liens chargés est vide. Vérifiez la feuille.")
            return None
            
        st.sidebar.success(f"✅ Chargement réussi : **{len(model_urls_list)}** liens chargés depuis Sheets.")
        
        return model_urls_list

    except Exception as e:
        # Ce message d'erreur est affiché en cas de problème de connexion (permissions, JWT, etc.)
        st.sidebar.error(f"❌ Échec de la connexion Sheets. Vérifiez les permissions de partage et le Secret TOML. Erreur : {e}")
        return None

# --- INTERFACE STREAMLIT PRINCIPALE ---

st.set_page_config(page_title="Scraper Catalogue iPhone", layout="centered")
st.title(" Каталог iPhone Visiodirect")
st.caption("Synchronisation des liens via Google Sheets")

# --- MENU LATÉRAL : PARAMÈTRES DE CALCUL ---
with st.sidebar:
    st.header("⚙️ Ajuster les Paramètres")
    
    marge_brute = st.slider("Coefficient de Marge Brute", 1.0, 3.0, value=1.60, step=0.01)
    frais_mo = st.number_input("Frais Fixes de Main d'Œuvre (€)", 0.0, 100.0, value=20.0, step=1.0)
    tva_coeff = st.number_input("Coefficient de TVA (Ex: 1.20 pour 20%)", 1.0, 3.0, value=1.20, step=0.01)
    
    st.markdown("---")
    st.header("Statut de la Connexion")
    # Lance la vérification de la connexion dès le chargement de l'interface
    model_urls_on_load = load_model_urls_from_sheets()

if st.button("LANCER LE SCRAPING COMPLET", type="primary"):
    
    model_urls_to_scrape = model_urls_on_load # Utilise le résultat de la vérification initiale

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
                label=" Télécharger le CSV final",
                data=csv_output,
                file_name="resultats_catalogue_iphone.csv",
                mime="text/csv",
            )
            st.balloons()
        else:
            log_status.error("Erreur lors de la génération du fichier CSV (aucune donnée trouvée).")

# Fin du fichier app.py
