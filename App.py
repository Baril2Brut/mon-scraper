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

# --- CONFIGURATION INITIALE DES LIENS ---
# Cette liste n'est utilisée que la première fois que l'utilisateur lance l'application.
# Ensuite, la liste est stockée et modifiée par l'utilisateur via le tableau interactif.
DEFAULT_MODEL_URLS: List[Tuple[str, str]] = [
    # iPhone 15 Series
    ("iPhone 15 Pro Max", "http://www.visiodirect-mobile.com/iphone-15-pro-max-ssf1301-fss2-fcss4.html"),
    ("iPhone 15 Pro", "http://www.visiodirect-mobile.com/iphone-15-pro-ssf1300-fss2-fcss4.html"),
    ("iPhone 15 Plus", "http://www.visiodirect-mobile.com/iphone-15-plus-ssf1299-fss2-fcss4.html"),
    ("iPhone 15", "http://www.visiodirect-mobile.com/iphone-15-ssf1298-fss2-fcss4.html"),
    # iPhone 14 Series (Raccourci pour l'exemple)
    ("iPhone 14 Pro Max", "http://www.visiodirect-mobile.com/iphone-14-pro-max-ssf1297-fss2-fcss4.html"),
    ("iPhone 14 Pro", "http://www.visiodirect-mobile.com/iphone-14-pro-ssf1296-fss2-fcss4.html"),
    ("iPhone 14 Plus", "http://www.visiodirect-mobile.com/iphone-14-plus-ssf1086-fss2-fcss4.html"),
    ("iPhone 14", "http://www.visiodirect-mobile.com/iphone-14-ssf1085-fss2-fcss4.html"),
    # Ajoutez d'autres modèles ici si vous le souhaitez pour l'initialisation
] 

# SÉLECTEUR DE PRODUIT CONFIRMÉ
PRODUCT_CONTAINER_SELECTOR: str = 'div.cadre_prod'
BASE_URL: str = "http://www.visiodirect-mobile.com"


# --- FONCTIONS UTILITAIRES ---
@st.cache_data 
def clean_price(price_raw: str) -> float:
    """Nettoie une chaîne de prix pour la convertir en nombre flottant (float)."""
    if price_raw == "N/A": return 0.0
    cleaned_price = price_raw.lower().replace('€', '').replace('ttc', '').replace('.', '').replace(',', '.').strip()
    try: return float(cleaned_price)
    except ValueError: return 0.0

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
    """Visite la page du modèle et extrait tous les composants (produits) pour l'interface Streamlit."""
    
    log_func(f"**🔎 Démarrage du scraping des composants pour {model_name}...**")
    
    all_products_for_model: List[Dict[str, Any]] = []
    current_page = 1
    total_pages = 1 
    # ... (Le reste du code de scraping est le même que la version corrigée)
    
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
    """Applique les calculs de prix basés sur les paramètres utilisateur et génère le CSV."""
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

    data.sort(key=lambda x: (str(x.get('marque_modele', '')).lower(), str(x.get('nom_composant', '')).lower()))

    # --- 2. CRÉATION DU CSV EN MÉMOIRE ---
    all_keys = set()
    for d in data: all_keys.update(d.keys())
    
    fieldnames = [
        'marque_modele', 
        'nom_composant', 
        'reference', 
        'Prix Fournisseur HT', 
        'Marge Brute HT',      
        'Prix Intermédiaire + M.O. HT', 
        'Prix Client TTC',     
        'price_raw', 
        'link'
    ]
    fieldnames += sorted([k for k in all_keys if k not in fieldnames])
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    writer.writerows(data)
    
    return output.getvalue()


# --- INTERFACE ET EXECUTION PRINCIPALE STREAMLIT ---

def main():
    
    st.set_page_config(
        page_title="Scraper Catalogue iPhone", 
        layout="centered",
        initial_sidebar_state="expanded" # Le menu sera ouvert par défaut
    )

    # --- 1. GESTION DE L'ÉTAT DE SESSION (Sauvegarde des liens) ---
    if 'model_links' not in st.session_state:
        st.session_state['model_links'] = DEFAULT_MODEL_URLS
        
    st.title("🤖 Catalogue iPhone Visiodirect")
    st.caption("Gérez vos liens et lancez le scraping.")
    
    
    # --- 2. MENU LATÉRAL : PARAMÈTRES DE CALCUL (Nouveauté) ---
    with st.sidebar:
        st.header("⚙️ Ajuster les Paramètres")
        st.caption("Modifiez ces valeurs pour recalculer les prix finaux.")
        
        # st.slider pour la marge (plus visuel)
        marge_brute = st.slider(
            "Coefficient de Marge Brute", 
            1.0, 3.0, 
            value=1.60, 
            step=0.01,
            help="1.60 = 60% de marge. Prix HT x 1.60"
        )
        # st.number_input pour les frais
        frais_mo = st.number_input(
            "Frais Fixes de Main d'Œuvre (€)", 
            0.0, 100.0, 
            value=20.0,
            step=1.0
        )
        # st.number_input pour la TVA
        tva_coeff = st.number_input(
            "Coefficient de TVA (Ex: 1.20 pour 20%)", 
            1.0, 3.0, 
            value=1.20,
            step=0.01
        )
        st.markdown("---")
        
    
    # --- 3. ZONE PRINCIPALE : GESTION DES LIENS (Nouveauté) ---
    st.subheader("🔗 Liens de Catégories à Scraper")
    st.caption("Ajoutez, modifiez ou supprimez des liens directement dans le tableau. Cliquez deux fois sur une cellule pour la modifier. Le tri se fait en cliquant sur les en-têtes.")

    # st.data_editor pour gérer les données de manière interactive
    edited_links = st.data_editor(
        st.session_state['model_links'],
        column_config={
            0: st.column_config.TextColumn("Nom du Modèle", help="Ex: iPhone 15 Pro Max", width="medium"),
            1: st.column_config.TextColumn("URL de la Catégorie", help="Lien complet de la catégorie sur visiodirect-mobile.com", width="large"),
        },
        num_rows="dynamic", # Permet d'ajouter de nouvelles lignes
        hide_index=True
    )
    
    # Met à jour la Session State avec les liens édités par l'utilisateur
    st.session_state['model_links'] = edited_links

    # Filtration des lignes vides ou non valides
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
            
            # Utilisation de colonnes pour une meilleure mise en page mobile
            col1, col2 = st.columns([4, 1]) 
            progress_bar = col1.progress(0, text="Progression globale...")
            
            for index, (model_name, model_url) in enumerate(valid_urls_to_scrape):
                
                progress_bar.progress((index + 1) / total_models, text=f"Modèle {index+1}/{total_models} : {model_name}")
                
                time.sleep(random.uniform(2.0, 5.0)) 
                
                data_modele = scrape_model_page_streamlit(model_name, model_url, log_status.info)
                toutes_les_donnees.extend(data_modele)

            # Traitement final et obtention du texte CSV, en passant les nouveaux paramètres
            log_status.update(label="Traitement final des données...", state="running", expanded=True)
            csv_text = process_and_get_csv_text(
                toutes_les_donnees, 
                marge_brute, 
                frais_mo, 
                tva_coeff
            )
        
        # --- 5. RÉSULTATS ---
        
        st.success(f"🎉 Processus terminé ! **{len(toutes_les_donnees)}** composants extraits.")
        
        if csv_text:
            st.download_button(
                label="📥 Télécharger le Fichier CSV",
                data=csv_text,
                file_name='resultats_catalogue_iphone.csv',
                mime='text/csv'
            )
            st.balloons()
        else:
            st.error("Aucune donnée n'a pu être extraite.")

if __name__ == "__main__":
    main()
