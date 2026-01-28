import datetime
from datetime import timedelta
import sys
import uuid
import base64
import logging
from pydoc import html
from django.http import FileResponse, JsonResponse, HttpResponseNotFound, StreamingHttpResponse
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
import subprocess
from docxtpl import DocxTemplate, RichText
from customapp_swissbix.customfunc import save_record_fields
from xhtml2pdf import pisa
from playwright.sync_api import sync_playwright
from types import SimpleNamespace
from commonapp.models import SysUser
from PIL import Image
from customapp_swissbix.utils.browser_manager import BrowserManager

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
        return JsonResponse({'success': False, 'message': 'Metodo non permesso. Utilizza POST.'}, status=405)

    try:
        request_body = json.loads(request.body or "{}")
        data = request_body.get('data', {})
        recordid_deal = data.get('recordIdTrattativa')

        if not recordid_deal:
            return JsonResponse({'success': False, 'message': 'recordIdTrattativa mancante.'}, status=400)

        # -------------------------------------------------
        # Helper Functions
        # -------------------------------------------------
        def fetch_existing_dealline(recordid_deal, category):
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT recordid_
                    FROM user_dealline
                    WHERE recordiddeal_ = %s
                      AND name LIKE %s
                      AND deleted_ = 'N'
                    LIMIT 1
                """, [recordid_deal, category])
                row = cursor.fetchone()
                return row[0] if row else None

        def save_dealline(values):
            rec_id = values.get('recordid_')
            record = UserRecord('dealline', rec_id) if rec_id else UserRecord('dealline')

            for k, v in values.items():
                if k != 'recordid_':
                    record.values[k] = v

            computed = Helper.compute_dealline_fields(record.values, UserRecord)
            record.values.update(computed)
            record.save()
            save_record_fields('dealline', record.recordid)
            return record.recordid

        # -------------------------------------------------
        # SECTION 1 — Prodotto principale
        # -------------------------------------------------
        section1 = data.get('section1', {})
        product_id = section1.get('selectedTier')
        price = section1.get('price', 0)
        cost = section1.get('cost', 0)

        if product_id:
            product = UserRecord('product', product_id)
            if not product or not product.values:
                return JsonResponse({'success': False, 'message': f'Prodotto con ID {product_id} non trovato.'}, status=404)

            existing_id = fetch_existing_dealline(recordid_deal, "System assurance%")

            save_dealline({
                'recordid_': existing_id,
                'recordiddeal_': recordid_deal,
                'recordidproduct_': product.values.get('recordid_'),
                'name': product.values.get('name'),
                'unitprice': price,
                'unitexpectedcost': cost,
                'quantity': 1
            })

        # -------------------------------------------------
        # SECTION 2 — Prodotti multipli
        # -------------------------------------------------
        for product_key, product_data in data.get('section2Products', {}).items():
            product = UserRecord('product', product_key)
            if not product or not product.values:
                continue

            quantity = product_data.get('quantity', 1)
            unit_price = product_data.get('unitPrice', 0)
            unit_cost = product_data.get('unitCost', 0)
            billing_type = product_data.get('billingType', 'monthly')

            existing_id = fetch_existing_dealline(recordid_deal, product.values.get('name', ''))

            save_dealline({
                'recordid_': existing_id,
                'recordiddeal_': recordid_deal,
                'recordidproduct_': product.values.get('recordid_'),
                'name': product.values.get('name'),
                'unitprice': unit_price,
                'unitexpectedcost': unit_cost,
                'quantity': quantity,
                'frequency': 'Annuale' if billing_type == 'yearly' else 'Mensile'
            })

        # -------------------------------------------------
        # SECTION 3 — Servizi
        # -------------------------------------------------
        services = data.get('section2Services', {})
        if not services:
            return JsonResponse({'success': True, 'message': 'Dati ricevuti e processati con successo.'}, status=200)

        conditions = data.get('section3', {})
        frequency = conditions.get('selectedFrequency', 'Mensile')
        frequency_price = float(conditions.get('price', 0))

        total_price = 0
        total_cost = 0
        name_parts = []

        for key, service in services.items():
            qty = int(service.get('quantity', 0))
            unit_price = float(service.get('unitPrice', 0))
            unit_cost = float(service.get('unitCost', 0))
            title = service.get('title', '')

            if qty <= 0:
                continue

            name_parts.append(f"{title}: qta. {qty}")
            service_total = qty * unit_price

            # Sconto speciale solo per clientPC
            if key == "clientPC" and qty > 1:
                discount = 1 - (qty - 1) / 100
                service_total *= discount

            total_price += service_total
            total_cost += qty * unit_cost

        total_price += frequency_price
        name_str = "AM - Manutenzione servizi - \n" + ",\n".join(name_parts) if name_parts else "AM - Manutenzione servizi"

        # Recupera productid del servizio
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT recordid_
                FROM user_product
                WHERE name LIKE 'AM - Manutenzione servizi%%'
                  AND deleted_ = 'N'
                LIMIT 1
            """)
            product_row = cursor.fetchone()

        product_id = product_row[0] if product_row else None

        # Check esistenza dealline
        existing_id = fetch_existing_dealline(recordid_deal, "AM - Manutenzione servizi%")

        save_dealline({
            'recordid_': existing_id,
            'recordiddeal_': recordid_deal,
            'recordidproduct_': product_id,
            'name': name_str,
            'unitprice': total_price,
            'unitexpectedcost': total_cost,
            'quantity': 1,
            'frequency': frequency
        })

        return JsonResponse({'success': True, 'message': 'Dati ricevuti e processati con successo.'}, status=200)

    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Errore inatteso: {str(e)}'}, status=500)


def build_offer_data(recordid_deal, fe_data=None):
    offer_data = fe_data or {}

    # -----------------------------
    # 1. SECTION 1 → System Assurance
    # -----------------------------
    if fe_data.get("section1").get('selectedTier'):
        req_sa = type('Req', (object,), {"body": json.dumps({"trattativaid": recordid_deal})})
        sa_resp = get_system_assurance_activemind(req_sa)
        tiers = json.loads(sa_resp.content)["tiers"]
        for t in tiers:
            t["total"] = float(t.get("price") or 0.0) if t.get("selected") else 0.0
        offer_data["tiers"] = tiers
    else:
        offer_data["tiers"] = []  # SEZIONE NON ATTIVA

    # -----------------------------
    # 2. SECTION 3 → Frequenze
    # -----------------------------
    total_frequencies = 0
    if fe_data.get("section3") and fe_data.get("section2Services"):
        req_freq = type('Req', (object,), {"body": json.dumps({"dealid": recordid_deal})})
        freq_resp = get_conditions_activemind(req_freq)
        frequencies = json.loads(freq_resp.content)["frequencies"]
        offer_data["frequencies"] = frequencies
        selected_frequency_label = None
        for f in frequencies:
            if f.get("selected"):
                total_frequencies = float(f.get('price', 0))
                selected_frequency_label = f.get("label")
                break
    else:
        offer_data["frequencies"] = []  # SEZIONE NON ATTIVA

    # -----------------------------
    # 3. SECTION 2 → Servizi
    # -----------------------------
    if fe_data.get("section2Services"):
        req_srv = type('Req', (object,), {"body": json.dumps({"dealid": recordid_deal})})
        srv_resp = get_services_activemind(req_srv)
        services = json.loads(srv_resp.content)["services"]
        for s in services:
            s["billingType"] = selected_frequency_label  # usiamo la frequenza selezionata
        offer_data["services"] = services
    else:
        offer_data["services"] = []

    # -----------------------------
    # 4. SECTION 2 → Prodotti
    # -----------------------------
    if fe_data.get("section2Products"):
        req_prod = type('Req', (object,), {"body": json.dumps({"trattativaid": recordid_deal})})
        prod_resp = get_products_activemind(req_prod)
        products = json.loads(prod_resp.content)["servicesCategory"]
        for cat in products:
            for p in cat.get("services", []):
                if p['billingType'] == 'yearly':
                    p["total"] = float(p.get("yearlyPrice") or 0.0) * int(p.get("quantity") or 0)
                else:
                    p["total"] = float(p.get("monthlyPrice") or 0.0) * int(p.get("quantity") or 0)
        offer_data["products"] = products
    else:
        offer_data["products"] = []

    # -----------------------------
    # 5. CALCOLO TOTALE → solo su ciò che è stato caricato
    # -----------------------------

    tiers = offer_data.get("tiers", [])
    services = offer_data.get("services", [])
    products = offer_data.get("products", [])
    frequencies = offer_data.get("frequencies", [])

    total_tiers = sum(t.get("total", 0.0) for t in tiers)
    total_services = sum(s.get("total", 0.0) for s in services)
    total_products = sum(
        p.get("total", 0.0)
        for c in products
        for p in c.get("services", [])
    )

    monthly_total = 0.0
    quarterly_total = 0.0
    biannual_total = 0.0
    yearly_total = 0.0

    for c in products:
        for p in c.get("services", []):
            total = p.get("total", 0.0)
            billing = (p.get("billingType") or "").lower()

            if billing == "monthly":
                monthly_total += total
            elif billing == "annual" or billing == "yearly":
                yearly_total += total

    selected_frequency_label = None
    for f in frequencies:
        if f.get("selected"):
            selected_frequency_label = f.get("label")
            break

    if selected_frequency_label:
        temp_total_freq = total_frequencies
        for s in services:
            total = s.get("total", 0.0) + temp_total_freq

            if selected_frequency_label == "Mensile":
                monthly_total += total
            elif selected_frequency_label == "Trimestrale":
                quarterly_total += total
            elif selected_frequency_label == "Semestrale":
                biannual_total += total
            elif selected_frequency_label == "Annuale":
                yearly_total += total
            temp_total_freq = 0

    grand_total = total_tiers + total_services + total_products + total_frequencies

    from babel.numbers import format_decimal
    def fmt_ch(val):
        if val is None:
            return "0"
        return format_decimal(val, format='#,##0', locale='de_CH')

    raw_totals = {
        "tiers": total_tiers,
        "services": total_services,
        "products": total_products,
        "monthly": monthly_total,
        "monthly_annual": monthly_total * 12,
        "quarterly": quarterly_total,
        "quarterly_annual": quarterly_total * 4,
        "biannual": biannual_total,
        "biannual_annual": biannual_total * 2,
        "yearly": yearly_total,
        "frequencies": total_frequencies,
        "grand_total": grand_total,
    }

    offer_data["totals_raw"] = raw_totals
    offer_data["totals"] = {k: fmt_ch(v) for k, v in raw_totals.items()}

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
        offer_data = build_offer_data(recordid_deal, data.get('data'))

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
        # template = get_template('activeMind/pdf_template.html')
        # html = template.render(context)
        # response = HttpResponse(content_type="application/pdf")
        # response["Content-Disposition"] = 'inline; filename="offerta.pdf"'
        # pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
        # if pisa_status.err:
        #     return HttpResponse("Errore durante la creazione del PDF", status=500)
        # return response

        html_content = render_to_string(
            'activeMind/pdf_template.html',
            context,
            request=request
        )

        # 6) path PDF temporaneo
        pdf_filename = f"offerta_{recordid_deal}_{uuid.uuid4().hex}.pdf"
        temp_pdf_path = os.path.join(
            BASE_DIR, "tmp", pdf_filename
        )
        os.makedirs(os.path.dirname(temp_pdf_path), exist_ok=True)

        # 6) genera PDF con Playwright
        BrowserManager.generate_pdf(
            html_content=html_content,
            output_path=temp_pdf_path,
        )

        if os.path.exists(temp_pdf_path):            
            def stream_and_delete(path):
                try:
                    with open(path, "rb") as f:
                        while chunk := f.read(8192):
                            yield chunk
                finally:
                    try:
                        os.remove(path)
                    except FileNotFoundError:
                        pass

            response = StreamingHttpResponse(
                stream_and_delete(temp_pdf_path),
                content_type="application/pdf"
            )
            
            return response
        else:
            return HttpResponseNotFound("Il file PDF non è stato generato correttamente.")


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
            SELECT recordid_, name, price, cost
            FROM user_product
            WHERE category = 'ActiveMind' AND subcategory ='system_assurance' AND deleted_ = 'N'
        """)
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
            prod_id, name, price, cost = product
            tiers.append({
                "id": str(prod_id),
                "label": name.replace("System assurance - ", ""),
                "price": float(price) if price is not None else 0.0,
                "cost": float(cost) if cost is not None else 0.0,
                "selected": prod_id in selected_ids
            })

    return JsonResponse({"tiers": tiers})

def get_services_activemind(request):
    """
    Restituisce i servizi ActiveMind:
    - Tutti i dati provengono dal DB (user_product)
    - Quantità recuperate dalla dealline (Manutenzione servizi)
    - Se il servizio non è nella dealline → quantity = 0
    """
    try:
        data = json.loads(request.body)
        recordid_deal = data.get("dealid")
        if not recordid_deal:
            return JsonResponse({"error": "Missing dealid"}, status=400)

        # 1️⃣ Recupero TUTTI i servizi ActiveMind dal DB
        services_dict = {}

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT recordid_, name,description, price, cost, note
                FROM user_product
                WHERE category = 'ActiveMind'
                  AND subcategory = 'services'
                  AND deleted_ = 'N'
                ORDER BY name
            """)
            db_products = cursor.fetchall()

        for recordid_product, name,description, price, cost, note in db_products:
            clean_name = name.replace("AM - ", "").strip()
            key = clean_name.lower()

            services_dict[key] = {
                "recordid_product": recordid_product,
                "id": description,
                "title": clean_name,
                "unitPrice": float(price or 0),
                "unitCost": float(cost or 0),
                "quantity": 0,
                "total": 0,
                "selected": False,
                "icon": "Server",
                "features": [f.strip() for f in note.split(",")] if note else []
            }

        # 2️⃣ Recupero quantità dalla dealline (Manutenzione servizi)
        quantities_map = {}

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT dl.name
                FROM user_dealline dl
                JOIN user_product p
                  ON p.recordid_ = dl.recordidproduct_
                WHERE dl.recordiddeal_ = %s
                  AND p.category = 'ActiveMind'
                  AND p.subcategory = 'services_maintenance'
                  AND dl.deleted_ = 'N'
                  AND p.deleted_ = 'N'
                LIMIT 1
            """, [recordid_deal])
            row = cursor.fetchone()

        if row:
            raw = row[0].replace("AM - Manutenzione servizi - ", "")
            for entry in raw.split(","):
                if ": qta." not in entry:
                    continue
                name, qty = entry.split(": qta.", 1)
                quantities_map[name.strip().lower()] = int(qty.strip())

        # 3️⃣ Calcolo quantità, totale e selected
        for key, s in services_dict.items():
            qty = quantities_map.get(key, 0)
            unit_price = s["unitPrice"]

            total = qty * unit_price

            # Sconto speciale clientPC
            if s["id"] == "clientPC" and qty > 1:
                discount = 1 - (qty - 1) / 100
                total *= discount

            s["quantity"] = qty
            s["total"] = round(total, 2)
            s["selected"] = qty > 0

        return JsonResponse({"services": list(services_dict.values())})

    except Exception as e:
        logger.error(f"Errore in get_services_activemind: {e}")
        return JsonResponse({"error": str(e)}, status=500)
    

def get_products_activemind(request):
    data = json.loads(request.body)
    recordid_deal = data.get('trattativaid')

    if not recordid_deal:
        return JsonResponse({'error': 'Missing trattativaid'}, status=400)

    # 🔹 Icon mapping
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

    categories_dict = {}

    with connection.cursor() as cursor:
        # 1️⃣ Tutti i prodotti ActiveMind
        cursor.execute("""
            SELECT recordid_, name, description, note, price, cost, subcategory
            FROM user_product
            WHERE category = 'ActiveMind'
              AND deleted_ = 'N'
        """)
        db_products = cursor.fetchall()

        # 2️⃣ Quantità dalla trattativa
        cursor.execute("""
            SELECT recordidproduct_, quantity, frequency
            FROM user_dealline
            WHERE recordiddeal_ = %s
              AND deleted_ = 'N'
        """, [recordid_deal])
        deal_rows = cursor.fetchall()

    quantity_map = {row[0]: row[1] for row in deal_rows}
    frequency_map = {row[0]: row[2] for row in deal_rows}

    excluded_subcategories = {
        'services',
        'services_maintenance',
        'system_assurance',
        'conditions'
    }

    # 3️⃣ Costruzione dinamica categorie + servizi
    for recordid_, name, description, note, price, cost, subcategory in db_products:
        if not subcategory or subcategory in excluded_subcategories:
            continue

        # creo la categoria se non esiste
        if subcategory not in categories_dict:
            categories_dict[subcategory] = {
                "id": subcategory,
                "title": subcategory.replace("_", " ").title(),
                "services": []
            }

        features = [f.strip() for f in note.split(",")] if note else []
        quantity = quantity_map.get(recordid_, 0)
        frequency = frequency_map.get(recordid_, "")

        matched_icon = next(
            (icon for key, icon in icon_map.items() if key.lower() in name.lower()),
            None
        )

        service = {
            "id": str(recordid_),
            "title": name.replace("AM - ", ""),
            "description": description,
            "category": subcategory,
            "icon": matched_icon,
            "unitPrice": float(price or 0),
            "unitCost": float(cost or 0),
            "monthlyPrice": float(price) if price else None,
            "yearlyPrice": float(price) * 10.5 if price else None,
            "features": features,
            "quantity": quantity,
            "billingType": "yearly" if frequency == "Annuale" else "monthly",
        }

        categories_dict[subcategory]["services"].append(service)

    # 4️⃣ Output finale
    return JsonResponse(
        {"servicesCategory": list(categories_dict.values())},
        safe=False
    )



def get_conditions_activemind(request):
    data = json.loads(request.body)
    recordid_deal = data.get('dealid')

    if not recordid_deal:
        return JsonResponse({'error': 'Missing dealid'}, status=400)

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT recordid_, name, description, price, note
            FROM user_product
            WHERE category LIKE 'ActiveMind' AND subcategory LIKE 'conditions' AND deleted_ = 'N'
        """)
        products = cursor.fetchall()

        cursor.execute("""
            SELECT dl.frequency
            FROM user_dealline dl
            JOIN user_product p
            ON p.recordid_ = dl.recordidproduct_
            WHERE dl.recordiddeal_ = %s
            AND p.subcategory = 'services_maintenance'
            AND p.category = 'ActiveMind'
            AND dl.deleted_ = 'N'
            AND p.deleted_ = 'N'
            LIMIT 1
        """, [recordid_deal])
        row = cursor.fetchone()
        selected_frequency = row[0] if row else None

    conditions_list = []
    for recordid_product, name, description, price, note in products:
        clean_name = name.replace("AM - ", "").strip()

        operations_in_one_year = None

        if note:
            match_ops = re.search(r'operationsInOneYear\s*:\s*(\d+)', note)

            if match_ops:
                operations_in_one_year = int(match_ops.group(1))
        
        conditions_list.append({
            "id": clean_name,
            "label": clean_name,
            "description": description or "",
            "recordid_product": recordid_product,
            "price": float(price) if price else 0.0,
            "selected": clean_name == selected_frequency,
            "icon": "Calendar",
            "operationsInOneYear": operations_in_one_year,
        })

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
    tableid = data.get("tableid")
    recordid = data.get("recordid")

    return_badgeItems = {}

    # Record company
    record_company = UserRecord(tableid, recordid)
    fields = record_company.fields

    company_name     = fields.get("companyname", {})
    company_email    = fields.get("email", {})
    company_phone    = fields.get("phonenumber", {})
    company_address  = fields.get("address", {})
    customertype     = fields.get("customertype", {})
    paymentstatus    = fields.get("paymentstatus", {})
    salesuser        = fields.get("salesuser", {})

    # Sales user
    if salesuser and salesuser.get("value"):
        from commonapp.models import SysUser
        user_sales = SysUser.objects.filter(id=salesuser["value"]).first()
        return_badgeItems["sales_user_name"] = (
            f"{user_sales.firstname} {user_sales.lastname}" if user_sales else ''
        )
        return_badgeItems["sales_user_photo"] = user_sales.id if user_sales else ''
    else:
        return_badgeItems["sales_user_name"] = ''
        return_badgeItems["sales_user_photo"] = ''

    # --- Aggregations (SQL necessario) ---

    sql = f"""
        SELECT COUNT(worktime_decimal) AS total
        FROM user_timesheet
        WHERE recordidcompany_='{recordid}' AND deleted_='N'
    """
    total_timesheet = HelpderDB.sql_query_value(sql, 'total') or 0

    sql = f"""
        SELECT COUNT(*) AS total
        FROM user_deal
        WHERE dealstatus='Vinta'
        AND recordidcompany_='{recordid}'
        AND deleted_='N'
    """
    total_deals = HelpderDB.sql_query_value(sql, 'total') or 0

    sql = f"""
        SELECT SUM(totalnet) AS total
        FROM user_invoice
        WHERE recordidcompany_='{recordid}'
        AND status='Paid'
        AND deleted_='N'
    """
    total_invoices = HelpderDB.sql_query_value(sql, 'total')
    total_invoices = round(total_invoices, 0) if total_invoices else 0.00

    # --- Badge items ---

    return_badgeItems["company_logo"]   = ''  # se non gestito da UserRecord
    return_badgeItems["company_name"]   = company_name.get("value", '')
    return_badgeItems["company_email"]  = company_email.get("value", '')
    return_badgeItems["company_phone"]  = company_phone.get("value", '')
    return_badgeItems["company_address"] = company_address.get("value", '')
    return_badgeItems["payment_status"] = paymentstatus.get("value", '')
    return_badgeItems["customer_type"]  = customertype.get("value", '')

    return_badgeItems["total_timesheet"] = total_timesheet
    return_badgeItems["total_deals"]     = total_deals
    return_badgeItems["total_invoices"]  = total_invoices

    response = {"badgeItems": return_badgeItems}
    return JsonResponse(response)

def get_record_badge_swissbix_deals(request):
    data = json.loads(request.body)
    tableid = data.get("tableid")
    recordid = data.get("recordid")

    return_badgeItems = {}

    # Deal record
    record_deal = UserRecord(tableid, recordid)
    fields = record_deal.fields

    deal_name = fields.get("dealname", {})
    deal_amount = fields.get("amount", {})
    deal_effectivemargin = fields.get("effectivemargin", {})
    deal_stage = fields.get("dealstage", {})
    salesuser = fields.get("dealuser1", {})
    company = fields.get("recordidcompany_", {})

    # Sales user
    if salesuser and salesuser.get("value"):
        user_sales = SysUser.objects.filter(id=salesuser["value"]).first()
        return_badgeItems["sales_user_name"] = (
            f"{user_sales.firstname} {user_sales.lastname}" if user_sales else ''
        )
        return_badgeItems["sales_user_photo"] = user_sales.id if user_sales else ''
    else:
        return_badgeItems["sales_user_name"] = ''
        return_badgeItems["sales_user_photo"] = ''

    # Badge items
    return_badgeItems["deal_name"] = deal_name.get("value", '')
    return_badgeItems["deal_amount"] = deal_amount.get("value", 0)
    return_badgeItems["deal_effectivemargin"] = deal_effectivemargin.get("value", 0)
    return_badgeItems["deal_stage"] = deal_stage.get("value", '')

    return_badgeItems["company_id"] = company.get("value", '')
    return_badgeItems["company_name"] = company.get("convertedvalue", '')

    response = {"badgeItems": return_badgeItems}
    return JsonResponse(response)


def get_record_badge_swissbix_project(request):
    data = json.loads(request.body)
    tableid = data.get("tableid")
    recordid = data.get("recordid")

    return_badgeItems = {}

    # Project record
    record_project = UserRecord(tableid, recordid)
    fields = record_project.fields

    project_name = fields.get("projectname", {})
    project_status = fields.get("status", {})
    expected_hours = fields.get("expectedhours", {})
    used_hours = fields.get("usedhours", {})
    residual_hours = fields.get("residualhours", {})
    manager = fields.get("assignedto", {})
    company = fields.get("recordidcompany_", {})

    # Project manager
    if manager and manager.get("value"):
        from commonapp.models import SysUser
        user_manager = SysUser.objects.filter(id=manager["value"]).first()
        return_badgeItems["manager_name"] = (
            f"{user_manager.firstname} {user_manager.lastname}" if user_manager else ''
        )
        return_badgeItems["manager_photo"] = user_manager.id if user_manager else ''
    else:
        return_badgeItems["manager_name"] = ''
        return_badgeItems["manager_photo"] = ''

    # Badge items
    return_badgeItems["project_name"] = project_name.get("value", '')
    return_badgeItems["project_status"] = project_status.get("value", '')
    return_badgeItems["expected_hours"] = expected_hours.get("value", 0)
    return_badgeItems["used_hours"] = used_hours.get("value", 0)
    return_badgeItems["residual_hours"] = residual_hours.get("value", 0)

    return_badgeItems["company_id"] = company.get("value", '')
    return_badgeItems["company_name"] = company.get("convertedvalue", '')

    response = {"badgeItems": return_badgeItems}
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
    
    filename = re.sub(r'[^a-zA-Z0-9\-_]', '', reference.replace(' ', '_')) if reference else f"offerta_{recordid_deal}"

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
        rt_prodotto.add(f"{name}:\n", size=20, underline=True)
        rt_prodotto.add("\tQuantità: ", size=20)
        rt_prodotto.add(qty_str, bold=True, size=20)
        rt_prodotto.add("\t|\tPrezzo unitario: ", size=20)
        rt_prodotto.add(unit_str, bold=True, size=20)
        rt_prodotto.add("\t|\tTotale: ", size=20)
        rt_prodotto.add(price_str, bold=True, size=20)
        rt_prodotto.add("\n\n", size=20)

        lines.append(rt_prodotto)

    # Crea il titolo
    # Crea il separatore
    separatore = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Crea il totale finale
    total_str = f"CHF {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    rt_totale = RichText()
    rt_totale.add('TOTALE COMPLESSIVO: ', bold=True, size=22)
    rt_totale.add(total_str, bold=True, size=22)

    # Combina tutti i prodotti in un unico RichText
    rt_all_products = RichText()
    for rt_prod in lines:
        # Aggiungi il contenuto di ogni prodotto
        rt_all_products.add(rt_prod)

    # Crea il documento completo
    tabella_completa = RichText()
    tabella_completa.add(separatore, color='gray', size=18)
    tabella_completa.add('\n\n')
    tabella_completa.add(rt_all_products)
    tabella_completa.add(separatore, color='gray', size=18)
    tabella_completa.add('\n\n')
    tabella_completa.add(rt_totale)
    tabella_completa.add('\n\n')
    tabella_completa.add(separatore, color='gray', size=18)

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
            record=UserRecord(tableid,recordid, userid=Helper.get_userid(request),master_tableid=master_tableid,master_recordid=master_recordid)
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


def ensure_playwright_installed():
    """Garantisce che il browser Chromium sia presente."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)

def to_base64(path):
    """Converte immagine locale in Base64 per l'incorporamento nel PDF."""
    if path and os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception as e:
            print(f"Errore conversione Base64: {e}")
    return None

def generate_timesheet_pdf(recordid, signature_path=None):
    """
    Genera il PDF del timesheet con firma condizionale e footer fisso.
    """
    try:
        ensure_playwright_installed()

        base_path = os.path.normpath(os.path.join(settings.STATIC_ROOT, 'pdf'))
        os.makedirs(base_path, exist_ok=True)

        q_path = os.path.join(base_path, f"qr_{uuid.uuid4().hex}.png")
        qr = qrcode.QRCode(box_size=10, border=0)
        qr.add_data(f"timesheet_{recordid}")
        qr.make(fit=True)
        qr.make_image(fill_color="black", back_color="white").save(q_path)

        rows = HelpderDB.sql_query(f"""
            SELECT t.*, c.companyname, c.address, c.city, c.email, c.phonenumber, 
                   u.firstname, u.lastname 
            FROM user_timesheet AS t 
            JOIN user_company AS c ON t.recordidcompany_=c.recordid_ 
            JOIN sys_user AS u ON t.user = u.id 
            WHERE t.recordid_='{recordid}'
        """)

        if not rows:
            raise Exception(f"Nessun timesheet trovato per recordid {recordid}")

        row = rows[0]
        for k in row: row[k] = row[k] or ''

        row['qrUrl'] = to_base64(q_path)
        row['signatureUrl'] = to_base64(signature_path)
        row['recordid'] = recordid

        timesheetlines = HelpderDB.sql_query(
            f"SELECT * FROM user_timesheetline WHERE recordidtimesheet_='{recordid}'"
        )
        for line in timesheetlines:
            line['note'] = line.get('note') or ''
            line['expectedquantity'] = line.get('expectedquantity') or ''
            line['actualquantity'] = line.get('actualquantity') or ''
        row['timesheetlines'] = timesheetlines

        html_content = render_to_string('pdf/timesheet_signature.html', row)
        pdf_filename = f"timesheet_{recordid}.pdf"
        temp_pdf_path = os.path.join(base_path, pdf_filename)

        css = """
                /* Rimuove l'altezza forzata che spesso crea la seconda pagina */
                html, body { 
                    height: auto !important; 
                    overflow: hidden !important; 
                    margin: 0 !important; 
                    padding: 0 !important;
                }
                
                /* Evita che il footer fixed forzi un salto pagina se troppo vicino al bordo */
                div[style*="position:fixed"] {
                    position: absolute !important;
                    bottom: 0 !important;
                }

                /* Rimuove spazi bianchi finali indesiderati */
                body:after {
                    content: none !important;
                }
                
                /* Ottimizzazione scala */
                body {
                    zoom: 0.75;
                }
        """

        BrowserManager.generate_pdf(
            html_content=html_content,
            output_path=temp_pdf_path,
            css_styles=css
        )

        attachment_record = UserRecord('attachment')
        attachment_record.values['type'] = "Signature"
        attachment_record.values['recordidtimesheet_'] = recordid
        attachment_record.save()

        dest_dir = os.path.join(settings.UPLOADS_ROOT, "timesheet", str(recordid))
        os.makedirs(dest_dir, exist_ok=True)
        final_pdf_path = os.path.join(dest_dir, pdf_filename)
        shutil.move(temp_pdf_path, final_pdf_path)

        attachment_record.values['file'] = f"timesheet/{recordid}/{pdf_filename}"
        attachment_record.values['filename'] = pdf_filename
        attachment_record.save()

        if os.path.exists(q_path): os.remove(q_path)

        return pdf_filename

    except Exception as e:
        print(f"Errore in generate_timesheet_pdf: {e}")
        raise

def print_timesheet(request):
    """
    Genera (o rigenera) il PDF del timesheet e lo restituisce per il download.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito'}, status=405)

    try:
        data = json.loads(request.body)
        recordid = data.get('recordid')
        with_signature = data.get('with_signature')

        if not recordid:
            return JsonResponse({'error': 'Recordid mancante'}, status=400)

        attachment_rows = HelpderDB.sql_query(f"""
            SELECT file, filename 
            FROM user_attachment 
            WHERE recordidtimesheet_ = '{recordid}' 
            AND type = 'Signature'
            ORDER BY recordid_ DESC LIMIT 1
        """)

        if not attachment_rows or not with_signature:
            pdf_filename = generate_timesheet_pdf(recordid)
            attachment_rows = HelpderDB.sql_query(f"""
                SELECT file, filename 
                FROM user_attachment 
                WHERE recordidtimesheet_ = '{recordid}' 
                AND type = 'Signature'
                ORDER BY recordid_ DESC LIMIT 1
            """)
        
        file_info = attachment_rows[0]
        relative_path = file_info['file']
        filename = file_info.get('filename', 'timesheet.pdf')

        abs_path = os.path.normpath(os.path.join(settings.UPLOADS_ROOT, relative_path))

        if not os.path.exists(abs_path):
            return JsonResponse({'error': f'File non trovato sul server: {relative_path}'}, status=404)

        response = FileResponse(open(abs_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response

    except Exception as e:
        print(f"Errore in print_timesheet: {e}")
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
        ensure_playwright_installed()
        
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
        content = render_to_string('pdf/timesheet_signature.html', row)
        pdf_filename = f"allegato.pdf"
        pdf_path = os.path.join(base_path, pdf_filename)

        css = """
                html, body { height: auto !important; overflow: hidden !important; margin: 0 !important; }
                body { zoom: 0.98; }
                div[style*="position:fixed"] { position: absolute !important; bottom: 0 !important; }
        """
        
        BrowserManager.generate_pdf(
            html_content=content, 
            output_path=pdf_path, 
            css_styles=css,
            options={"margin": {"top": "1cm", "bottom": "0.5cm", "left": "1cm", "right": "1cm"}}
        )

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


def get_project_templates(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT recordid_, templatename
                FROM user_projecttemplate
                WHERE deleted_ = 'N'
            """)
            rows = cursor.fetchall()

        # Mappo i risultati per il FE
        templates = [
            {
                "id": str(row[0]),
                "value": row[1]
            }
            for row in rows
        ]

        return JsonResponse({"templates": templates}, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
def save_project_as_template(request):
    if request.method != "POST":
        return JsonResponse({"error": "Metodo non permesso"}, status=405)

    try:
        data = json.loads(request.body)

        project_id = data.get("recordid")
        template_id = data.get("template")

        if not project_id or not template_id:
            return JsonResponse({"error": "Parametri mancanti"}, status=400)

        userid = Helper.get_userid(request)
        # 🔹 Carico il record del progetto
        project_record = UserRecord("project", project_id, userid)

        if not project_record.values:
            return JsonResponse({"error": "Record progetto non trovato"}, status=404)

        # 🔹 Carico il record del template
        template_record = UserRecord("projecttemplate", template_id, userid)

        if not template_record.values:
            return JsonResponse({"error": "Template non trovato"}, status=404)

        # 🔥 Sovrascrivo i valori del progetto con quelli del template
        project_values = project_record.values
        template_values = template_record.values

        exclueded_fields = ['id', 'recordid_', 'creatorid_', 'creation_', 'lastupdaterid_', 'lastupdate_', 'totpages_', 'firstpagefilename_', 'recordstatus_', 'deleted_',]

        for fieldid, template_value in template_values.items():
            # ❗ non sovrascrivere ID o altre chiavi protette
            if fieldid in exclueded_fields:
                continue

            # aggiorna solo se esiste anche nel progetto
            if fieldid in project_values:
                project_values[fieldid] = template_value

        # 🔥 Salvo le modifiche
        project_record.save()

        tables = template_record.get_linked_tables()

        linked_tables_real_raw = project_record.get_linked_tables()
        linked_tables_real = [t["tableid"] for t in linked_tables_real_raw]

        for table in tables:
            template_table_id = table["tableid"]
            
            # es: da "projecttemplatechecklist" → "projectchecklist"
            real_table_id = template_table_id.replace("projecttemplate", "")

            if real_table_id not in linked_tables_real:
                continue

            old_records = project_record.get_linkedrecords_dict(real_table_id)

            for old in old_records:
                old_rec = UserRecord(real_table_id, old["recordid_"])
                old_rec.values["deleted_"] = "Y"
                old_rec.save()

            linked_records = template_record.get_linkedrecords_dict(template_table_id)

            for record in linked_records:

                # 🔥 CREO NUOVO RECORD NELLA TABELLA REALE
                new_rec = UserRecord(real_table_id)

                # Copio tutti i campi tranne quelli di sistema
                for fieldid, val in record.items():
                    if fieldid in exclueded_fields:
                        continue

                    # Se il campo contiene "projecttemplate", trasformalo in "project"
                    # Es: recordidprojecttemplate_ → recordidproject_
                    new_fieldid = fieldid.replace("projecttemplate", "project")

                    # TODO handle fields type FILE
                    new_rec.values[new_fieldid] = val

                # Imposto il recordid del progetto (campo di relazione)
                new_rec.values[f"recordidproject_"] = project_id

                # Salvo il nuovo record
                new_rec.save()

        return JsonResponse({"success": True, "message": "Template applicato correttamente."})

    except Exception as e:
        print("Errore:", e)
        return JsonResponse({"error": str(e)}, status=500)
def get_timesheets_to_invoice(request):
    from customapp_swissbix.script import get_timesheets_to_invoice
    return get_timesheets_to_invoice(request)

def upload_timesheet_in_bexio(request):
    from customapp_swissbix.script import upload_timesheet_in_bexio
    return upload_timesheet_in_bexio(request)

def get_timetracking(request):
    from customapp_swissbix.script import get_timetracking
    return get_timetracking(request)

def resume_timetracking(request):
    from customapp_swissbix.script import resume_timetracking
    return resume_timetracking(request)

def delete_timetracking(request):
    from customapp_swissbix.script import delete_timetracking
    return delete_timetracking(request)

def update_timetracking(request):
    from customapp_swissbix.script import update_timetracking
    return update_timetracking(request)

def save_timetracking(request):
    from customapp_swissbix.script import save_timetracking
    return save_timetracking(request)

def stop_timetracking(request):
    from customapp_swissbix.script import stop_timetracking
    return stop_timetracking(request)

def get_timesheet_initial_data(request):
    from customapp_swissbix.script import get_timesheet_initial_data
    return get_timesheet_initial_data(request)

def save_timesheet(request):
    from customapp_swissbix.script import save_timesheet
    return save_timesheet(request)

def save_timesheet_material(request):
    from customapp_swissbix.script import save_timesheet_material
    return save_timesheet_material(request)

def remove_timesheet_material(request):
    from customapp_swissbix.script import remove_timesheet_material
    return remove_timesheet_material(request)

def save_timesheet_attachment(request):
    from customapp_swissbix.script import save_timesheet_attachment
    return save_timesheet_attachment(request)

def remove_timesheet_attachment(request):
    from customapp_swissbix.script import remove_timesheet_attachment
    return remove_timesheet_attachment(request)

def search_timesheet_entities(request):
    from customapp_swissbix.script import search_timesheet_entities
    return search_timesheet_entities(request)

def upload_markdown_image(request):
    from customapp_swissbix.script import upload_markdown_image
    return upload_markdown_image(request)

def get_monitoring(request):
    from customapp_swissbix.script import get_monitoring
    return get_monitoring()

def check_ai_status(request):
    from customapp_swissbix.script import check_ai_server

    is_online, message = check_ai_server()
    if is_online:
        print(f"✅  {message}")
        return JsonResponse({"status": True})
    else:
        print(f"❌  {message}")
        return JsonResponse({"status": False})

def check_ai_chat_status(request):
    from customapp_swissbix.script import check_ai_chat_server

    is_online, message = check_ai_chat_server()
    if is_online:
        print(f"✅  {message}")
        return JsonResponse({"status": True})
    else:
        print(f"❌  {message}")
        return JsonResponse({"status": False})

def get_bixhub_initial_data(request):
    from customapp_swissbix.script import get_bixhub_initial_data
    return get_bixhub_initial_data(request)