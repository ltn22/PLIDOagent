#!/usr/bin/env python3
"""
browse_pass.py

Agent autonome d'automatisation pour PASS IMT Atlantique.
- Ouvre Chrome en mode visible (headless=False)
- Se rend sur https://pass.imt-atlantique.fr
- Clique sur SSO et saisit 'toutain' comme identifiant
- Attend la saisie manuelle du mot de passe et la validation
- Laisse le navigateur actif pour la navigation vers 'Consultation des fiches pédagogiques' -> 'Catalogue UE - TAF'
- Pour chaque élément (UE/cours) de la liste, clique et intercepte spécifiquement la FENÊTRE POPUP ouverte
- Attend 10 secondes que la popup se charge complètement, extrait son texte (toutes frames) et la ferme.
"""

import os
import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TAF_DIR = os.path.abspath("taf")
os.makedirs(TAF_DIR, exist_ok=True)

# Temps d'attente configuré pour le chargement des popups (en secondes)
POPUP_WAIT_SECONDS = 10

def extract_content_from_target(page_or_popup):
    """
    Extrait l'intégralité du texte et du HTML de la fenêtre popup spécifiée,
    en parcourant TOUTES ses frames/iframes (PASS utilise des <frameset> et <frame name="content">).
    """
    all_text_parts = []
    all_html_parts = []
    
    for frame in page_or_popup.frames:
        try:
            f_name = frame.name or frame.url
            f_txt = frame.evaluate("() => document.body ? document.body.innerText : ''").strip()
            f_html = frame.content()
            
            if not f_txt and f_html:
                soup = BeautifulSoup(f_html, "html.parser")
                for tag in soup(["script", "style", "head", "meta"]):
                    tag.decompose()
                f_txt = soup.get_text("\n", strip=True)
                
            if f_txt and len(f_txt) > 20:
                all_text_parts.append(f"--- FRAME ({f_name}) ---\n" + f_txt)
            if f_html:
                all_html_parts.append(f"<!-- FRAME ({f_name}) -->\n" + f_html)
        except Exception:
            pass

    if not all_text_parts:
        top_txt = page_or_popup.evaluate("() => document.body ? document.body.innerText : ''").strip()
        top_html = page_or_popup.content()
        if not top_txt and top_html:
            soup = BeautifulSoup(top_html, "html.parser")
            for tag in soup(["script", "style", "head", "meta"]):
                tag.decompose()
            top_txt = soup.get_text("\n", strip=True)
        if top_txt:
            all_text_parts.append(top_txt)
        if top_html:
            all_html_parts.append(top_html)

    full_text = "\n\n".join(all_text_parts)
    full_html = "\n\n".join(all_html_parts)
    
    return full_text.strip(), full_html.strip()

def find_course_items(frame_or_page):
    """Trouve tous les éléments/liens cliquables représentant une fiche UE/cours dans la liste."""
    items = []
    seen_texts = set()
    
    selectors = [
        "a[href*='Fiche']", "a[href*='javascript']", "a[onclick]", "tr[onclick]",
        "a:has-text('PA-')", "a:has-text('UE')", "table td a", "ul li a"
    ]
    
    for sel in selectors:
        try:
            elements = frame_or_page.query_selector_all(sel)
            for el in elements:
                txt = el.text_content().strip()
                if txt and len(txt) > 3 and txt not in seen_texts and txt not in ["Retour", "Accueil", "Aide", "Déconnexion"]:
                    seen_texts.add(txt)
                    items.append((txt, el))
        except Exception:
            pass
            
    return items

def click_and_capture_popup(context, page, link_el):
    """Clique sur le lien et intercepte la fenêtre POPUP ouverte par Chrome."""
    popup_page = None
    
    # 1. Tentative avec expect_page + clic direct
    try:
        with context.expect_page(timeout=5000) as p_info:
            link_el.click(force=True)
        popup_page = p_info.value
    except Exception:
        pass
        
    # 2. Tentative avec clic JavaScript
    if not popup_page:
        try:
            with context.expect_page(timeout=5000) as p_info:
                link_el.evaluate("el => el.click()")
            popup_page = p_info.value
        except Exception:
            pass

    # 3. Vérification des fenêtres secondaires dans le contexte
    if not popup_page:
        pages = context.pages
        if len(pages) > 1 and pages[-1] != page:
            popup_page = pages[-1]

    return popup_page

def click_and_extract_item(context, page, frame, link_el, item_idx, item_label, choice_idx, choice_label):
    clean_course = re.sub(r"[^\w\-_]", "_", item_label[:50].strip())
    clean_choice = re.sub(r"[^\w\-_]", "_", choice_label[:25].strip())
    prefix = f"taf_{choice_idx}_{clean_choice}_item_{item_idx:02d}_{clean_course}"
    
    print(f"\n   [Fiche {item_idx:02d}] Clic sur l'UE : '{item_label[:65]}'...")

    # Clic et interception de la popup
    popup_page = click_and_capture_popup(context, page, link_el)
    
    if popup_page:
        print(f"      --> FENÊTRE POPUP DÉTECTÉE : {popup_page.url}")
        print(f"      --> Attente de {POPUP_WAIT_SECONDS}s pour le chargement complet de la popup...")
        
        start_wait = time.time()
        while time.time() - start_wait < POPUP_WAIT_SECONDS:
            try:
                popup_page.wait_for_load_state("networkidle", timeout=2000)
            except Exception:
                pass
            txt_check, _ = extract_content_from_target(popup_page)
            if len(txt_check) > 300:
                print(f"      --> Contenu POPUP chargé ({len(txt_check):,} caractères) en {int(time.time() - start_wait)}s")
            time.sleep(1.5)
            
        elapsed = time.time() - start_wait
        if elapsed < POPUP_WAIT_SECONDS:
            time.sleep(POPUP_WAIT_SECONDS - elapsed)

        # Extraction DE LA POPUP
        popup_text, popup_html = extract_content_from_target(popup_page)
        
        txt_path = os.path.join(TAF_DIR, f"{prefix}.txt")
        html_path = os.path.join(TAF_DIR, f"{prefix}.html")
        
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"CHOIX_TAF: {choice_label}\nTITRE_FICHE: {item_label}\nURL_POPUP: {popup_page.url}\n\n{popup_text}")
            
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(popup_html)
            
        print(f"      --> FICHE POPUP ENREGISTRÉE : {txt_path} ({len(popup_text):,} caractères)")

        # Téléchargement des PDF depuis la popup
        try:
            pdf_links = popup_page.query_selector_all("a[href*='.pdf'], a:has-text('PDF'), a:has-text('Télécharger')")
            for p_idx, p_link in enumerate(pdf_links, 1):
                try:
                    with popup_page.expect_download(timeout=3000) as d_info:
                        p_link.click()
                    download = d_info.value
                    pdf_file = os.path.join(TAF_DIR, f"{prefix}_pdf_{p_idx}_{download.suggested_filename}")
                    download.save_as(pdf_file)
                    print(f"      --> PDF téléchargé : {pdf_file}")
                except Exception:
                    pass
        except Exception:
            pass

        # Fermer la fenêtre popup
        try:
            popup_page.close()
            print("      --> Fenêtre popup fermée.")
        except Exception:
            pass
    else:
        print("      --> AVERTISSEMENT: Aucune popup détectée pour cet élément.")

def process_current_list(context, page, choice_idx, choice_label):
    print(f"\n--- [Choix {choice_idx}] Recherche des éléments UE cliquables : {choice_label} ---")
    
    items = []
    target_frame = page.main_frame
    
    for frame in page.frames:
        frame_items = find_course_items(frame)
        if len(frame_items) > len(items):
            items = frame_items
            target_frame = frame
            
    if not items:
        items = find_course_items(page)

    if items:
        print(f"--> Trouvé {len(items)} éléments UE dans la liste !")
        for item_idx, (item_label, link_el) in enumerate(items, 1):
            click_and_extract_item(context, page, target_frame, link_el, item_idx, item_label, choice_idx, choice_label)
    else:
        print("--> Aucun élément spécifique détecté automatiquement.")

def main():
    print("=" * 75)
    print(" Agent PASS IMT Atlantique - Capture Ciblée des Fenêtres Popups UE")
    print("=" * 75)

    with sync_playwright() as p:
        print("\n[1/4] Ouverture du navigateur Chrome...")
        browser = p.chromium.launch(headless=False, slow_mo=200)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print("[2/4] Navigation vers https://pass.imt-atlantique.fr ...")
        page.goto("https://pass.imt-atlantique.fr")
        time.sleep(2)

        try:
            sso_btn = page.query_selector("button:has-text('SSO'), a:has-text('SSO'), input[value*='SSO']")
            if sso_btn:
                print("--> Clic sur le bouton SSO...")
                sso_btn.click()
                time.sleep(2)
        except Exception:
            pass

        try:
            user_input = page.query_selector("input#username, input[name='username'], input[placeholder*='Identifiant'], input[type='text']")
            if user_input:
                user_input.fill("toutain")
                print("--> Identifiant 'toutain' renseigné.")
            pwd_input = page.query_selector("input#password, input[name='password'], input[type='password']")
            if pwd_input:
                pwd_input.focus()
        except Exception:
            pass

        print("\n" + "*" * 75)
        print(" INSTRUCTION : ")
        print(" 1. Tapez votre MOT DE PASSE dans Chrome et connectez-vous.")
        print(" 2. Le navigateur Chrome reste ouvert et actif.")
        print("*" * 75 + "\n")

        input("Appuyez sur ENTRÉE dans cette console une fois connecté à PASS...")

        print("\n[3/4] Accès au 'Catalogue UE - TAF'...")
        input("Allez sur la page 'Catalogue UE - TAF' dans Chrome, puis appuyez sur ENTRÉE ici...")

        print("\n[4/4] Recherche des 4 choix de catalogues/TAF...")

        choices_found = []
        for frame in page.frames:
            try:
                selects = frame.query_selector_all("select")
                for s in selects:
                    opts = [o for o in s.query_selector_all("option") if o.get_attribute("value") and o.get_attribute("value") not in ["0", "", "-1"]]
                    if len(opts) >= 2:
                        choices_found.append((frame, s, opts))
            except Exception:
                pass

        if choices_found:
            target_frame, target_select, options = choices_found[0]
            print(f"--> Menu déroulant des choix trouvé ({len(options)} options) !")

            for choice_idx, opt in enumerate(options[:4], 1):
                val = opt.get_attribute("value")
                label = opt.text_content().strip()
                print(f"\n=========================================================================")
                print(f" SELECTION DU CHOIX {choice_idx}/4 : '{label}'")
                print(f"=========================================================================")

                try:
                    target_select.select_option(value=val)
                    time.sleep(3)
                except Exception as e:
                    print(f"    (Note sélection : {e})")

                process_current_list(context, page, choice_idx, label)
        else:
            print("--> Sélecteur automatique de choix non trouvé. Traitement du choix actuellement affiché :")
            for choice_idx in range(1, 5):
                print(f"\n--- Traitement du Choix {choice_idx}/4 ---")
                label_input = input(f"Affichez la liste du Choix n°{choice_idx} dans Chrome, puis appuyez sur ENTRÉE : ")
                label = label_input.strip() or f"Choix_TAF_{choice_idx}"
                process_current_list(context, page, choice_idx, label)

        print("\n" + "=" * 75)
        print(f" EXTRACTION TERMINÉE ! Toutes les fiches ont été enregistrées dans :\n {TAF_DIR}")
        print("=" * 75)

        input("\nAppuyez sur ENTRÉE pour fermer le navigateur Chrome...")
        browser.close()

if __name__ == "__main__":
    main()
