import requests
from bs4 import BeautifulSoup
import re
import csv
import time
import math 
import random 
from typing import List, Dict, Any, Tuple
import io 
import streamlit as st 
import pandas as pd 
import gspread
import gspread_dataframe as gd
from datetime import datetime 

# --- CONFIGURATION PRINCIPALE ET SECRETS CLOUD ---

# Cette liste sert de base uniquement la première fois que l'application est lancée.
DEFAULT_MODEL_URLS: List[Tuple[str, str]] = [
    # iPhone 15 Series
    ("iPhone 15 Pro Max", "http://www.visiodirect-mobile.com/iphone-15-pro-max-ssf1301-fss2-fcss4.html"),
    ("iPhone 15 Pro", "http://www.visiodirect-mobile.com/iphone-15-pro-ssf1300-fss2-fcss4.html"),
    ("iPhone 15 Plus", "http://www.visiodirect-mobile.com/iphone-15-plus-ssf1299-fss2-fcss4.html"),
    ("iPhone 15", "http://www.visiodirect-mobile.com/iphone-15-ssf1298-fss2-fcss4.html"),
    # iPhone 14 Series (À compléter ou supprimer après importation)
    ("iPhone 14 Pro Max", "http://www.visiodirect-mobile.com/iphone-14-pro-max-ssf1297-fss2-fcss4.html"),
    ("iPhone 14 Pro", "http://www.visiodirect-mobile.com/iphone-14-pro-ssf1296-fss2-fcss4.html"),
    ("iPhone 14 Plus", "http://www.visiodirect-mobile.com/iphone-14-plus-ssf1086-fss2-fcss4.html"),
    ("iPhone 14", "http://www.visiodirect-mobile.com/iphone-14-ssf1085-fss2-fcss4.html"),
] 

PRODUCT_CONTAINER_SELECTOR: str = 'div.cadre_prod'
BASE_URL: str = "http://www.visiodirect-mobile.com"
GSHEET_NAME: str = "Resultats_Scraping_iPhone_Automatise" # <--- IMPORTANT : CHANGEZ CECI PAR LE NOM EXACT DE VOTRE FEUILLE GOOGLE SHEET


# --- FONCTIONS UTILITAIRES DE BASE ---

@st.cache_data 
def clean_price(price_raw: str) -> float:
    """
    Nettoie une chaîne de prix pour la convertir en nombre flottant (float).
    
    CORRECTION MAJEURE: Ajoute une logique de division par 100 si la valeur 
    extraite semble être en centimes (ce qui cause le décalage x100).
    """
    if price_raw == "N/A": return 0.0
    
    # Étape 1: Nettoyage des caractères non numériques et uniformisation des décimales
    cleaned_price_str = price_raw.lower().replace('€', '').replace('ttc', '').strip()
    
    # Logique pour gérer les formats:
    if ',' in cleaned_price_str and '.' in cleaned_price_str:
        # Format FR avec séparateur de milliers (.) et séparateur décimal (,)
        cleaned_price_str = cleaned_price_str.replace('.', '').replace(',', '.')
    elif ',' in cleaned_price_str:
        # Format FR simple (ex: 12,34)
        cleaned_price_str = cleaned_price_str.replace(',', '.')
    elif '.' in cleaned_price_str and cleaned_price_str.count('.') > 1:
        # Format EN avec séparateur de milliers (,) et décimal (.) - Peu probable ici, mais sécurisé
        cleaned_price_str = cleaned_price_str.replace('.', '') 
    elif '.' in cleaned_price_str and cleaned_price_str.count('.') == 1:
        # Format EN simple (ex: 12.34) - Laisser le point décimal
        pass # <-- Correction de l'IndentationError
        
    cleaned_price_str = re.sub(r'[^\d.]', '', cleaned_price_str) # Suppression finale de tout sauf chiffres et point

    try: 
        final_price = float(cleaned_price_str)
        
        # --- CORRECTION APPLIQUÉE ICI ---
        # Si le prix est > 100 et que l'original ne contenait pas de point/virgule, on divise par 100
        # pour corriger la lecture en centimes.
        if final_price > 1000.0 and (not any(c in price_raw for c in [',', '.'])): 
             return final_price / 100.0
        # --- FIN CORRECTION ---
        
        return final_price
    except ValueError: 
        return 0.0

def get_soup(url: str, max_retries: int = 3, log_func=st.warning) -> BeautifulSoup | None:
    """Télécharge l'URL et retourne l'objet Beautiful Soup, avec des tentatives en cas d'échec."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status() 
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            log_func(f"    [TENTATIVE {attempt + 1}/{max_retries}] Échec de la requête. Erreur: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
    return None

def scrape_model_page_streamlit(model_name: str, model_url: str, log_func) -> List[Dict[str, Any]]:
    """Visite la page du modèle et extrait tous les composants (produits)."""
    
    log_func(f"**🔎 Démarrage du scraping des composants pour {model_name}...**")
    
    all_products_for_model: List[Dict[str, Any]] = []
    current_page = 1
    total_pages = 1 
    
    while current_page <= total_pages:
        url = model_url.replace(".html", f"-p{current_page}.html") if current_page > 1 else model_url
        log_func(f"  -> Page {current_page}/{total_pages} : {url}")
        
        soup = get_soup(url, log_func=log_func) 
        if not soup: break
            
        products_on_page = []
        product_containers = soup.select(PRODUCT_CONTAINER_SELECTOR)
        if not product_containers and current_page == 1:
            log_func(f"  [AVERTISSEMENT] Aucun composant trouvé pour {model_name} (Page 1).")
            break 
        
        # Extraction des données
        for container in product_containers:
            try:
                name_tag = container.select_one('h3') or container.select_one('h4')
                name = name_tag.text.strip() if name_tag else "N/A"
                
                link_tag = container.find('a', href=True)
                link = BASE_URL + link_tag['href'] if link_tag and link_tag['href'].startswith('/') else link_tag['href'] if link_tag else "N/A"
                
                price_tag = container.select_one('.price_item') or container.select_one('.prix')
                price_raw = price_tag.text.strip() if price_tag else "N/A"
                price_float = clean_price(price_raw)
                
                reference = "N/A"
                ref_text_match = container.find(string=re.compile(r'Réf\. :'))
                if ref_text_match:
                    reference = ref_text_match.split(':', 1)[1].strip()

                products_on_page.append({
                    'marque_modele': model_name, 
                    'nom_composant': name,
                    'reference': reference,
                    'price_float': price_float, 
                    'price_raw': price_raw,     
                    'link': link
                })
            except Exception as e: 
                 log_func(f"    [ERREUR Extraction] Échec sur un produit de la page {current_page}: {e}")
                 continue

        # Gestion de la pagination 
        # (Logique de pagination complète conservée ici)
        if current_page == 1:
            pagination_links = soup.select('div.pagination a')
            max_page = 1
            if pagination_links:
                for link in pagination_links:
                    href = link.get('href', '')
                    match = re.search(r'-p(\d+)\.html', href)
                    if match:
                         page_num = int(match.group(1))
                         if page_num > max_page: max_page = page_num
                total_pages = max_page
            
            if total_pages > 1:
                log_func(f"  [INFO] **{total_pages}** pages de composants trouvées pour ce modèle.")
                
        if not products_on_page and current_page > 1: break 
            
        all_products_for_model.extend(products_on_page)
        log_func(f"  [SUCCÈS] **{len(products_on_page)}** composants extraits (Total : {len(all_products_for_model)})")
        
        current_page += 1
        time.sleep(random.uniform(1.5, 3.5)) 
        
    return all_products_for_model


# --- EXPORTATION ET TRI (MAJ avec paramètres dynamiques) ---

@st.cache_data
def process_and_get_csv_text(data: List[Dict[str, Any]], marge_brute: float, frais_fixes_mo: float, tva_coeff: float) -> str | None:
    """Applique les calculs de prix basés sur les paramètres utilisateur et génère le CSV en mémoire."""
    if not data: return None

    # --- 1. CALCUL ET FORMATAGE DES PRIX ---
    for item in data:
        price_float = item['price_float']
        
        prix_marge = price_float * marge_brute
        prix_intermediaire = prix_marge + frais_fixes_mo
        prix_final_ttc = math.ceil(prix_intermediaire * tva_coeff)
        
        # Formatage des colonnes
        item['Prix Fournisseur HT'] = f"{round(price_float, 2):.2f}".replace('.', ',') + " €"
        item['Marge Brute HT'] = f"{round(prix_marge, 2):.2f}".replace('.', ',') + " €"
        item['Prix Intermédiaire + M.O. HT'] = f"{round(prix_intermediaire, 2):.2f}".replace('.', ',') + " €"
        item['Prix Client TTC'] = f"{prix_final_ttc:.2f}".replace('.', ',') + " €" 
        
        del item['price_float']
        del item['price_raw'] # Suppression pour utiliser le prix formaté

    data.sort(key=lambda x: (str(x.get('marque_modele', '')).lower(), str(x.get('nom_composant', '')).lower()))

    # --- 2. CRÉATION DU CSV EN MÉMOIRE ---
    
    fieldnames = [
        'marque_modele', 
        'nom_composant', 
        'reference', 
        'Prix Fournisseur HT', 
        'Marge Brute HT',      
        'Prix Intermédiaire + M.O. HT', 
        'Prix Client TTC',     
        'link'
    ]
    
    output = io.StringIO()
    # On utilise le point-virgule comme séparateur (standard Excel/FR)
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    writer.writerows(data)
    
    return output.getvalue()


# --- FONCTIONS D'IMPORT/EXPORT DE LIENS (CSV/EXCEL) ---

def download_links_csv(model_links: List[Tuple[str, str]]) -> str:
    """Crée et retourne le contenu CSV des liens de modèles (pour l'export)."""
    df = pd.DataFrame(model_links, columns=['Nom du Modèle', 'URL de la Catégorie'])
    return df.to_csv(index=False, sep=';', encoding='utf-8-sig')

def upload_links_file(uploaded_file: io.BytesIO | None) -> List[Tuple[str, str]] | None:
    """Traite le fichier (CSV ou Excel) téléversé et retourne la liste des liens."""
    if uploaded_file is None:
        return None
    
    file_name = uploaded_file.name
    
    try:
        if file_name.endswith('.csv'):
            # Lecture CSV : Séparateur point-virgule
            df = pd.read_csv(uploaded_file, sep=';', encoding='utf-8-sig')
        elif file_name.endswith('.xlsx'):
            # Lecture Excel : pandas gère la lecture de la première feuille
            df = pd.read_excel(uploaded_file)
        else:
            st.error("Format de fichier non pris en charge. Veuillez utiliser un fichier CSV (séparateur point-virgule) ou Excel (.xlsx).")
            return None
        
        if len(df.columns) < 2:
            st.error("Le fichier doit contenir les données sur deux colonnes : 1) Nom du Modèle et 2) URL de la Catégorie.")
            return None
            
        # Renomme les colonnes pour s'assurer que l'extraction est correcte
        df.columns = ['Nom du Modèle', 'URL de la Catégorie'] + list(df.columns[2:])
        
        new_links = list(df[['Nom du Modèle', 'URL de la Catégorie']].itertuples(index=False, name=None))
        
        valid_new_links = [
            (str(name).strip(), str(url).strip())
            for name, url in new_links
            if str(name).strip() and str(url).strip().startswith('http')
        ]
        
        st.success(f"**{len(valid_new_links)}** liens de modèles importés avec succès depuis le fichier !")
        return valid_new_links
        
    except Exception as e:
        st.error(f"Erreur lors du traitement du fichier. Veuillez vérifier la structure (Nom et URL en colonnes 1 et 2). Détail de l'erreur : {e}")
        return None


# --- FONCTIONS DE SAUVEGARDE GOOGLE SHEETS (Remplace rclone) ---

@st.cache_resource 
def get_gsheet_client():
    """Authentifie et retourne le client gspread en utilisant les secrets Streamlit."""
    try:
        # Tente de se connecter en utilisant le contenu du JSON de la clé de service
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        return gc
    except Exception as e:
        st.error(f"❌ Échec de la connexion à Google Sheets. Avez-vous configuré les secrets ('gcp_service_account') ? Erreur : {e}")
        return None

def save_to_google_sheet(csv_text: str):
    """Convertit le CSV en DataFrame et l'écrit automatiquement dans la Google Sheet."""
    gc = get_gsheet_client()
    if not gc: return False

    try:
        # 1. Conversion du CSV (en mémoire) en DataFrame Pandas
        data_io = io.StringIO(csv_text)
        df = pd.read_csv(data_io, sep=';', encoding='utf-8-sig')

        # 2. Ouverture de la Google Sheet
        spreadsheet_name = GSHEET_NAME # Utilise la constante définie en haut
        sh = gc.open(spreadsheet_name)
        worksheet = sh.get_worksheet(0) # On utilise la première feuille (index 0)

        # 3. Ajout d'une colonne de date/heure de l'export
        df.insert(0, 'Date Export', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        # 4. Écrit le DataFrame dans la feuille de calcul (remplace le contenu existant)
        gd.set_with_dataframe(worksheet, df) 
        
        st.success(f"💾 SAUVEGARDE AUTOMATIQUE RÉUSSIE ! Les données ont été écrites dans la Google Sheet : **{spreadsheet_name}**.")
        st.markdown(f"**[Cliquez ici pour voir les résultats]({sh.url})**")

        return True

    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ Fichier Google Sheet introuvable. Nom : '{spreadsheet_name}'. Assurez-vous qu'il est partagé avec le compte de service.")
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Feuille non trouvée. Assurez-vous que la première feuille de '{spreadsheet_name}' existe.")
    except Exception as e:
        st.error(f"❌ Erreur lors de l'écriture dans Google Sheets : {e}")
        return False


# --- INTERFACE ET EXECUTION PRINCIPALE STREAMLIT ---

def main():
    
    st.set_page_config(
        page_title="Scraper Catalogue iPhone", 
        layout="centered",
        initial_sidebar_state="expanded" 
    )

    # --- CODE DE DÉBOGAGE (À SUPPRIMER PLUS TARD) ---
    try:
        # Tente de lire une partie de la clé
        if 'private_key_id' in st.secrets["gcp_service_account"]:
             st.success("✅ **SECRET CHARGÉ !** La connexion Google est prête à être testée.")
        else:
             st.error("❌ SECRET NON TROUVÉ. Veuillez vérifier le formatage dans Streamlit Cloud.")
    except Exception:
        st.error("❌ ERREUR DE LECTURE DU SECRET. La clé 'gcp_service_account' est manquante ou mal formatée.")
    # --- FIN DU CODE DE DÉBOGAGE ---

    # --- 1. GESTION DE L'ÉTAT DE SESSION ---
    if 'model_links' not in st.session_state:
        st.session_state['model_links'] = DEFAULT_MODEL_URLS
        
    st.title("🤖 Catalogue iPhone Visiodirect")
    st.caption("Gérez vos liens et lancez le scraping.")
    
    
    # --- 2. MENU LATÉRAL : PARAMÈTRES DE CALCUL ---
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
        
    
    # --- 3. ZONE PRINCIPALE : GESTION DES LIENS ---
    st.subheader("🔗 Liens de Catégories à Scraper")
    st.caption("Modifiez, ajoutez, ou utilisez l'import/export pour la gestion de masse.")

    col_dl, col_ul = st.columns(2)

    # EXPORTATION
    csv_links = download_links_csv(st.session_state['model_links'])
    col_dl.download_button(
        label="⬇️ Exporter les liens (CSV)",
        data=csv_links,
        file_name='liens_modeles_a_modifier.csv',
        mime='text/csv',
        help="Téléchargez pour ajouter en masse sur votre PC/Mac."
    )

    # IMPORTATION (accepte CSV et Excel)
    uploaded_file = col_ul.file_uploader(
        "Importer des liens (CSV ou Excel)", 
        type=['csv', 'xlsx'], 
        key="uploader_links",
        help="La première colonne doit contenir le Nom, la deuxième l'URL."
    )

    if uploaded_file is not None:
        new_links = upload_links_file(uploaded_file)
        if new_links:
            st.session_state['model_links'] = new_links
            st.rerun() 


    # Tableau éditable 
    edited_links = st.data_editor(
        st.session_state['model_links'],
        column_config={
            0: st.column_config.TextColumn("Nom du Modèle", help="Ex: iPhone 15 Pro Max", width="medium"),
            1: st.column_config.TextColumn("URL de la Catégorie", help="Lien complet...", width="large"),
        },
        num_rows="dynamic", 
        hide_index=True,
        key="data_editor_links"
    )
    
    st.session_state['model_links'] = edited_links

    # Filtration des lignes valides
    urls_to_scrape = st.session_state['model_links']
    valid_urls_to_scrape = [ 
        (name, url) for name, url in urls_to_scrape 
        if isinstance(name, str) and isinstance(url, str) and name.strip() and url.strip().startswith('http') 
    ]
    
    st.info(f"**{len(valid_urls_to_scrape)}** liens valides seront scannés.")


    # --- 4. BOUTON D'EXÉCUTION ---
    if st.button("LANCER LE SCRAPING COMPLET", type="primary"):
        if not valid_urls_to_scrape:
            st.error("Veuillez ajouter au moins un lien valide pour commencer le scraping.")
            return

        toutes_les_donnees: List[Dict[str, Any]] = []
        st.info("Démarrage du processus. Le temps d'exécution dépend du nombre de liens (comptez plusieurs minutes).")
        
        with st.status('Scraping et traitement en cours...', expanded=True) as log_status:
            
            total_models = len(valid_urls_to_scrape)
            
            col1, col2 = st.columns([4, 1]) 
            progress_bar = col1.progress(0, text="Progression globale...")
            
            for index, (model_name, model_url) in enumerate(valid_urls_to_scrape):
                
                progress_bar.progress((index + 1) / total_models, text=f"Modèle {index+1}/{total_models} : {model_name}")
                
                time.sleep(random.uniform(2.0, 5.0)) 
                
                data_modele = scrape_model_page_streamlit(model_name, model_url, log_status.info)
                toutes_les_donnees.extend(data_modele)

            log_status.update(label="Traitement final des données...", state="running", expanded=True)
            csv_text = process_and_get_csv_text(
                toutes_les_donnees, 
                marge_brute, 
                frais_mo, 
                tva_coeff
            )
        
        # --- 5. RÉSULTATS : SAUVEGARDE AUTOMATIQUE (FINALE) ---
        
        st.success(f"🎉 Processus terminé ! **{len(toutes_les_donnees)}** composants extraits.")
        
        if csv_text:
            # Remplace la fonction rclone / le téléchargement manuel
            save_to_google_sheet(csv_text) 
            
            st.balloons()
        else:
            st.error("Aucune donnée n'a pu être extraite.")

if __name__ == "__main__":
    main()
