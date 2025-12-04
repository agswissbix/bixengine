import datetime
from datetime import timedelta
import uuid
import base64
import logging
from pydoc import html
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt
import pdfkit
import io
from io import BytesIO
from django.contrib.staticfiles import finders
from django.template.loader import get_template
from bixengine.settings import BASE_DIR
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *
import qrcode
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.enum.section import WD_SECTION
from docxtpl import DocxTemplate, RichText
from customapp_swissbix.mock.activeMind.products import products as products_data_mock
from customapp_swissbix.mock.activeMind.services import services as services_data_mock
from customapp_swissbix.mock.activeMind.conditions import frequencies as conditions_data_mock
from customapp_swissbix.customfunc import save_record_fields
from xhtml2pdf import pisa
from types import SimpleNamespace
from commonapp.models import SysUser
from PIL import Image

logger = logging.getLogger(__name__)


def get_activemind(request):
    response_data = {}
    try:
        data = json.loads(request.body)
        recordid_deal = data.get('recordIdTrattativa', None)
        if recordid_deal:
            record_deal=UserRecord('deal',recordid_deal)
            recordid_company=record_deal.values.get('recordidcompany_', None)
            if recordid_company:
                record_company=UserRecord('company',recordid_company)
                response_data = {
                "cliente": {
                    "nome": record_company.values.get('companyname', ''),
                    "indirizzo": record_company.values.get('address', ''),
                    "citta": record_company.values.get('city', '')
                }
            }
        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Si è verificato un errore inatteso: {str(e)}'
        }, status=500)

def save_activemind(request):
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Metodo non permesso. Utilizza POST.'
        }, status=405)

    try:
        request_body = json.loads(request.body)
        data=request_body.get('data', {})
        recordid_deal = data.get('recordIdTrattativa', None)

        if not recordid_deal:
            return JsonResponse({
                'success': False,
                'message': 'recordIdTrattativa mancante.'
            }, status=400)

        # =====================
        # 🔸 SECTION 1
        # =====================
        section1 = data.get('section1', {})
        price = section1.get('price', '')
        product_id = section1.get('selectedTier', '')

        if product_id:
            product = UserRecord('product', product_id)
            if not product or not product.values:
                return JsonResponse({
                    'success': False,
                    'message': f'Prodotto con ID {product_id} non trovato.'
                }, status=404)

            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT recordid_
                    FROM user_dealline
                    WHERE recordiddeal_ = %s
                    AND name LIKE 'System assurance%%' AND deleted_ = 'N'
                    LIMIT 1
                """, [recordid_deal])
                existing_row = cursor.fetchone()

            record_dealline = UserRecord('dealline')
            if existing_row:
                record_dealline = UserRecord('dealline', existing_row[0])

            record_dealline.values['recordiddeal_'] = recordid_deal
            record_dealline.values['recordidproduct_'] = product.values.get('recordid_', '')
            record_dealline.values['name'] = product.values.get('name', '')
            record_dealline.values['unitprice'] = price
            record_dealline.values['unitexpectedcost'] = 0
            record_dealline.values['quantity'] = 1
            record_dealline.save()

            save_record_fields('dealline', record_dealline.recordid)

        # =====================
        # 🔸 SECTION 2 (prodotti multipli)
        # =====================
        section2_products = data.get('section2Products', {})

        for product_key, product_data in section2_products.items():
            quantity = product_data.get('quantity', 1)
            unit_price = product_data.get('unitPrice', 0)
            billing_type = product_data.get('billingType', 'monthly')

            # Trova il recordid_ del prodotto
            product = UserRecord('product', product_key)
            if not product or not product.values:
                # se non trova il prodotto → logga o salta
                continue

            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT recordid_
                    FROM user_dealline
                    WHERE recordiddeal_ = %s
                    AND name LIKE %s AND deleted_ = 'N'
                    LIMIT 1
                """, [recordid_deal, product.values.get('name', '')])
                existing_row = cursor.fetchone()

            record_dealline = UserRecord('dealline')
            if existing_row:
                record_dealline = UserRecord('dealline', existing_row[0])
            record_dealline.values['recordiddeal_'] = recordid_deal
            record_dealline.values['recordidproduct_'] = product.values.get('recordid_', '')
            record_dealline.values['name'] = product.values.get('name', '')
            record_dealline.values['unitprice'] = unit_price
            record_dealline.values['unitexpectedcost'] = 0
            record_dealline.values['quantity'] = quantity
            record_dealline.values['frequency'] = 'Annuale' if billing_type == 'yearly' else 'Mensile'
            record_dealline.save()

            save_record_fields('dealline', record_dealline.recordid)

        # =====================
        # 🔸 SECTION 3 (servizi)
        # =====================
        section_services = data.get('section2Services', {})
        section_conditions = data.get('section3', {})

        frequency = section_conditions.get('selectedFrequency', 'Mensile')
        frequency_price = float(section_conditions.get('price', 0))

        name_parts = []
        total_price = 0

        for key, service in section_services.items():
            qty = int(service.get('quantity', 0))
            unit_price = float(service.get('unitPrice', 0))
            title = service.get('title', '')

            if qty > 0:
                name_parts.append(f"{title}: qta. {qty}")

                service_total = qty * unit_price

                if key == "clientPC" and qty > 1:
                    discount_multiplier = 1 - (qty - 1) / 100
                    service_total = service_total * discount_multiplier

                total_price += service_total

        total_price += frequency_price

        name_str = "AM - Manutenzione servizi - \n" + ",\n".join(name_parts) if name_parts else "AM - Manutenzione servizi"

        # 2. Controllo se esiste già un record dealline per questa trattativa
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT recordid_
                FROM user_dealline
                WHERE recordiddeal_ = %s
                AND name LIKE 'AM - Manutenzione servizi%%' AND deleted_ = 'N'
                LIMIT 1
            """, [recordid_deal])
            existing_row = cursor.fetchone()

            cursor.execute("""
                SELECT recordid_
                FROM user_product
                WHERE name LIKE 'AM - Manutenzione servizi%%' AND deleted_ = 'N'
                LIMIT 1
            """)
            product_row = cursor.fetchone()

        # 3. Se esiste → UPDATE
        record = UserRecord('dealline')
        if existing_row:
            record = UserRecord('dealline', existing_row[0])
        
        record.values['recordidproduct_'] = product_row[0] if product_row else None
        record.values['recordiddeal_'] = recordid_deal
        record.values['name'] = name_str
        record.values['unitprice'] = total_price
        record.values['unitexpectedcost'] = 0
        record.values['quantity'] = 1
        record.values['frequency'] = frequency
        record.save()
        save_record_fields('dealline', record.recordid)

        return JsonResponse({
            'success': True,
            'message': 'Dati ricevuti e processati con successo.'
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Si è verificato un errore inatteso: {str(e)}'
        }, status=500)
    

def build_offer_data(recordid_deal):
    offer_data = {}

    # --- 1) Tiers ---
    req_sa = type('Req', (object,), {"body": json.dumps({"trattativaid": recordid_deal})})
    sa_resp = get_system_assurance_activemind(req_sa)
    tiers = json.loads(sa_resp.content)["tiers"]
    for t in tiers:
        t["total"] = float(t.get("price") or 0.0) if t.get("selected") else 0.0
    offer_data["tiers"] = tiers

    # --- 2) Frequenze ---
    req_freq = type('Req', (object,), {"body": json.dumps({"dealid": recordid_deal})})
    freq_resp = get_conditions_activemind(req_freq)
    frequencies = json.loads(freq_resp.content)["frequencies"]
    offer_data["frequencies"] = frequencies

    selected_frequency_label = None
    for f in frequencies:
        if f.get("selected"):
            selected_frequency_label = f.get("label")
            break

    # --- 3) Servizi ---
    req_srv = type('Req', (object,), {"body": json.dumps({"dealid": recordid_deal})})
    srv_resp = get_services_activemind(req_srv)
    services = json.loads(srv_resp.content)["services"]
    for s in services:
        s["total"] = float(s.get("unitPrice") or 0.0) * int(s.get("quantity") or 0)
        s["billingType"] = selected_frequency_label  # usiamo la frequenza selezionata

    offer_data["services"] = services

    # --- 4) Prodotti ---
    req_prod = type('Req', (object,), {"body": json.dumps({"trattativaid": recordid_deal})})
    prod_resp = get_products_activemind(req_prod)
    products = json.loads(prod_resp.content)["servicesCategory"]
    for cat in products:
        for p in cat.get("services", []):
            p["total"] = float(p.get("unitPrice") or 0.0) * int(p.get("quantity") or 0)
    offer_data["products"] = products

    # --- 5) Totali ---
    total_tiers = sum(t.get("total", 0.0) for t in tiers)
    total_services = sum(s.get("total", 0.0) for s in services)
    total_products = sum(p.get("total", 0.0) for c in products for p in c.get("services", []))

    # 📊 Subtotali ricorrenti
    monthly_total = 0.0
    quarterly_total = 0.0
    biannual_total = 0.0
    yearly_total = 0.0

    # Prodotti
    for c in products:
        for p in c.get("services", []):
            total = p.get("total", 0.0)
            billing = (p.get("billingType") or "").lower()
            if billing == "monthly":
                monthly_total += total
            elif billing == "yearly":
                yearly_total += total

    # Servizi (basati sulla frequenza selezionata)
    if selected_frequency_label:
        for s in services:
            total = s.get("total", 0.0)
            if selected_frequency_label == "Mensile":
                monthly_total += total
            elif selected_frequency_label == "Trimestrale":
                quarterly_total += total
            elif selected_frequency_label == "Semestrale":
                biannual_total += total
            elif selected_frequency_label == "Annuale":
                yearly_total += total

    grand_total = total_tiers + total_services + total_products

    offer_data["totals"] = {
        "tiers": total_tiers,
        "services": total_services,
        "products": total_products,
        "monthly": monthly_total,
        "quarterly": quarterly_total,
        "biannual": biannual_total,
        "yearly": yearly_total,
        "grand_total": grand_total,
    }

    return offer_data


def make_obj(d: dict) -> SimpleNamespace:
    """
    Converte un dict in oggetto con attribute access,
    garantendo campi minimi usati dal chunk.
    """
    d = dict(d)  # copia
    d.setdefault("features", [])
    d.setdefault("quantity", 0)
    return SimpleNamespace(**d)

def chunk(iterable):
    """
    Mantiene esattamente la tua logica:
    - se quantity == 0 → salta
    - se features > 7 → 2 elementi per pagina, altrimenti 3
    """
    pages = []
    page = []
    counter = 0
    for s in iterable:
        # supporta sia oggetti sia dict
        qty = getattr(s, "quantity", s.get("quantity", 0) if isinstance(s, dict) else 0)
        feats = getattr(s, "features", s.get("features", []) if isinstance(s, dict) else [])
        if qty == 0:
            continue
        limit = 2 if len(feats) > 7 else 3
        page.append(s)
        counter += 1
        if counter >= limit:
            pages.append(page)
            page = []
            counter = 0
    if page:
        pages.append(page)
    return pages

@csrf_exempt
def print_pdf_activemind(request):
    """
    Genera il PDF usando SOLO l'id della trattativa:
    - legge tutto dal DB (build_offer_data)
    - calcola i totali lato backend
    - crea le pagine (chunk) per servizi e prodotti
    """
    try:
        data = json.loads(request.body)
        recordid_deal = data.get('idTrattativa', None)
        if not recordid_deal:
            return JsonResponse({'error': 'Missing idTrattativa'}, status=400)

        # firma digitale (come nel tuo codice)
        digital_signature_b64 = data.get('signature', None)
        nameSignature = data.get('nameSignature', '')

        signature_url = None
        if digital_signature_b64:
            try:
                import base64, os, uuid
                if "," in digital_signature_b64:
                    digital_signature_b64 = digital_signature_b64.split(",")[1]
                signature_bytes = base64.b64decode(digital_signature_b64)
                filename = f"signature_{uuid.uuid4().hex}.png"
                signature_path = os.path.join(BASE_DIR, "customapp_swissbix/static/signatures", filename)
                os.makedirs(os.path.dirname(signature_path), exist_ok=True)
                with open(signature_path, "wb") as f:
                    f.write(signature_bytes)
                signature_url = f"signatures/{filename}"
            except Exception as e:
                logger.error(f"Errore salvataggio firma: {e}")

        # 1) ricostruzione offerta
        offer_data = build_offer_data(recordid_deal)

        # 2) preparo oggetti per impaginazione (chunk)
        # servizi (flat -> oggetti)
        service_objs = [make_obj(s) for s in offer_data["services"]]
        section2_services_pages = chunk(service_objs)

        # prodotti: flatten categorie -> oggetti
        product_objs = []
        for cat in offer_data["products"]:
            for p in cat.get("services", []):
                product_objs.append(make_obj(p))
        section2_products_pages = chunk(product_objs)

        # 3) info cliente
        cliente = {}
        record_deal = UserRecord('deal', recordid_deal)
        recordid_company = record_deal.values.get('recordidcompany_', None)
        if recordid_company:
            record_company = UserRecord('company', recordid_company)
            cliente = {
                "nome": record_company.values.get('companyname', ''),
                "indirizzo": record_company.values.get('address', ''),
                "citta": record_company.values.get('city', '')
            }

        # 4) contesto per il template
        context = {
            "client_info": cliente,
            "offer_data": offer_data,
            "section2_services_pages": section2_services_pages,
            "section2_products_pages": section2_products_pages,
            # flat per tabella riepilogo finale (se ti serve)
            "section2_products": product_objs,
            "date": datetime.datetime.now().strftime("%d/%m/%Y"),
            "limit_acceptance_date": (datetime.datetime.now() + timedelta(days=10)).strftime("%d/%m/%Y"),
            "digital_signature_url": signature_url,
            "nameSignature": nameSignature,
        }

        # 5) render + pdf
        template = get_template('activeMind/pdf_template.html')
        html = template.render(context)
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="offerta.pdf"'
        pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
        if pisa_status.err:
            return HttpResponse("Errore durante la creazione del PDF", status=500)
        return response

    except Exception as e:
        logger.error(f"Errore nella generazione PDF: {str(e)}")
        return JsonResponse({'error': f'Errore nella generazione del PDF: {str(e)}'}, status=500)

def link_callback(uri, rel):
    """
    Converti i percorsi HTML (es. /static/ o STATIC_URL) in percorsi assoluti
    leggibili da xhtml2pdf.
    """
    # Cerca nei files statici gestiti da Django
    result = finders.find(uri.replace(settings.STATIC_URL, ""))
    if result:
        if not isinstance(result, (list, tuple)):
            result = [result]
        return result[0]

    # Prova a gestire MEDIA_URL
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
        if os.path.isfile(path):
            return path

    raise Exception(f"Immagine o file statico non trovato: {uri}")

def get_system_assurance_activemind(request):
    data = json.loads(request.body)
    recordid_deal = data.get('trattativaid', None)

    if not recordid_deal:
        return JsonResponse({'error': 'Missing trattativaid'}, status=400)

    tiers = []

    with connection.cursor() as cursor:
        # 1. Prendo i prodotti che iniziano con "System Assurance"
        cursor.execute("""
            SELECT recordid_, name, price
            FROM user_product
            WHERE name LIKE %s AND deleted_ = 'N'
        """, ["System Assurance%"])
        products = cursor.fetchall()  # [(id, name, price), ...]

        # 2. Prendo i product_id selezionati nella trattativa
        cursor.execute("""
            SELECT recordidproduct_
            FROM user_dealline
            WHERE recordiddeal_ = %s AND deleted_ = 'N'
        """, [recordid_deal])
        selected_rows = cursor.fetchall()  # [(product_id,), ...]
        selected_ids = {row[0] for row in selected_rows}

        # 3. Costruisco i tiers
        for product in products:
            prod_id, name, price = product
            tiers.append({
                "id": str(prod_id),
                "label": name.replace("System assurance - ", ""),
                "price": float(price) if price is not None else 0.0,
                "selected": prod_id in selected_ids
            })

    return JsonResponse({"tiers": tiers})

def get_services_activemind(request):
    """
    Restituisce i servizi ActiveMind:
    - Si appoggia al mock solo per determinare quali servizi sono validi e per l'ordine base.
    - Recupera prezzo e features reali dal DB (user_product).
    - Recupera quantità dalla dealline (record AM - Manutenzione servizi).
    - Se il prodotto non è nel DB → mantiene mock con quantità 0.
    """
    try:
        data = json.loads(request.body)
        recordid_deal = data.get("dealid")
        if not recordid_deal:
            return JsonResponse({"error": "Missing dealid"}, status=400)

        # 1️⃣ Costruisco dizionario dal mock (titolo lower come chiave)
        services_dict = {s["title"].strip().lower(): s.copy() for s in services_data_mock}
        for s in services_dict.values():
            s["recordid_product"] = None
            s["unitPrice"] = s.get("unitPrice", 0)
            s["quantity"] = 0
            s["selected"] = False
            s["features"] = s.get("features", [])

        # 2️⃣ Recupero dal DB i prodotti validi
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT recordid_, name, price, note
                FROM user_product
                WHERE name LIKE 'AM %%'
                  AND name NOT LIKE 'AM - Annuale'
                  AND name NOT LIKE 'AM - Trimestrale'
                  AND name NOT LIKE 'AM - Semestrale'
                  AND name NOT LIKE 'AM - Mensile'
                  AND deleted_ = 'N'
            """)
            db_products = cursor.fetchall()

        for recordid_product, name, price, note in db_products:
            clean_name = name.replace("AM - ", "").strip()
            key = clean_name.lower()
            if key not in services_dict:
                # ignoro prodotti non presenti nel mock
                continue

            # sovrascrivo i dati dal DB
            s = services_dict[key]
            s["recordid_product"] = recordid_product
            s["title"] = clean_name
            s["unitPrice"] = float(price or 0)
            s["selected"] = False

            # estraggo le features dal campo note (una per riga)
            if note and note.strip():
                s["features"] = [f.strip() for f in note.split(",")] if note else []

        # 3️⃣ Recupero quantità dalla dealline
        quantities_map = {}
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT name
                FROM user_dealline
                WHERE recordiddeal_ = %s
                  AND name LIKE 'AM - Manutenzione servizi%%' AND deleted_ = 'N'
                LIMIT 1
            """, [recordid_deal])
            row = cursor.fetchone()

        if row:
            raw = row[0].replace("AM - Manutenzione servizi - ", "")
            for entry in raw.split(","):
                if ":" not in entry:
                    continue
                n, qty = entry.strip().split(": qta. ", 1)
                quantities_map[n.strip().lower()] = int(qty.strip())

        # 4️⃣ Aggiorno quantità e totale
        for key, s in services_dict.items():
            s["quantity"] = quantities_map.get(key, 0)
            s["total"] = float(s["unitPrice"]) * s["quantity"]
            s["selected"] = s["quantity"] > 0

        # 5️⃣ Lista finale mantenendo l’ordine del mock
        services_list = list(services_dict.values())

        return JsonResponse({"services": services_list})

    except Exception as e:
        logger.error(f"Errore in get_services_activemind: {e}")
        return JsonResponse({"error": str(e)}, status=500)
    

def get_products_activemind(request):
    data = json.loads(request.body)
    recordid_deal = data.get('trattativaid', None)

    if not recordid_deal:
        return JsonResponse({'error': 'Missing trattativaid'}, status=400)

    # 🔹 Pattern per mappare prodotti -> categorie
    category_map = {
        "data_security": ["RMM", "EDR", "Backup"],
        "mobile_security": ["Safely Mobile"],
        "infrastructure": ["Vulnerability"],
        "sophos": ["Central E-mail", "Phish Threat"],
        "firewall": ["XGS"],
        "microsoft": ["Microsoft 365"]
    }

    # 🔹 Mappa icone già definite nel mock
    icon_map = {
        "RMM": "Monitor",
        "EDR": "Shield",
        "Backup": "Database",
        "Safely Mobile": "Smartphone",
        "Vulnerability": "Search",
        "Central E-mail": "Mail",
        "Phish Threat": "AlertTriangle",
        "XGS": "Shield",
        "Microsoft 365": "Cloud",
    }

    # 🔹 Creo un dizionario per accedere rapidamente alle macro-categorie
    categories_dict = {c["id"]: c for c in products_data_mock}
    # Svuoto i services per poi riempirli con dati reali
    for cat in categories_dict.values():
        cat["services"] = []

    with connection.cursor() as cursor:
        # 1. Prendo tutti i prodotti AM
        cursor.execute("""
            SELECT recordid_, name, description, note, price
            FROM user_product
            WHERE name LIKE 'AM - %' AND deleted_ = 'N'
        """)
        db_products = cursor.fetchall()

        # 2. Prendo le quantità dalla trattativa
        cursor.execute("""
            SELECT recordidproduct_, quantity, frequency
            FROM user_dealline
            WHERE recordiddeal_ = %s AND deleted_ = 'N'
        """, [recordid_deal])
        deal_rows = cursor.fetchall()
        quantity_map = {row[0]: row[1] for row in deal_rows}
        frequency_map = {row[0]: row[2] for row in deal_rows}

    # 3. Per ogni prodotto DB → mappo alla categoria mock
    for recordid_, name, description, note, price in db_products:
        matched_category_id = None
        matched_icon = None

        for cat_id, patterns in category_map.items():
            for p in patterns:
                if p.lower() in name.lower():
                    matched_category_id = cat_id
                    matched_icon = icon_map.get(p, None)
                    break
            if matched_category_id:
                break

        if not matched_category_id:
            # se non matcha nessuna categoria → skip
            continue

        features = [f.strip() for f in note.split(",")] if note else []
        quantity = quantity_map.get(recordid_, 0)
        frequency = frequency_map.get(recordid_, "")

        service = {
            "id": str(recordid_),
            "title": name.replace("AM - ", ""),
            "unitPrice": float(price) if price else 0.0,
            "icon": matched_icon,
            "category": matched_category_id,
            "description": description,
            "monthlyPrice": float(price) if price else None,
            "yearlyPrice": float(price) * 10.5 if price else None,
            "features": features,
            "quantity": quantity,
            "billingType": "yearly" if frequency == "Annuale" else 'monthly',
        }

        categories_dict[matched_category_id]["services"].append(service)

    # 4. Ritorno la struttura aggiornata
    return JsonResponse({"servicesCategory": list(categories_dict.values())}, safe=False)


def get_conditions_activemind(request):
    data = json.loads(request.body)
    recordid_deal = data.get('dealid', None)

    if not recordid_deal:
        return JsonResponse({'error': 'Missing trattativaid'}, status=400)

    # 1. Dizionario base dal mock
    conditions_dict = {f["label"].strip(): f.copy() for f in conditions_data_mock}
    for f in conditions_dict.values():
        f["price"] = 0
        f["selected"] = False
        f["recordid_product"] = None

    # 2. Prendo i prodotti condizioni dal DB
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT recordid_, name, description, price
            FROM user_product
            WHERE name LIKE 'AM - %' AND deleted_ = 'N'
        """)
        products = cursor.fetchall()

        for recordid_product, name, description, price in products:
            clean_name = name.replace("AM - ", "").strip()
            if clean_name in conditions_dict:
                conditions_dict[clean_name]["label"] = clean_name
                conditions_dict[clean_name]["id"] = clean_name
                conditions_dict[clean_name]["description"] = description
                conditions_dict[clean_name]["recordid_product"] = recordid_product
                conditions_dict[clean_name]["price"] = float(price) if price else 0.0

        # 3. Recupero la frequenza selezionata per AM - Manutenzione servizi
        cursor.execute("""
            SELECT frequency
            FROM user_dealline
            WHERE recordiddeal_ = %s
              AND name LIKE 'AM - Manutenzione servizi%%' AND deleted_ = 'N'
            LIMIT 1
        """, [recordid_deal])
        row = cursor.fetchone()

    # 4. Se esiste una riga per manutenzione servizi, controllo il product id associato
    if row and row[0]:
        selected_frequency = row[0]

        # Ricerco tra le condizioni quella con lo stesso recordid_product
        for cond in conditions_dict.values():
            if cond["label"] == selected_frequency:
                cond["selected"] = True
                break

    # 5. Ritorno la lista aggiornata
    conditions_list = list(conditions_dict.values())
    return JsonResponse({"frequencies": conditions_list}, safe=False)


def get_record_badge_swissbix_timesheet(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    recordid= data.get("recordid")

    return_badgeItems={}

    record_timesheet = UserRecord(tableid,recordid)
    company = record_timesheet.fields.get("recordidcompany_", '')
    project = record_timesheet.fields.get("recordidproject_", '')
    service = record_timesheet.fields.get("service", '')
    date = record_timesheet.fields.get("date", '')
    description = record_timesheet.fields.get("description", '')
    user = record_timesheet.fields.get("user", '')
    total_worktime = record_timesheet.fields.get("totaltime_decimal", 0.00)
    validated = record_timesheet.fields.get("validated", 'No')
    invoice_status = record_timesheet.fields.get("invoicestatus", '')

    if user and user['value']:
        user_record = SysUser.objects.filter(id=user['value']).first()
        return_badgeItems["user_photo"] = user_record.id if user_record else ''

    return_badgeItems["service"] = service['value']
    return_badgeItems["date"] = date['value']
    return_badgeItems["description"] = description['value']
    return_badgeItems['project_id'] = project['value'] if project else ''
    return_badgeItems['project_name'] = project['convertedvalue'] if project else ''
    return_badgeItems['user_name'] = user['convertedvalue'] if user else ''
    return_badgeItems['company_id'] = company['value'] if company else ''
    return_badgeItems['company_name'] = company['convertedvalue'] if company else ''
    return_badgeItems["total_worktime"] = total_worktime['value']
    return_badgeItems["validated"] = validated['value']
    return_badgeItems["invoice_status"] = invoice_status['value']
    response={ "badgeItems": return_badgeItems}
    return JsonResponse(response)

def get_record_badge_swissbix_company(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    recordid= data.get("recordid")

    record=UserRecord(tableid,recordid)
    return_badgeItems={}

    # sql=f"SELECT logo FROM user_company WHERE recordid_='{recordid}' AND deleted_='N'"
    # company_logo=HelpderDB.sql_query_value(sql, 'logo')
    company_logo=''

    sql=f"SELECT email, phonenumber, address FROM user_company WHERE recordid_='{recordid}' AND deleted_='N'"
    company_email  =HelpderDB.sql_query_value(sql, 'email')
    company_address=HelpderDB.sql_query_value(sql, 'phonenumber')
    company_phone=HelpderDB.sql_query_value(sql, 'address')


    sql=f"SELECT COUNT(worktime_decimal) as total FROM user_timesheet WHERE recordidcompany_='{recordid}' AND deleted_='N'"
    total_timesheet=HelpderDB.sql_query_value(sql, 'total')

    sql=f"SELECT COUNT(*) as total FROM user_deal WHERE dealstatus='Vinta' AND recordidcompany_='{recordid}' AND deleted_='N'"
    total_deals=HelpderDB.sql_query_value(sql, 'total')

    sql=f"SELECT customertype FROM user_company WHERE recordid_='{recordid}' AND deleted_='N'"
    customertype=HelpderDB.sql_query_value(sql, 'customertype')

    sql=f"SELECT paymentstatus FROM user_company WHERE recordid_='{recordid}' AND deleted_='N'"
    paymentstatus=HelpderDB.sql_query_value(sql, 'paymentstatus')

    sql=f"SELECT salesuser FROM user_company WHERE recordid_='{recordid}' AND deleted_='N'"
    salesuser=HelpderDB.sql_query_value(sql, 'salesuser')
    if salesuser:
        from commonapp.models import SysUser
        user_sales=SysUser.objects.filter(id=salesuser).first()
        return_badgeItems["sales_user_name"] = user_sales.firstname + ' ' + user_sales.lastname if user_sales else ''
        return_badgeItems["sales_user_photo"] = user_sales.id if user_sales else ''
    else:
        return_badgeItems["sales_user_name"] = ''
        return_badgeItems["sales_user_photo"] = ''

    sql=f"SELECT SUM(totalnet) as total FROM user_invoice WHERE recordidcompany_='{recordid}' AND status='Paid' AND deleted_='N'"
    total_invoices=round(HelpderDB.sql_query_value(sql, 'total'), 0) if HelpderDB.sql_query_value(sql, 'total') else 0.00

    return_badgeItems["company_logo"] = company_logo
    return_badgeItems["company_name"] = record.values.get("companyname", '')
    return_badgeItems["company_email"] = company_email  
    return_badgeItems["company_address"] = company_address
    return_badgeItems["company_phone"] = company_phone
    return_badgeItems["payment_status"] = paymentstatus 
    return_badgeItems["customer_type"] = customertype
    return_badgeItems["total_timesheet"] = total_timesheet
    return_badgeItems["total_deals"] = total_deals
    return_badgeItems["total_invoices"] = total_invoices
    response={ "badgeItems": return_badgeItems}
    return JsonResponse(response)   

# TODO migliorare codice in modo da usare UserRecord invece di SQL diretto
def get_record_badge_swissbix_deals(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    recordid= data.get("recordid")

    record=UserRecord(tableid,recordid)
    return_badgeItems={}

    sql=f"SELECT dealname, amount , effectivemargin, dealuser1, dealstage, recordidcompany_ FROM user_deal WHERE recordid_='{recordid}' AND deleted_='N'"

    deal_name=HelpderDB.sql_query_value(sql, 'dealname')
    deal_amount=HelpderDB.sql_query_value(sql, 'amount')
    deal_effectivemargin=HelpderDB.sql_query_value(sql, 'effectivemargin')
    dealstage=HelpderDB.sql_query_value(sql, 'dealstage')


    salesuser=HelpderDB.sql_query_value(sql, 'dealuser1')
    if salesuser:
        user_sales=SysUser.objects.filter(id=salesuser).first()
        return_badgeItems["sales_user_name"] = user_sales.firstname + ' ' + user_sales.lastname if user_sales else ''
        return_badgeItems["sales_user_photo"] = user_sales.id if user_sales else ''
    else:
        return_badgeItems["sales_user_name"] = ''
        return_badgeItems["sales_user_photo"] = ''

    recordidcompany_=HelpderDB.sql_query_value(sql, 'recordidcompany_')
    sql=f"SELECT companyname FROM user_company WHERE recordid_='{recordidcompany_}' AND deleted_='N'"
    company_name=HelpderDB.sql_query_value(sql, 'companyname')

    return_badgeItems["deal_name"] = deal_name
    return_badgeItems["deal_amount"] = deal_amount
    return_badgeItems["deal_effectivemargin"] = deal_effectivemargin
    return_badgeItems["company_name"] = company_name
    return_badgeItems["deal_stage"] = dealstage
    response={ "badgeItems": return_badgeItems}
    return JsonResponse(response)   

def get_record_badge_swissbix_project(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    recordid= data.get("recordid")

    record=UserRecord(tableid,recordid)
    return_badgeItems={}

    sql=f"SELECT projectname, assignedto, status, expectedhours, usedhours, residualhours, recordidcompany_ FROM user_project WHERE recordid_='{recordid}' AND deleted_='N'"

    project_name=HelpderDB.sql_query_value(sql, 'projectname')
    project_status=HelpderDB.sql_query_value(sql, 'status')
    expected_hours=HelpderDB.sql_query_value(sql, 'expectedhours')
    used_hours=HelpderDB.sql_query_value(sql, 'usedhours')
    residual_hours=HelpderDB.sql_query_value(sql, 'residualhours')
    print(f"expected_hours: {expected_hours}, used_hours: {used_hours}, residual_hours: {residual_hours}")
    recordidcompany_=HelpderDB.sql_query_value(sql, 'recordidcompany_')


    manager=HelpderDB.sql_query_value(sql, 'assignedto')
    if manager:
        from commonapp.models import SysUser
        user_sales=SysUser.objects.filter(id=manager).first()
        return_badgeItems["manager_name"] = user_sales.firstname + ' ' + user_sales.lastname if user_sales else ''
        return_badgeItems["manager_photo"] = user_sales.id if user_sales else ''
    else:
        return_badgeItems["manager_name"] = ''
        return_badgeItems["manager_photo"] = ''
    
    sql=f"SELECT companyname FROM user_company WHERE recordid_='{recordidcompany_}' AND deleted_='N'"
    company_name=HelpderDB.sql_query_value(sql, 'companyname')

    return_badgeItems["project_name"] = project_name
    return_badgeItems["project_status"] = project_status
    return_badgeItems["expected_hours"] = expected_hours
    return_badgeItems["used_hours"] = used_hours
    return_badgeItems["residual_hours"] = residual_hours
    return_badgeItems["company_name"] = company_name
    response={ "badgeItems": return_badgeItems}
    return JsonResponse(response)

def stampa_offerta(request):
    data = json.loads(request.body)
    recordid_deal = data.get('recordid')
    

    tableid= 'deal'
  
    # Percorso al template Word
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, 'templates', 'template.docx')


    if not os.path.exists(template_path):
        return HttpResponse("File non trovato", status=404)

    
    deal_record = UserRecord(tableid, recordid_deal)
    reference = deal_record.values.get('reference', 'N/A')
    dealname = deal_record.values.get('dealname', 'N/A')
    dealuser1 = deal_record.values.get('dealuser1', 'N/A')
    closedata = deal_record.values.get('closedate', 'N/A')
    
    filename = reference if reference else f"offerta_{recordid_deal}"

    companyid = deal_record.values.get('recordidcompany_')
    if companyid:
        company_record = UserRecord('company', deal_record.values.get('recordidcompany_'))
        companyname = company_record.values.get('companyname', 'N/A')
        address = company_record.values.get('address', 'N/A')
        cap = company_record.values.get('cap', 'N/A')
        city = company_record.values.get('city', 'N/A')

    user_record=HelpderDB.sql_query_row(f"SELECT * FROM sys_user WHERE id ='{dealuser1}'")
    user = user_record['firstname'] + ' ' + user_record['lastname']
    
    # Definizione economica
    dealline_records = deal_record.get_linkedrecords_dict('dealline')
    lines = []
    total = 0.0

    for idx, line in enumerate(dealline_records, 1):
        name = line.get('name', 'N/A')
        quantity = line.get('quantity', 0)
        unit_price = line.get('unitprice', 0.0)
        price = line.get('price', 0.0)
        total += price
        
        # Formatta i numeri in stile italiano
        qty_str = f"{quantity:.0f}".replace('.', ',')
        unit_str = f"CHF {unit_price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        price_str = f"CHF {price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        # Crea RichText per questa riga prodotto
        rt_prodotto = RichText()
        rt_prodotto.add(f"{idx}. ", bold=True, size=20)
        rt_prodotto.add(name, size=20)
        rt_prodotto.add('\n   ', size=20)
        rt_prodotto.add('Quantità: ', size=20)
        rt_prodotto.add(f"{qty_str}  |  ", bold=True, size=20)
        rt_prodotto.add('Prezzo unitario: ', size=20)
        rt_prodotto.add(f"{unit_str}  |  ", bold=True, size=20)
        rt_prodotto.add('Totale: ', size=20)
        rt_prodotto.add(price_str, bold=True, size=20)
        rt_prodotto.add('\n\n', size=20)
        
        lines.append(rt_prodotto)

    # Crea il titolo
    # Crea il separatore
    separatore = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Crea il totale finale
    total_str = f"CHF {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    rt_totale = RichText()
    rt_totale.add('TOTALE COMPLESSIVO: ', bold=True, size=24)
    rt_totale.add(total_str, bold=True, size=24)

    # Combina tutti i prodotti in un unico RichText
    rt_all_products = RichText()
    for rt_prod in lines:
        # Aggiungi il contenuto di ogni prodotto
        rt_all_products.add(rt_prod)

    # Crea il documento completo
    tabella_completa = RichText()
    tabella_completa.add(separatore)
    tabella_completa.add('\n\n')
    tabella_completa.add(rt_all_products)
    tabella_completa.add(separatore)
    tabella_completa.add('\n\n')
    tabella_completa.add(rt_totale)
    tabella_completa.add('\n\n')
    tabella_completa.add(separatore)

    dati_trattativa = {
        "indirizzo": f"{address}, {cap} {city}",
        "azienda": companyname,
        "titolo": dealname,
        "venditore": user,
        "data_chiusura_vendita": closedata.strftime("%d/%m/%Y") if isinstance(closedata, datetime.date) else closedata,
        "data_attuale": datetime.datetime.now().strftime("%d/%m/%Y"),
        'tabella_prodotti': tabella_completa,
    }


    # Carica il template e fai il rendering
    doc = DocxTemplate(template_path)
    doc.render(dati_trattativa)

    # Salva il documento in memoria
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}.docx"'
    return response

from commonapp.models import *
from django.db.models.functions import Coalesce
from django.db.models import IntegerField
def get_fields_swissbix_deal(request):
    """
    Restituisce tutti gli step di una tabella, includendo:
      - fields per gli step di tipo "campi"
      - linked_tables per gli step di tipo "collegate"
    Senza formattazione FE (ritorna i dati grezzi).
    """
    data = json.loads(request.body)
    tableid = data.get('tableid')
    recordid= data.get("recordid")
    master_tableid= data.get("mastertableid")
    master_recordid= data.get("masterrecordid")

    if not tableid:
        return JsonResponse({
            "success": False,
            "error": "Parametri mancanti."
        }, status=400)

    try:
        table = SysTable.objects.get(id=tableid)
        user = SysUser.objects.get(id=Helper.get_userid(request))
    except (SysTable.DoesNotExist, SysUser.DoesNotExist):
        return JsonResponse({
            "success": False,
            "error": "Tabella o utente non trovati."
        }, status=404)

    step_tables = (
        SysStepTable.objects
        .filter(table=table, user=user)
        .select_related('step')
        .order_by(Coalesce('order', 9999))
    )

    if not step_tables.exists():
        step_tables = (
            SysStepTable.objects
            .filter(table=table, user_id=1)
            .select_related('step')
            .order_by(Coalesce('order', 9999))
        )


    steps_data = []

    for st in step_tables:
        step = st.step
        step_data = {
            "id": step.id,
            "name": step.name,
            "type": step.type,
            "order": st.order,
        }

        if step.type == "campi":
            record=UserRecord(tableid,recordid,Helper.get_userid(request),master_tableid,master_recordid)
            card_fields=record.get_record_card_fields(typepreference='steps_fields', step_id=step.id)

            step_data["fields"] = card_fields

        elif step.type == "collegate":
            record=UserRecord(tableid,recordid)
            linked_tables=record.get_linked_tables(typepreference='keylabel_steps', step_id=step.id)

            step_data["linked_tables"] = linked_tables

        elif step.type == "allegati":
            attachments=HelpderDB.sql_query(f"SELECT * FROM user_attachment WHERE recordid{tableid}_='{recordid}' AND deleted_ = 'N'")
            step_data["attachments"] = attachments

        steps_data.append(step_data)

    return JsonResponse({
        "success": True,
        "steps": steps_data
    })


def deal_update_status(request):
    print('test')
    data = json.loads(request.body)
    params = data.get('params')
    recordid = params.get('recordid')
    status= params.get('status')
    stage= params.get('stage')
    deal_record=UserRecord('deal',recordid)
    deal_record.values['dealstage']=stage
    deal_record.values['dealstatus']=status
    deal_record.save()
    response={ "status": "ok"}
    return JsonResponse(response)


def get_satisfation(request):
    from customapp_swissbix.script import get_satisfaction
    return get_satisfaction()

def update_deals(request):
    from customapp_swissbix.script import update_deals
    return update_deals(request)

def get_scheduler_logs(request):
    from customapp_swissbix.script import get_scheduler_logs
    return get_scheduler_logs(request)

def sync_graph_calendar(request):
    from customapp_swissbix.script import sync_graph_calendar
    return sync_graph_calendar(request)

def sync_tables(request):
    from customapp_swissbix.script import sync_tables
    return sync_tables(request)



def print_timesheet(request):
    """
    Restituisce un PDF già generato, passato come file_path nel body.
    Serve per scaricare il PDF firmato precedentemente salvato.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        data = json.loads(request.body)
        recordid = data.get('recordid')

        if not recordid:
            return JsonResponse({'error': 'Missing recordid'}, status=400)


        record_timesheet = UserRecord('attachment', recordid)
        file_path = record_timesheet.values['file']

        # Percorso assoluto
        abs_path = os.path.join(settings.UPLOADS_ROOT, file_path)

        if not os.path.exists(abs_path):
            return JsonResponse({'error': f'File not found: {file_path}'}, status=404)

        # Legge il PDF e lo restituisce
        with open(abs_path, 'rb') as f:
            pdf_data = f.read()

        response = HttpResponse(pdf_data, content_type='application/pdf')
        filename = os.path.basename(file_path)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        print(f"Error in sign_timesheet (download): {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
def save_signature(request):
    """
    Riceve una firma in base64, genera il PDF del timesheet con la firma
    e salva il file come allegato nel DB (tabella attachment).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        data = json.loads(request.body)
        recordid = data.get('recordid')
        img_base64 = data.get('image')

        if not recordid:
            return JsonResponse({'error': 'Missing recordid'}, status=400)
        if not img_base64:
            return JsonResponse({'error': 'No image data'}, status=400)

        # -------------------------
        # 1️⃣ Salva la firma come immagine PNG
        # -------------------------
        if ',' in img_base64:
            _, img_base64 = img_base64.split(',', 1)
        img_data = base64.b64decode(img_base64)

        base_path = os.path.join(settings.STATIC_ROOT, 'pdf')
        os.makedirs(base_path, exist_ok=True)

        filename_firma = f"firma_{recordid}_{uuid.uuid4().hex}.png"
        firma_path = os.path.join(base_path, filename_firma)

        img_pil = Image.open(BytesIO(img_data))
        if img_pil.mode in ('RGBA', 'LA') or (img_pil.mode == 'P' and 'transparency' in img_pil.info):
            background = Image.new('RGB', img_pil.size, (255, 255, 255))
            background.paste(img_pil, mask=img_pil.split()[-1])
            img_pil = background
        else:
            img_pil = img_pil.convert('RGB')
        img_pil.save(firma_path, format='PNG')

        # -------------------------
        # 2️⃣ Genera QR Code
        # -------------------------
        uid = uuid.uuid4().hex
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=0,
        )
        qrcontent = f"timesheet_{recordid}"
        qr.add_data(qrcontent)
        qr.make(fit=True)

        img_qr = qr.make_image(fill_color="black", back_color="white")
        qr_name = f"qrcode_{uid}.png"
        qr_path = os.path.join(base_path, qr_name)
        img_qr.save(qr_path)

        # -------------------------
        # 3️⃣ Recupera i dati del timesheet
        # -------------------------
        rows = HelpderDB.sql_query(f"""
            SELECT t.*, c.companyname, c.address, c.city, c.email, c.phonenumber, 
                   u.firstname, u.lastname 
            FROM user_timesheet AS t 
            JOIN user_company AS c ON t.recordidcompany_=c.recordid_ 
            JOIN sys_user AS u ON t.user = u.id 
            WHERE t.recordid_='{recordid}'
        """)

        if not rows:
            return JsonResponse({'error': f'Timesheet {recordid} non trovato'}, status=404)

        row = rows[0]
        for value in row:
            row[value] = row[value] or ''

        server = os.environ.get('BIXENGINE_SERVER')
        firma_url = f"{server}/static/pdf/{filename_firma}"
        qr_url = f"{server}/static/pdf/{qr_name}"

        # -------------------------
        # 4️⃣ Prepara i dati per il template
        # -------------------------
        row['recordid'] = recordid
        row['qrUrl'] = qr_url
        row['signatureUrl'] = firma_url

        timesheetlines = HelpderDB.sql_query(
            f"SELECT * FROM user_timesheetline WHERE recordidtimesheet_='{recordid}'"
        )
        for line in timesheetlines:
            line['note'] = line.get('note') or ''
            line['expectedquantity'] = line.get('expectedquantity') or ''
            line['actualquantity'] = line.get('actualquantity') or ''
        row['timesheetlines'] = timesheetlines

        # -------------------------
        # 5️⃣ Genera il PDF
        # -------------------------
        script_dir = os.path.dirname(os.path.abspath(__file__))
        wkhtmltopdf_path = os.path.join(script_dir, 'wkhtmltopdf.exe')
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        content = render_to_string('pdf/timesheet_signature.html', row)

        pdf_filename = f"allegato.pdf"
        pdf_path = os.path.join(base_path, pdf_filename)
        pdfkit.from_string(content, pdf_path, configuration=config)

        # -------------------------
        # 6️⃣ Crea il record allegato
        # -------------------------
        attachment_record = UserRecord('attachment')
        attachment_record.values['type'] = "Signature"
        attachment_record.values['recordidtimesheet_'] = recordid
        attachment_record.save()

        uploads_dir = os.path.join(settings.UPLOADS_ROOT, f"timesheet/{attachment_record.values['recordidtimesheet_']}")
        os.makedirs(uploads_dir, exist_ok=True)

        final_pdf_path = os.path.join(uploads_dir, pdf_filename)
        shutil.copy(pdf_path, final_pdf_path)

        relative_path = f"timesheet/{attachment_record.values['recordidtimesheet_']}/{pdf_filename}"
        attachment_record.values['file'] = relative_path
        attachment_record.values['filename'] = pdf_filename
        attachment_record.save()

        # -------------------------
        # 7️⃣ Risposta finale
        # -------------------------
        return JsonResponse({
            'success': True,
            'message': 'PDF con firma salvato con successo',
            'recordid': recordid,
            'attachment_recordid': attachment_record.recordid,
            'pdf_filename': pdf_filename,
            'pdf_path': relative_path
        })

    except Exception as e:
        print(f"Error in save_signature: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
     

from commonapp.utils.email_sender import *
def save_email_timesheet(request):
    """
    Crea un record email collegato ad un timesheet e allega il PDF del timesheet.
    Si aspetta:
    {
        "recordidTimesheet": "XXXX",
        "recordidAttachment": "YYYY",   # opzionale
        "mailbody": "",
        "subject": "",
        "recipient": ""
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        data = json.loads(request.body)

        recordid_timesheet = data.get("recordid")
        recordid_attachment = data.get("recordidAttachment")

        if not recordid_timesheet:
            return JsonResponse({"error": "Missing recordidTimesheet"}, status=400)

        timesheet = UserRecord("timesheet", recordid_timesheet)

        # INFO PRINCIPALI
        user_id = timesheet.values.get("user")                    # chi ha svolto il lavoro
        creator_id = timesheet.values.get("creatorid_")          # chi ha creato il record
        company_name = timesheet.fields["recordidcompany_"]["convertedvalue"]

        # DESTINATARIO EMAIL
        # esempio: email al responsabile (creator)
        recipient = SysUser.objects.filter(id=creator_id).values_list("email", flat=True).first()

        # SUBJECT
        subject = f"Nuovo timesheet registrato per {company_name}"

        # DATI PER IL CORPO EMAIL
        descrizione = timesheet.values.get("description", "")
        data_lavoro = timesheet.values.get("date", "")
        worktime = timesheet.values.get("worktime", "")
        traveltime = timesheet.values.get("traveltime", "")
        totalprice = timesheet.values.get("totalprice", "")

        # PROGETTO
        project = timesheet.fields["recordidproject_"]["convertedvalue"] \
            if timesheet.values.get("recordidproject_") else ""

        # TASK (opzionale)
        task = timesheet.fields["recordidtask_"]["convertedvalue"] \
            if timesheet.values.get("recordidtask_") else ""

        # UTENTE CHE HA FATTO IL LAVORO
        worker_name = timesheet.fields["user"]["convertedvalue"]

        # ----------------------------------------------------
        #               CORPO EMAIL HTML
        # ----------------------------------------------------
        mailbody = f"""
        <p style="margin:0 0 6px 0;">Ciao,</p>

        <p style="margin:0 0 10px 0;">
            È stato registrato un nuovo timesheet. Ecco i dettagli:
        </p>

        <table style="border-collapse:collapse; width:100%; font-size:14px;">
            <tr><td style="padding:4px 0; font-weight:bold;">Utente:</td><td>{worker_name}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Data:</td><td>{data_lavoro}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Descrizione:</td><td>{descrizione}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Tempo lavoro:</td><td>{worktime}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Tempo viaggio:</td><td>{traveltime}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Prezzo totale:</td><td>{totalprice}</td></tr>
        """

        if project:
            mailbody += f"""
            <tr><td style="padding:4px 0; font-weight:bold;">Progetto:</td><td>{project}</td></tr>
            """

        if task:
            mailbody += f"""
            <tr><td style="padding:4px 0; font-weight:bold;">Task associato:</td><td>{task}</td></tr>
            """

        mailbody += "</table>"

        # link piattaforma
        link_web = "https://bixportal.dc.swissbix.ch/home"

        mailbody += f"""
        <p style="margin:16px 0 0 0;">
            Puoi vedere maggiori informazioni accedendo alla piattaforma:
            <a href="{link_web}">{link_web}</a>
        </p>

        <p style="margin:0;">Cordiali saluti,</p>
        <p style="margin:0;">Il team</p>
        """


        # Dati email da salvare

        # --- Gestione allegato ---
        if recordid_attachment:
            try:
                attach_record = UserRecord("attachment", recordid_attachment)
                file_rel_path = attach_record.values.get("file", "")


            except Exception as ex:
                print("Errore nel recupero allegato:", ex)

        email_data = {
            "to": recipient,
            "subject": subject,
            "text": mailbody,
            "cc": "",
            "bcc": "",
            "attachment_relativepath": file_rel_path if file_rel_path else "",
            "attachment_name": os.path.basename(file_rel_path) if file_rel_path else ""
        }
        # Salvataggio finale email
        EmailSender.save_email("timesheet", recordid_timesheet, email_data)

        return JsonResponse({"success": True})

    except Exception as e:
        print("Error in save_email_timesheet:", e)
        return JsonResponse({"error": str(e)}, status=500)
def print_servicecontract(request):
    from customapp_swissbix.script import print_servicecontract
    return print_servicecontract(request)

def renew_servicecontract(request):
    from customapp_swissbix.script import renew_servicecontract
    return renew_servicecontract(request)

def sync_contacts(request):
    from customapp_swissbix.script import sync_contacts
    return sync_contacts(request)

def sync_job_status(request):
    from customapp_swissbix.script import sync_job_status
    return sync_job_status(request)

def get_timesheets_to_invoice(request):
    from customapp_swissbix.script import get_timesheets_to_invoice
    return get_timesheets_to_invoice(request)

def upload_timesheet_in_bexio(request):
    from customapp_swissbix.script import upload_timesheet_in_bexio
    return upload_timesheet_in_bexio(request)