# =================================================================
# Fichier: app.py (Interface Streamlit et Connexion Sheets)
# =================================================================
import streamlit as st
import gspread # Pour se connecter à Google Sheets
import pandas as pd # Pour gérer les données
import time
import random
from typing import List, Dict, Any, Tuple
from scraper_iphone import scrape_model_page, export_to_csv # Importe les fonctions du Scraper

# --- CONFIGURATION GOOGLE SHEETS ---
# URL complète fournie par l'utilisateur
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1RQCsS2G_N-KQ-TzuEdY7f3X_7shXhm7w2AjPwaESe84/edit?usp=drivesdk" 
# Nom de l'onglet (feuille) où sont les liens, par défaut "Feuille 1"
SHEET_NAME = "Feuille 1" 

# --- FONCTION DE LECTURE DES LIENS DEPUIS SHEETS ---

@st.cache_data(ttl=600) # Mise en cache (recharge après 10 minutes ou si l'app est redémarrée)
def load_model_urls_from_sheets():
    """Se connecte à Google Sheets via les secrets et charge la liste des URLs à scraper."""
    
    if 'gcp_service_account' not in st.secrets:
        st.sidebar.error("❌ Secret 'gcp_service_account' manquant. Configuré ?")
        return None

    try:
        # 1. Connexion à Google Sheets
        gc = gspread.service_account_from_dict(st.secrets['gcp_service_account']) 
        
        # 2. Ouverture de la feuille de calcul
        sh = gc.open_by_url(SPREADSHEET_URL)
        
        # 3. Sélection de l'onglet
        worksheet = sh.worksheet(SHEET_NAME) 

        # 4. Lecture des données dans un DataFrame (utilise la première ligne comme en-tête)
        df = pd.DataFrame(worksheet.get_all_records())
        
        # 5. Vérification et extraction des colonnes
        COL_MODEL = 'Nom du Modèle' 
        COL_URL = 'URL de la Catégorie' 
        
        if COL_MODEL not in df.columns or COL_URL not in df.columns:
            st.error(f"❌ Colonnes '{COL_MODEL}' ou '{COL_URL}' introuvables. Vérifiez les titres dans Sheets.")
            return None
            
        # Filtrage des lignes vides et création de la liste de tuples : (Nom du Modèle, URL)
        model_urls_list = list(df[[COL_MODEL, COL_URL]].dropna().itertuples(index=False, name=None))
        
        st.sidebar.success(f"✅ Chargement réussi : **{len(model_urls_list)}** liens chargés depuis Sheets.")
        
        return model_urls_list

    except Exception as e:
        st.sidebar.error(f"❌ Erreur connexion Sheets. Partage, URL ou Clé invalide : {e}")
        return None

# --- INTERFACE STREAMLIT PRINCIPALE ---

st.set_page_config(
    page_title="Scraper Catalogue iPhone", 
    layout="centered"
)

st.title(" Каталог iPhone Visiodirect")
st.caption("Synchronisation des liens via Google Sheets")

# --- MENU LATÉRAL : PARAMÈTRES DE CALCUL ---
with st.sidebar:
    st.header("⚙️ Ajuster les Paramètres")
    
    marge_brute = st.slider(
        "Coefficient de Marge Brute", 
        1.0, 3.0, 
        value=1.60, 
        step=0.01,
        help="1.60 = 60% de marge. Prix HT x 1.60"
    )
    frais_mo = st.number_input(
        "Frais Fixes de Main d'Œuvre (€)", 
        0.0, 100.0, 
        value=20.0,
        step=1.0
    )
    tva_coeff = st.number_input(
        "Coefficient de TVA (Ex: 1.20 pour 20%)", 
        1.0, 3.0, 
        value=1.20,
        step=0.01
    )
    st.markdown("---")
    st.header("Statut de la Connexion")
    # Laisse l'espace pour le feedback de load_model_urls_from_sheets
    
if st.button("LANCER LE SCRAPING COMPLET", type="primary"):
    
    # 1. Tente de charger la liste des URLs
    model_urls_to_scrape = load_model_urls_from_sheets()

    if not model_urls_to_scrape:
        st.error("🛑 Impossible de lancer : Aucun lien valide n'a pu être chargé depuis Google Sheets.")
        st.warning("Veuillez vérifier que le secret est correct et que l'URL est partagée.")
    else:
        st.info(f"🚀 Démarrage du scraping de **{len(model_urls_to_scrape)}** modèles...")
        
        toutes_les_donnees: List[Dict[str, Any]] = []
        
        # Conteneur pour afficher les logs en temps réel
        log_status = st.status('Scraping et traitement en cours...', expanded=True)
        
        # 2. Boucle et appelle la fonction de scraping pour chaque modèle
        for model_name, model_url in model_urls_to_scrape:
            
            # Délai aléatoire entre 2.0 et 5.0 secondes entre les modèles
            time.sleep(random.uniform(2.0, 5.0)) 
            
            # Appel de la fonction de scraping (on lui passe le conteneur Streamlit pour les logs)
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
            log_status.error("Erreur lors de la génération du fichier CSV.")
