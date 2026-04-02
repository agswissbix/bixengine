from customapp_swissbix.helper import HelperSwissbix
import datetime
from datetime import timedelta
import os
import uuid
import base64
import logging
import json
from django.http import JsonResponse, HttpResponseNotFound, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from bixengine.settings import BASE_DIR
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *
import shutil
from customapp_swissbix.custom_handlers import save_record_fields
from types import SimpleNamespace
from commonapp.models import SysUser
from customapp_swissbix.utils.browser_manager import BrowserManager
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

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
            response_data["cliente"]["deal_user"] = record_deal.fields.get('dealuser1', None)['convertedvalue']
        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Si è verificato un errore inatteso: {str(e)}'
        }, status=500)

def process_save_activemind_data(data):
    recordid_deal = data.get('recordIdTrattativa')

    if not recordid_deal:
        raise ValueError('recordIdTrattativa mancante.')

    # -------------------------------------------------
    # Helper Functions
    # -------------------------------------------------
    def fetch_existing_dealline(recordid_deal, subcategory, recordidproduct=None):
        query = """
            SELECT dl.recordid_
            FROM user_dealline dl
            JOIN user_product p
            ON p.recordid_ = dl.recordidproduct_
            WHERE dl.recordiddeal_ = %s
            AND p.subcategory = %s
            AND p.category = 'ActiveMind'
            AND dl.deleted_ = 'N'
            AND p.deleted_ = 'N'
        """
        params = [recordid_deal, subcategory]

        if recordidproduct is not None:
            query += " AND dl.recordidproduct_ = %s"
            params.append(recordidproduct)

        query += " LIMIT 1"

        with connection.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return row[0] if row else None

    def save_dealline(values):
        rec_id = values.get('recordid_')
        record = UserRecord('dealline', rec_id) if rec_id else UserRecord('dealline')

        for k, v in values.items():
            if k != 'recordid_':
                record.values[k] = v

        computed = HelperSwissbix.compute_dealline_fields(record.values, UserRecord)
        record.values.update(computed)
        record.save()
        # save_record_fields('dealline', record.recordid)
        return record.recordid

    def remove_dealline(recordid_dealline):
        record = UserRecord('dealline', recordid_dealline)
        record.values['deleted_'] = 'Y'
        record.save()

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
            raise ValueError(f'Prodotto con ID {product_id} non trovato.')

        existing_id = fetch_existing_dealline(recordid_deal, "system_assurance")

        save_dealline({
            'recordid_': existing_id,
            'recordiddeal_': recordid_deal,
            'recordidproduct_': product.values.get('recordid_'),
            'name': product.values.get('name'),
            'unitprice': price,
            'unitexpectedcost': cost,
            'quantity': 1
        })
    else:
        remove_dealline(fetch_existing_dealline(recordid_deal, "system_assurance"))

    # -------------------------------------------------
    # Estrarre constraint / calcolare sconto
    # -------------------------------------------------
    client_info = data.get('clientInfo', {})
    contract_constraint = int(client_info.get('contractConstraint', 12))
    
    discount_percentage = 0
    if contract_constraint == 24:
        discount_percentage = 5
    elif contract_constraint == 36:
        discount_percentage = 10
        
    discount_rate = discount_percentage / 100.0

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
        billing_type = product_data.get('billingType', 'Trimestrale')
        name = product.values.get('name')

        existing_id = fetch_existing_dealline(recordid_deal, product.values.get('subcategory', ''), product.recordid)

        if quantity <= 0:
            if existing_id:
                remove_dealline(existing_id)
            continue

        unitprice_discounted = unit_price * (1 - discount_rate)

        save_dealline({
            'recordid_': existing_id,
            'recordiddeal_': recordid_deal,
            'recordidproduct_': product.values.get('recordid_'),
            'name': name,
            'unitprice': unitprice_discounted * 3,
            'unitexpectedcost': unit_cost * 3,
            'quantity': quantity,
            'frequency': 'Annuale' if billing_type == 'yearly' else 'Trimestrale',
            'contractual_obligation': contract_constraint,
            'discount': discount_percentage
        })

    # -------------------------------------------------
    # SECTION 3 — Servizi (una riga dealline per servizio)
    # -------------------------------------------------
    services = data.get('section2Services', {})
    conditions = data.get('section3', {})
    frequency = conditions.get('selectedFrequency', 'Mensile')

    for product_key, service in services.items():
        product_key_str = str(service.get('idproduct', ''))
        qty = int(service.get('quantity', 0))
        unit_price = float(service.get('unitPrice', 0))
        unit_cost = float(service.get('unitCost', 0))
        title = service.get('title', '')

        existing_id = fetch_existing_dealline(recordid_deal, service.get('subcategory', ''), product_key_str)

        if qty <= 0:
            if existing_id:
                remove_dealline(existing_id)
            continue

        unitprice_discounted = unit_price * (1 - discount_rate)

        # Fatturazione trimestrale: moltiplica i valori unitari x3
        save_dealline({
            'recordid_': existing_id,
            'recordiddeal_': recordid_deal,
            'recordidproduct_': product_key_str,
            'name': title,
            'unitprice': unitprice_discounted * 3,
            'unitexpectedcost': unit_cost * 3,
            'quantity': qty,
            'intervention_frequency': frequency,
            'frequency': 'Trimestrale',
            'contractual_obligation': contract_constraint,
            'discount': discount_percentage
        })

    # -------------------------------------------------
    # SECTION Assistance BwBix
    # -------------------------------------------------
    sectionAssistanceBwbix = data.get('sectionAssistanceBwbix', {})
    if sectionAssistanceBwbix:
        product_id = sectionAssistanceBwbix.get('selectedOption')
        name_str = sectionAssistanceBwbix.get('label')
        existing_id = fetch_existing_dealline(recordid_deal, 'assistance_bwbix')
        if not product_id or product_id == '':
            if existing_id:
                remove_dealline(existing_id)
        else:
            save_dealline({
                'recordid_': existing_id,
                'recordiddeal_': recordid_deal,
                'recordidproduct_': product_id,
                'name': name_str,
                'unitprice': sectionAssistanceBwbix.get('price', 0),
                'unitexpectedcost': sectionAssistanceBwbix.get('cost', 0),
                'quantity': 1,
            })

    # -------------------------------------------------
    # SECTION 4 — Monte Ore
    # -------------------------------------------------
    
    sectionHours = data.get('sectionHours', {})
    if not sectionHours:
        return True

    product_id = sectionHours.get('selectedOption')

    if not product_id or product_id == '':
        return True

    name_str = sectionHours.get('label')

    existing_id = fetch_existing_dealline(recordid_deal, 'monte_ore')
    existing_id_bwbix = fetch_existing_dealline(recordid_deal, 'monte_ore_bwbix')

    if existing_id:
        remove_dealline(existing_id)
    if existing_id_bwbix:
        remove_dealline(existing_id_bwbix)

    save_dealline({
        'recordid_': existing_id,
        'recordiddeal_': recordid_deal,
        'recordidproduct_': product_id,
        'name': name_str,
        'unitprice': sectionHours.get('price', 0),
        'unitexpectedcost': sectionHours.get('cost', 0),
        'quantity': 1,
    })

    return True

def save_activemind(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Metodo non permesso. Utilizza POST.'}, status=405)

    try:
        request_body = json.loads(request.body or "{}")
        data = request_body.get('data', {})
        recordid_deal = data.get('recordIdTrattativa')
        
        process_save_activemind_data(data)

        save_record_fields('deal', recordid_deal)

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
    # 5. SECTION 4 → Monte Ore
    # -----------------------------
    if fe_data.get("sectionHours").get("selectedOption"):
        req_monte_ore = type('Req', (object,), {"body": json.dumps({"dealid": recordid_deal})})
        monte_ore_resp = get_monte_ore_activemind(req_monte_ore)
        monte_ore = json.loads(monte_ore_resp.content)["options"]
        for m in monte_ore:
            if m.get("selected"):
                offer_data["monte_ore"] = monte_ore
                break
        if not offer_data.get("monte_ore"):
            offer_data["monte_ore"] = []
    else:
        offer_data["monte_ore"] = []

    # -----------------------------
    # 5.5. SECTION Assistance BwBix
    # -----------------------------
    if fe_data and fe_data.get("sectionAssistanceBwbix", {}).get("selectedOption"):
        req_assistance_bwbix = type('Req', (object,), {"body": json.dumps({"dealid": recordid_deal})})
        assistance_bwbix_resp = get_assistance_bwbix_activemind(req_assistance_bwbix)
        assistance_bwbix_list = json.loads(assistance_bwbix_resp.content)["options"]
        for m in assistance_bwbix_list:
            if m.get("selected"):
                offer_data["assistance_bwbix"] = assistance_bwbix_list
                break
        if not offer_data.get("assistance_bwbix"):
            offer_data["assistance_bwbix"] = []
    else:
        offer_data["assistance_bwbix"] = []

    # -----------------------------
    # 7. SERVICE & ASSETS (Pass-through)
    # -----------------------------
    req_service_asset = type('Req', (object,), {"body": json.dumps({"dealid": recordid_deal})})
    service_asset_resp = get_service_and_asset_activemind(req_service_asset)
    service_asset = json.loads(service_asset_resp.content)["options"]
    offer_data["service_assets"] = service_asset

    # -----------------------------
    # 6. CALCOLO TOTALE → solo su ciò che è stato caricato
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

    monte_ore_list = offer_data.get("monte_ore", [])
    total_monte_ore = 0.0
    for m in monte_ore_list:
        if m.get("selected"):
            total_monte_ore += float(m.get("price", 0.0))

    assistance_bwbix_list = offer_data.get("assistance_bwbix", [])
    total_assistance_bwbix = 0.0
    for m in assistance_bwbix_list:
        if m.get("selected"):
            total_assistance_bwbix += float(m.get("price", 0.0))

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
                monthly_total += total /12
                yearly_total += total

    selected_frequency_label = None
    for f in frequencies:
        if f.get("selected"):
            selected_frequency_label = f.get("label")
            break

    monthly_total += total_services
    monthly_total += total_assistance_bwbix
    
    contract_constraint = fe_data.get("clientInfo", {}).get("contractConstraint", 12) if fe_data else 12
    discount_rate = 0.10 if contract_constraint == 36 else 0.05 if contract_constraint == 24 else 0.0
    
    monthly_total_discounted = monthly_total * (1 - discount_rate)
    quarterly_total_discounted = monthly_total_discounted * 3
    yearly_total_discounted = monthly_total_discounted * 12

    grand_total = (monthly_total_discounted * 12) + yearly_total_discounted + total_monte_ore + total_tiers

    raw_totals = {
        "tiers": total_tiers,
        "services": total_services,
        "products": total_products,
        "monthly": monthly_total,
        "monthly_discounted": monthly_total_discounted,
        "monthly_annual": monthly_total * 12,
        "monthly_annual_discounted": monthly_total_discounted * 12,
        "quarterly": quarterly_total,
        "quarterly_annual": quarterly_total * 4,
        "quarterly_annual_discounted": quarterly_total_discounted,
        "biannual": biannual_total,
        "biannual_annual": biannual_total * 2,
        "yearly": yearly_total,
        "yearly_discounted": yearly_total_discounted,
        "frequencies": total_frequencies,
        "monte_ore": total_monte_ore,
        "assistance_bwbix": total_assistance_bwbix,
        "grand_total": grand_total,
        "contract_constraint": contract_constraint,
        "discount_pct": int(discount_rate * 100),
        "discount_amount_monthly": monthly_total - monthly_total_discounted,
    }

    offer_data["totals_raw"] = raw_totals
    offer_data["totals"] = {k: v if isinstance(v, (int, float)) else v for k, v in raw_totals.items()}

    # Aggiungi info sulla pianificazione se presente
    offer_data["pianificazione_label"] = selected_frequency_label

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
    limit = 4
    for s in iterable:
        # supporta sia oggetti sia dict
        qty = getattr(s, "quantity", s.get("quantity", 0) if isinstance(s, dict) else 0)
        feats = getattr(s, "features", s.get("features", []) if isinstance(s, dict) else [])
        if qty == 0:
            continue
        if len(feats) > 6:
            limit = 3
            if counter >= 3:
                pages.append(page)
                page = []
                counter = 0
        page.append(s)
        counter += 1
        if counter >= limit:
            pages.append(page)
            page = []
            counter = 0
            limit = 4
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

        is_bwbix = data.get('isBwbix', False)

        signature_url = None
        if digital_signature_b64:
            # Se è già un data URL, lo usiamo direttamente
            if "data:image" in digital_signature_b64 and ";base64," in digital_signature_b64:
                signature_url = digital_signature_b64
            else:
                # Altrimenti proviamo a ricostruire il data URL assumendo sia PNG o che vada bene così
                # Se c'è una virgola ma mancava l'intestazione, prendiamo la parte dopo
                if "," in digital_signature_b64:
                    # Probabilmente ha un'intestazione parziale o diversa, normalizziamo?
                    # Nel dubbio, se il frontend manda data:image/png;base64,... è perfetto.
                    signature_url = digital_signature_b64
                else:
                    signature_url = f"data:image/png;base64,{digital_signature_b64}"

        # Convertiamo le immagini statiche in Base64
        import os
        from django.conf import settings
        static_img_path = os.path.join(settings.BASE_DIR, "customapp_swissbix/static/images")
        img_cover = HelperSwissbix.to_base64(os.path.join(static_img_path, "cover.png"))
        if is_bwbix:
            img_cover = HelperSwissbix.to_base64(os.path.join(static_img_path, "cover_bwbix.jpg"))
        img_systemassurance = HelperSwissbix.to_base64(os.path.join(static_img_path, "systemassurance.png"))
        img_prodotti = HelperSwissbix.to_base64(os.path.join(static_img_path, "prodotti_beall.jpg"))
        img_servizi = HelperSwissbix.to_base64(os.path.join(static_img_path, "servizi.jpg"))

        # 0) Salva dati prima di stampare
        save_data = data.get('data', {})
        save_data['recordIdTrattativa'] = recordid_deal
        try:
            process_save_activemind_data(save_data)
        except Exception as e:
            logger.error(f"Errore nel salvataggio prima della stampa: {str(e)}")
            return JsonResponse({'error': f'Errore nel salvataggio preliminare: {str(e)}'}, status=500)

        # 1) ricostruzione offerta
        offer_data = build_offer_data(recordid_deal, save_data)

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

        # 2b) Filter lists for Summary Table (needed for correct rowspan calculation)
        summary_products = [p for p in product_objs if getattr(p, "quantity", 0) > 0]
        summary_services = [s for s in offer_data.get("services", []) if s.get("quantity", 0) > 0]
        summary_monte_ore = [m for m in offer_data.get("monte_ore", []) if m.get("selected")]

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
            "deal_user": record_deal.fields.get('dealuser1', None)['convertedvalue'] or "Davide Crudo",
            "offer_data": offer_data,
            "section2_services_pages": section2_services_pages,
            "section2_products_pages": section2_products_pages,
            "context_summary_products": summary_products,
            "context_summary_services": summary_services,
            "context_summary_monte_ore": summary_monte_ore,
            "context_summary_assistance_bwbix": [m for m in offer_data.get("assistance_bwbix", []) if m.get("selected")],
            "context_service_assets": offer_data.get("service_assets", []),
            # flat per tabella riepilogo finale (se ti serve)
            "section2_products": product_objs,
            "date": datetime.datetime.now().strftime("%d/%m/%Y"),
            "limit_acceptance_date": (datetime.datetime.now() + timedelta(days=10)).strftime("%d/%m/%Y"),
            "digital_signature_url": signature_url,
            "img_cover": img_cover,
            "img_systemassurance": img_systemassurance,
            "img_prodotti": img_prodotti,
            "img_servizi": img_servizi,
            "nameSignature": nameSignature,
            "is_bwbix": is_bwbix,
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
        import uuid
        import os
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

# Helper per le features (prodotti & servizi): 
# se c'è "|", splitta esplicitamente le colonne.
# Altrimenti, splitta per virgola e divide a metà la lista in due colonne.
def parse_features(note_str):
    if not note_str: return []
    
    if "|" in note_str:
        return [[f.strip() for f in col.split(",") if f.strip()] for col in note_str.split("|")]
    else:
        items = [f.strip() for f in note_str.split(",") if f.strip()]
        if not items: return []
        mid = (len(items) + 1) // 2
        return [items[:mid], items[mid:]]

def get_services_activemind(request):
    """
    Restituisce i servizi ActiveMind:
    - Tutti i dati provengono dal DB (user_product)
    - Quantità recuperate dalla dealline (Manutenzione servizi)
    - Se il servizio non è nella dealline → quantity = 0
    - isBwbix=True → restituisce solo prodotti con subcategory 'services_bwbix'
    - isBwbix=False (default) → restituisce prodotti con subcategory 'services'
    """
    try:
        data = json.loads(request.body)
        recordid_deal = data.get("dealid")
        if not recordid_deal:
            return JsonResponse({"error": "Missing dealid"}, status=400)

        is_bwbix = data.get("isBwbix", False)

        # 1️⃣ Recupero TUTTI i servizi ActiveMind dal DB
        services_dict = {}

        if is_bwbix:
            subcategories = ['services_bwbix']
        else:
            subcategories = ['services', 'services_bwbix']

        placeholders = ','.join(['%s'] * len(subcategories))

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT recordid_, name,description, price, cost, note, subcategory
                FROM user_product
                WHERE category = 'ActiveMind'
                  AND subcategory IN ({placeholders})
                  AND deleted_ = 'N'
                ORDER BY name
            """.format(placeholders=placeholders), subcategories)
            db_products = cursor.fetchall()

        for recordid_product, name,description, price, cost, note, subcategory in db_products:
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
                "features": parse_features(note),
                "subcategory": subcategory
            }

        # 2️⃣ Recupero quantità dalla dealline — una riga per prodotto
        params = [recordid_deal] + list(subcategories)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT dl.recordidproduct_, dl.quantity, dl.unitprice, dl.discount
                FROM user_dealline dl
                JOIN user_product p ON p.recordid_ = dl.recordidproduct_
                WHERE dl.recordiddeal_ = %s
                  AND p.category = 'ActiveMind'
                  AND p.subcategory IN ({placeholders})
                  AND dl.deleted_ = 'N'
                  AND p.deleted_ = 'N'
            """.format(placeholders=placeholders), params)
            dealline_rows = cursor.fetchall()

        # Mappa: recordid_product → (quantity, unitprice)
        dealline_map = {
            str(row[0]): {'quantity': int(row[1] or 0), 'unitprice': float(row[2] or 0), 'discount': float(row[3] or 0)}
            for row in dealline_rows
        }

        # 3️⃣ Calcolo quantità, totale e selected
        for key, s in services_dict.items():
            product_id_str = str(s["recordid_product"])
            dl = dealline_map.get(product_id_str)
            if dl:
                # unitprice in DB è già il valore trimestrale; per mostrare il prezzo
                # unitario mensile lo dividiamo per 3
                stored_unit_price = dl['unitprice']
                discount = dl['discount']
                qty = dl['quantity'] if dl['quantity'] else 0
                unit_price = stored_unit_price / 3 if stored_unit_price else s["unitPrice"]
                if discount:
                    unit_price = unit_price / (1 - (discount / 100))
            else:
                qty = 0
                unit_price = s["unitPrice"]

            total = qty * unit_price

            s["unitPrice"] = unit_price
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
            SELECT recordidproduct_, quantity, frequency, unitprice, discount
            FROM user_dealline
            WHERE recordiddeal_ = %s
              AND deleted_ = 'N'
        """, [recordid_deal])
        deal_rows = cursor.fetchall()

    quantity_map = {row[0]: row[1] for row in deal_rows}
    frequency_map = {row[0]: row[2] for row in deal_rows}
    unitprice_map = {row[0]: row[3] for row in deal_rows}
    discount_map = {row[0]: row[4] for row in deal_rows}

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT contractual_obligation, discount
            FROM user_dealline
            WHERE recordiddeal_ = %s
              AND deleted_ = 'N'
            LIMIT 1
        """, [recordid_deal])
        contract_row = cursor.fetchone()
        contract_constraint = contract_row[0] if contract_row and contract_row[0] else 12
        contract_discount = contract_row[1] if contract_row and contract_row[1] else 0

    included_subcategories = {
        'data_security',
        'mobile_security',
        'infrastructure',
        'sophos',
        'microsoft',
        'firewall',
    }

    # 3️⃣ Costruzione dinamica categorie + servizi

    for recordid_, name, description, note, price, cost, subcategory in db_products:
        if subcategory not in included_subcategories:
            continue

        # creo la categoria se non esiste
        if subcategory not in categories_dict:
            categories_dict[subcategory] = {
                "id": subcategory,
                "title": subcategory.replace("_", " ").title(),
                "services": []
            }

        features = parse_features(note)
        quantity = quantity_map.get(recordid_, 0)
        frequency = frequency_map.get(recordid_, "")
        unitprice = unitprice_map.get(recordid_, "")
        discount = discount_map.get(recordid_, "")
        if unitprice:
            if frequency == "Annuale":
                unitprice = unitprice / 12
            if discount:
                price = unitprice / 3 / (1 - (discount / 100))
            else:
                price = unitprice / 3

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
            "unitPrice": float(price or 0) *12 if frequency == "Annuale" else float(price or 0),
            "unitCost": float(cost or 0),
            "monthlyPrice": float(price) if price else None,
            "yearlyPrice": float(price) * 12 if price else None,
            "features": features,
            "quantity": quantity,
            "billingType": "yearly" if frequency == "Annuale" else "monthly",
        }

        categories_dict[subcategory]["services"].append(service)

    # 4️⃣ Output finale
    return JsonResponse({
        "servicesCategory": list(categories_dict.values()),
        "contractConstraint": contract_constraint,
        "discount": contract_discount
    })



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
            SELECT DISTINCT dl.intervention_frequency
            FROM user_dealline dl
            JOIN user_product p ON p.recordid_ = dl.recordidproduct_
            WHERE dl.recordiddeal_ = %s
              AND p.category = 'ActiveMind'
              AND p.subcategory IN ('services', 'services_bwbix')
              AND dl.deleted_ = 'N'
              AND p.deleted_ = 'N'
              AND dl.intervention_frequency IS NOT NULL
              AND dl.intervention_frequency != ''
        """, [recordid_deal])
        freq_rows = cursor.fetchall()
        # Se tutte le righe di servizio hanno la stessa frequenza → selezionata
        frequencies_found = [r[0] for r in freq_rows if r[0]]
        selected_frequency = frequencies_found[0] if len(set(frequencies_found)) == 1 else None

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
            "recordid_product": recordid_product,
            "price": 0.0, # Conditions have no price anymore
            "selected": clean_name == selected_frequency,
            "icon": "Calendar",
            "operationsInOneYear": operations_in_one_year,
        })

    return JsonResponse({"frequencies": conditions_list}, safe=False)


def get_monte_ore_activemind(request):
    data = json.loads(request.body)
    recordid_deal = data.get('dealid')
    is_bwbix = data.get('isBwbix', False)

    if not recordid_deal:
        return JsonResponse({'error': 'Missing dealid'}, status=400)

    if is_bwbix:
        subcategories = ['monte_ore_bwbix']
    else:
        subcategories = ['monte_ore', 'monte_ore_bwbix']

    placeholders = ','.join(['%s'] * len(subcategories))

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT recordid_, name, description, price, cost, note
            FROM user_product
            WHERE category LIKE 'ActiveMind' AND subcategory IN ({placeholders}) AND deleted_ = 'N'
            ORDER BY price ASC
        """.format(placeholders=placeholders), subcategories)
        products = cursor.fetchall()
        
        # Check for selected hour option in deal (if stored somewhere, e.g. in dealline like conditions)
        # For now, we assume it might be stored similar to conditions or just rely on frontend default/saving
        # If we want persistence, we'd need to check user_dealline. 
        # Making a guess that we might store it as 'subcategory = hours' product in dealline.
        cursor.execute("""
            SELECT recordidproduct_
            FROM user_dealline
            WHERE recordiddeal_ = %s
            AND deleted_ = 'N'
        """, [recordid_deal])
        selected_rows = cursor.fetchall()
        selected_ids = {row[0] for row in selected_rows}

    options_list = []
    for recordid_product, name, description, price, cost, note in products:
        clean_name = name.replace("AM - ", "").strip()
        
        hours_val = 0
        if note:
             match_hours = re.search(r'- \s*:\s*(\d+)', note)
             if match_hours:
                 hours_val = int(match_hours.group(1))

        options_list.append({
            "id": str(recordid_product), # Use recordid as ID
            "label": clean_name,
            "description": description or "",
            "price": float(price) if price else 0.0,
            "cost": float(cost) if cost else 0.0,
            "selected": recordid_product in selected_ids,
            "icon": "Clock",
            "hours": hours_val,
        })

    return JsonResponse({"options": options_list}, safe=False)


def get_assistance_bwbix_activemind(request):
    data = json.loads(request.body)
    recordid_deal = data.get('dealid')

    if not recordid_deal:
        return JsonResponse({'error': 'Missing dealid'}, status=400)

    subcategories = ['assistance_bwbix']
    placeholders = ','.join(['%s'] * len(subcategories))

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT recordid_, name, description, price, cost, note
            FROM user_product
            WHERE category LIKE 'ActiveMind' AND subcategory IN ({placeholders}) AND deleted_ = 'N'
            ORDER BY price ASC
        """.format(placeholders=placeholders), subcategories)
        products = cursor.fetchall()
        
        cursor.execute("""
            SELECT recordidproduct_, unitprice
            FROM user_dealline
            WHERE recordiddeal_ = %s
            AND deleted_ = 'N'
        """, [recordid_deal])
        selected_rows = cursor.fetchall()
        selected_dict = {str(row[0]): float(row[1]) for row in selected_rows if row[1] is not None}
        selected_ids = {row[0] for row in selected_rows}

    options_list = []
    for recordid_product, name, description, price, cost, note in products:
        clean_name = name.replace("AM - ", "").strip()
        
        hours_val = 0
        if note:
             match_hours = re.search(r'- \s*:\s*(\d+)', note)
             if match_hours:
                 hours_val = int(match_hours.group(1))

        opt_price = selected_dict.get(str(recordid_product), float(price) if price else 0.0)

        options_list.append({
            "id": str(recordid_product),
            "label": clean_name,
            "description": description or "",
            "price": opt_price,
            "cost": float(cost) if cost else 0.0,
            "selected": recordid_product in selected_ids,
            "icon": "Clock",
            "hours": hours_val,
        })

    has_selected = any(opt["selected"] for opt in options_list)
    if not has_selected and options_list:
        options_list[0]["selected"] = True

    return JsonResponse({"options": options_list}, safe=False)

def get_service_and_asset_activemind(request):
    data = json.loads(request.body)
    recordid_deal = data.get('dealid')
    recordid_company = data.get('companyid')

    if not recordid_deal and not recordid_company:
        return JsonResponse({'error': 'Missing dealid or companyid'}, status=400)

    with connection.cursor() as cursor:
        if recordid_company:
            cursor.execute("""
                SELECT recordid_, description, type, status, sector, note, provider, quantity, recordidproduct_
                FROM user_serviceandasset
                WHERE recordidcompany_ = %s AND status = 'Active' AND deleted_ = 'N'
                ORDER BY id ASC
            """, [recordid_company])
        else:
            cursor.execute("""
                SELECT sa.recordid_, sa.description, sa.type, sa.status, sa.sector, sa.note, sa.provider, sa.quantity, sa.recordidproduct_
                FROM user_serviceandasset as sa
                JOIN user_deal as d ON d.recordidcompany_ = sa.recordidcompany_
                WHERE d.recordid_ = %s AND sa.status = 'Active' AND sa.deleted_ = 'N'
                ORDER BY sa.id ASC
            """, [recordid_deal])
        servicesandassets = cursor.fetchall()

    options_list = []
    for recordid_service, description, type, status, sector, note, provider, quantity, recordidproduct_ in servicesandassets:
        clean_desc = description.strip()
        product_name = ""
        product_price = 0.0

        if recordidproduct_:
            product_record = UserRecord('product',recordidproduct_)
            product_name = product_record.values.get("name", '')
            product_price = product_record.values.get("price", 0.0)

        options_list.append({
            "id": str(recordid_service),
            "label": clean_desc,
            "note": note or "",
            "provider": provider or "",
            "quantity": quantity or 1,
            "sector": sector or "",
            "type": type or "",
            "status": status or "",
            "product_name": product_name or "",
            "product_price": float(product_price) if product_price else 0.0,
        })

    return JsonResponse({"options": options_list}, safe=False)


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

    # --- Active Services & Assets (Reusing logic) ---
    try:
        req_mock = type('Req', (object,), {"body": json.dumps({"companyid": recordid})})
        resp = get_service_and_asset_activemind(req_mock)
        if resp.status_code == 200:
            content = json.loads(resp.content)
            return_badgeItems["active_services"] = content.get("options", [])
        else:
            return_badgeItems["active_services"] = []
    except Exception as e:
        print(f"Error fetching active services for badge: {e}")
        return_badgeItems["active_services"] = []

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
    deal_expectedmargin = fields.get("expectedmargin", {})
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
    return_badgeItems["deal_expectedmargin"] = deal_expectedmargin.get("value", 0)
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





def sync_contacts(request):
    from customapp_swissbix.script import sync_contacts
    return sync_contacts(request)


def get_timetracking(request):
    print("get_timetracking")
    
    try:
        userid = Helper.get_userid(request)
        current_date = datetime.datetime.now().date()

        condition_list = []
        condition_list.append(f"user={userid}")

        timetrackings_list = UserTable('timetracking').get_records(conditions_list=condition_list)
        timetrackings = []
        task_totals_map = {}

        for timetracking in timetrackings_list:
            raw_date = timetracking['date']
            if not raw_date:
                continue

            if isinstance(raw_date, datetime.datetime):
                timetracking_date = raw_date.date()
            elif isinstance(raw_date, datetime.date):
                timetracking_date = raw_date
            elif isinstance(raw_date, str):
                try:
                    timetracking_date = datetime.datetime.strptime(raw_date, '%Y-%m-%d').date()
                except ValueError:
                    continue 
            else:
                continue

            if timetracking_date != current_date:
                continue

            clientid = timetracking.get('recordidcompany_', '')
            
            companyname = ""

            if clientid:
                company = UserRecord('company', clientid)
                if company:
                    companyname = company.values.get('companyname', '')

            task_id = timetracking.get('recordidtask_')
            task_key = str(task_id) if task_id else "no_task"
            task_totals_map[task_key] = calculate_task_total(
                task_id,
                userid,
                timetrackings_list,
                None,
            )

            task_name = ""
            expected_duration = 0.0

            if task_id:
                task_record = UserRecord('task', task_id)
                if task_record:
                    task_name = task_record.values.get('description', '')
                    raw_expected = task_record.values.get('duration')
                    expected_duration = float(raw_expected) if raw_expected is not None else 0.0
                    if not timetracking['worktime'] or timetracking['worktime'] == 0:
                        timetracking['worktime'] = task_record.values['tracked_time']

            timetracking_data = {
                'id': timetracking['recordid_'],
                'description': timetracking['description'],
                'date': timetracking['date'],
                'start': timetracking['start'],
                'end': timetracking['end'],
                'worktime': timetracking['worktime'],
                'worktime_string': timetracking['worktime_string'],
                'pausetime': timetracking['pausetime'],
                'pausetime_string': timetracking['pausetime_string'],
                'status': timetracking['stato'],
                'clientid': clientid,
                'client_name': companyname,
                'task_id': task_key,
                'task_name': task_name,
                'task_expected_duration': expected_duration,
                'service_name': timetracking['service']
            }
            timetrackings.append(timetracking_data)

        # Clienti
        companies_list = UserTable('company').get_records(limit=10000000)
        companies = []
        for company in companies_list:
            company_data = {
                'id': company['recordid_'],
                'companyname': company['companyname'],
            }
            companies.append(company_data)

        # Servizi
        services_data = SysLookupTableItem.objects.filter(lookuptableid='service_timetracking').order_by(F('itemorder').asc(nulls_last=True), 'itemcode').values('itemcode', 'itemdesc')
        services = []
        for s in services_data:
            services.append({
                'itemcode': s['itemcode'],
                'itemdesc': s['itemdesc']
            })

        return JsonResponse({"timetracking": timetrackings, "clients": companies,
                "task_totals": task_totals_map, "services": services}, safe=False)

    except Exception as e:
        logger.error(f"Errore nell'ottenimento dei timetracker per l'utente: {str(e)}")
        return JsonResponse({'error': f"Errore  nell'ottenimento dei timetracker per l'utente: {str(e)}"}, status=500)


def resume_timetracking(request):
    print("resume_timetracking")

    try:
        data = json.loads(request.body)
        recordid = data.get('timetracking')

        userid = Helper.get_userid(request)

        stop_active_timetracking(userid)

        if recordid:
            timetracking = UserRecord('timetracking', recordid)

            time_format = '%H:%M'

            last_end = datetime.datetime.strptime(
                timetracking.values['end'], time_format
            )

            now = datetime.datetime.now().strftime(time_format)

            pause_delta = datetime.datetime.strptime(now, time_format) - last_end

            total_minutes = pause_delta.total_seconds() / 60

            existing_pause_string = timetracking.values.get('pausetime_string', '00:00')
            if existing_pause_string:
                existing_hours, existing_minutes = map(int, existing_pause_string.split(':'))
                existing_pause_minutes = existing_hours * 60 + existing_minutes
            else:
                existing_pause_minutes = 0

            total_pause_minutes = existing_pause_minutes + total_minutes

            hours, minutes = divmod(total_pause_minutes, 60)
            formatted_time = "{:02}:{:02}".format(int(hours), int(minutes))
            timetracking.values['pausetime_string'] = str(formatted_time)

            pause_decimal = calculate_pausetime(formatted_time)
            timetracking.values['pausetime'] = pause_decimal

            timetracking.values['stato'] = "Attivo"

            timetracking.save()

        return JsonResponse({"status": "restarted"}, safe=False)

    except Exception as e:
        logger.error(f"Errore nel riavvio del timetracking: {str(e)}")
        return JsonResponse(
            {'error': f"Errore nel riavvio del timetracking: {str(e)}"},
            status=500
        )


def delete_timetracking(request):
    print("delete_timetracking")

    try:
        data = json.loads(request.body)
        recordid = data.get('timetracking')

        if recordid:
            timetracking = UserRecord('timetracking', recordid)
            timetracking.values['deleted_'] = 'Y'
            timetracking.save()

            taskid = timetracking.values['recordidtask_']
            if taskid:
                task = UserRecord('task', taskid)
                worktime = timetracking.values['worktime']
                if not worktime:
                    worktime = 0
                pausetime = timetracking.values['pausetime']
                if not pausetime:
                    pausetime = 0
                tracked_time = task.values['tracked_time']
                if tracked_time:
                    task.values['tracked_time'] = tracked_time - worktime - pausetime  
                    task.save()

        return JsonResponse({"status": "deleted"}, safe=False)
    except Exception as e:
        logger.error(f"Errore nella cancellazione del timetracking: {str(e)}")
        return JsonResponse(
            {'error': f"Errore nella cancellazione del timetracking: {str(e)}"},
            status=500
        )


def update_timetracking(request):
    print("update_timetracking")

    try:
        data = json.loads(request.body)
        recordid = data.get('timetracking_id')
        description = data.get('description')
        start = data.get('start')
        end = data.get('end')
        pausetime_string = data.get('pausetime_string')

        if recordid:
            timetracking = UserRecord('timetracking', recordid)
            timetracking.values['description'] = description
            timetracking.values['start'] = start
            timetracking.values['end'] = end
            timetracking.values['pausetime_string'] = pausetime_string
            pausetime = calculate_pausetime(pausetime_string)
            timetracking.values['pausetime'] = pausetime

            # ---- ricalcolo worktime ----
            if start and end:
                worktime, worktime_string = calculate_worktime(start, end)
                timetracking.values['worktime'] = worktime
                timetracking.values['worktime_string'] = worktime_string

            timetracking.save()

            if start and end:
                taskid = timetracking.values.get('recordidtask_')
                if taskid:
                    task = UserRecord('task', taskid)
                    condition_list = []
                    userid = Helper.get_userid(request)
                    condition_list.append(f"user={userid}")
                    condition_list.append(f"recordidtask_={taskid}")
                    task.values['tracked_time'] = calculate_task_total(
                        taskid,
                        userid,
                        None,
                        condition_list,
                    )
                    task.save()


        return JsonResponse({"status": "updated"}, safe=False)
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento del timetracking: {str(e)}")
        return JsonResponse(
            {'error': f"Errore nell'aggiornamento del timetracking: {str(e)}"},
            status=500
        )

def save_timetracking(request):
    print("save_timetracking")

    try:
        data = json.loads(request.body)

        userid = Helper.get_userid(request)

        stop_active_timetracking(userid)

        timetracking = UserRecord('timetracking')

        timetracking.values['user'] = userid
        timetracking.values['description'] = data.get('description')
        timetracking.values['date'] = datetime.datetime.now().strftime("%Y-%m-%d")
        timetracking.values['start'] = datetime.datetime.now().strftime("%H:%M")
        timetracking.values['stato'] = "Attivo"

        if data.get('clientid'):
            timetracking.values['recordidcompany_'] = data.get('clientid')    
            
        if data.get('service'):
            timetracking.values['service'] = data.get('service')

        timetracking.save()

        return JsonResponse({"status": "completed"}, safe=False)
    except Exception as e:
        logger.error(f"Errore nell'avviare il timetracking: {str(e)}")
        return JsonResponse({'error': f"Errore nell'avviare il timetracking: {str(e)}"}, status=500)


def stop_timetracking(request):
    print("stop_timetracking")

    try:
        data = json.loads(request.body)
        recordid = data.get('timetracking')
        userid = Helper.get_userid(request)

        if recordid:
            timetracking = UserRecord('timetracking', recordid)

            timetracking.values['end'] = datetime.datetime.now().strftime("%H:%M")
            timetracking.values['stato'] = "Terminato"

            worktime, worktime_string = calculate_worktime(
                timetracking.values['start'],
                timetracking.values['end']
            )
            timetracking.values['worktime'] = worktime
            timetracking.values['worktime_string'] = worktime_string
            timetracking.save()

            taskid = timetracking.values['recordidtask_']
            if taskid:
                task = UserRecord('task', taskid)
                task.values['tracked_time'] = calculate_task_total(
                    taskid,
                    userid,
                    None,
                    None,
                )
                task.save()

        return JsonResponse({"status": "completed"}, safe=False)
    except Exception as e:
        logger.error(f"Errore nel fermare il timetracking: {str(e)}")
        return JsonResponse({'error': f"Errore nel fermare il timetracking: {str(e)}"}, status=500)


def get_timesheet_initial_data(request):
    print("get_timesheet_initial_data")

    try:
        userid = Helper.get_userid(request)
        user = SysUser.objects.get(id=userid)
    
        data = json.loads(request.body)
        recordid = data.get('recordid')

        servizi = [
            {"id": "1", "name": "Amministrazione", "icon_slug": "amministrazione"},
            {"id": "2", "name": "Assistenza IT", "icon_slug": "it"},
            {"id": "3", "name": "Assistenza PBX", "icon_slug": "pbx"},
            {"id": "4", "name": "Assistenza SW", "icon_slug": "sw"},
            {"id": "5", "name": "Assistenza Web Hosting", "icon_slug": "web"},
            {"id": "6", "name": "Commerciale", "icon_slug": "commerciale"},
            {"id": "7", "name": "Formazione Apprendista", "icon_slug": "formazione"},
            {"id": "8", "name": "Formazione e Test", "icon_slug": "test"},
            {"id": "9", "name": "Interno", "icon_slug": "interno"},
            {"id": "10", "name": "Lenovo", "icon_slug": "lenovo"},
            {"id": "11", "name": "Printing", "icon_slug": "printing"},
            {"id": "12", "name": "Riunione", "icon_slug": "riunione"},
        ]

        opzioni = [
            # {"id": "o1", "name": "Commercial support"},
            # {"id": "o2", "name": "In contract"},
            # {"id": "o3", "name": "Monte ore"},
            # {"id": "o4", "name": "Out of contract"},
            {"id": "o5", "name": "Swisscom incident"},
            {"id": "o6", "name": "Swisscom ServiceNow"},
            {"id": "o7", "name": "To check"},
            {"id": "o8", "name": "Under Warranty"},
        ]


        # # Scelta aziende recenti a partire dai Timesheet
        # recent_ts = UserTable('timesheet').get_records(
        #     conditions_list=[f"user = '{userid}'"], 
        #     limit=50
        # )

        # recent_ids = []
        # for ts in recent_ts:
        #     cid = ts.get('recordidcompany_')
        #     if cid and cid not in recent_ids:
        #         recent_ids.append(cid)
        #     if len(recent_ids) >= 10: break

        # aziende_recenti = []
        # for cid in recent_ids:
        #     c_rec = UserTable('company').get_records(conditions_list=[f"recordid_ = '{cid}'"])
        #     if c_rec:
        #         aziende_recenti.append({
        #             'id': str(c_rec[0].get('recordid_')),
        #             'name': c_rec[0].get('companyname'),
        #             'details': c_rec[0].get('details')
        #         })

        # Scelta aziende recenti a partire dai progetti attivi
        conditions_list = []
        conditions_list.append(f"assignedto='{userid}'")
        conditions_list.append("status != 'Progetto fatturato'")

        active_projects = UserTable('project').get_records(conditions_list=conditions_list, orderby="lastupdate_ desc")

        aziende_recenti = []
        progetti_recenti = []

        seen_ids = set()
        
        for project in active_projects:
            cid = project.get('recordidcompany_')
            
            if len(aziende_recenti) <= 10:
                progetti_recenti.append({
                    'id': str(project.get('recordid_')),
                    'name': project.get('projectname'),
                })

            if cid and cid not in seen_ids:
                azienda = UserRecord('company', cid)
                
                if azienda and hasattr(azienda, 'values'):
                    aziende_recenti.append({
                        'id': str(cid),
                        'name': azienda.values.get('companyname', 'Azienda senza nome'),
                        'details': azienda.values.get('city', 'Località non definita')
                    })

                    seen_ids.add(cid) 
            
            if len(aziende_recenti) >= 10: 
                break

        timesheet_formatted = None
        
        if recordid:
            # TODO: controllo permessi


            conditions_list = [f"recordid_={recordid}"]
            raw_ts_list = UserTable("timesheet").get_records(conditions_list=conditions_list)
            
            if raw_ts_list:
                raw_ts = raw_ts_list[0]
                
                azienda_obj = None
                if raw_ts.get('recordidcompany_'):
                    c_rec = UserRecord('company', raw_ts.get('recordidcompany_'))
                    if c_rec and hasattr(c_rec, 'values'):
                        azienda_obj = {
                            'id': str(raw_ts.get('recordidcompany_')),
                            'name': c_rec.values.get('companyname'),
                            'details': c_rec.values.get('city', '')
                        }

                progetto_obj = None
                if raw_ts.get('recordidproject_'):
                    p_rec = UserRecord('project', raw_ts.get('recordidproject_'))
                    if p_rec and hasattr(p_rec, 'values'):
                        progetto_obj = {
                            'id': str(raw_ts.get('recordidproject_')),
                            'name': p_rec.values.get('projectname')
                        }

                ticket_obj = None
                if raw_ts.get('recordidticket_'):
                    t_rec = UserRecord('ticket', raw_ts.get('recordidticket_'))
                    if t_rec and hasattr(t_rec, 'values'):
                        ticket_obj = {
                            'id': str(raw_ts.get('recordidticket_')),
                            'name': t_rec.values.get('subject') or t_rec.values.get('ticket_no')
                        }

                servizio_obj = next((s for s in servizi if s['name'] == raw_ts.get('service')), None)
                opzione_obj = next((o for o in opzioni if o['name'] == raw_ts.get('invoiceoption')), None)

                conditions_list = [f"recordidtimesheet_={recordid}"]
                attachments_list = UserTable('attachment').get_records(conditions_list=conditions_list)

                attachments = []

                if attachments_list:
                    for attachment in attachments_list:
                        attachments.append({
                            "id": attachment.get("recordid_"),
                            "tipo": "Allegato generico",
                            "file": attachment.get("file"),  # sempre null dal backend
                            "filename": attachment.get("filename"),
                            "url": attachment.get("file"),  # usata solo per preview
                            "data": attachment.get("createdon_", ""),  # o campo corretto
                            "note": "",
                            "rapportiLavoro": None,
                            "progetto": None
                        })

                conditions_list = [f"recordidtimesheet_={recordid}"]
                timesheetlines_list = UserTable('timesheetline').get_records(conditions_list=conditions_list)

                materiali = []

                if timesheetlines_list:
                    for timesheetline in timesheetlines_list:
                        recordidproduct = timesheetline.get("recordidproduct_")
                        product = UserRecord('product', recordidproduct)

                        materiali.append({
                            "id": timesheetline.get("recordid_"),
                            "prodotto": {
                                "id": str(recordidproduct),
                                "name": product.values.get("name"),
                                "details": None,
                                "icon_slug": None
                            },
                            "note": str(timesheetline.get("note", "")),
                            "description": str(timesheetline.get("description", "")),
                            "qtaPrevista": str(timesheetline.get("plannedquantity", "")),
                            "qtaEffettiva": str(timesheetline.get("actualquantity", ""))
                        })
                

                def safe_time(val):
                    if not val: return '00:00'
                    return str(val)[:5]

                timesheet_formatted = {
                    'id': str(raw_ts.get('recordid_')),
                    'data': str(raw_ts.get('date'))[:10] if raw_ts.get('date') else None,
                    'descrizione': raw_ts.get('description', ''),
                    'tempoLavoro': safe_time(raw_ts.get('worktime')), 
                    'tempoTrasferta': safe_time(raw_ts.get('traveltime')),
                    'noteInterne': raw_ts.get('internalnotes', ''),
                    'notaRifiuto': raw_ts.get('decline_note', ''),
                    'printTravel': raw_ts.get('print_travel', ''),
                    'azienda': azienda_obj,
                    'progetto': progetto_obj,
                    'ticket': ticket_obj,
                    'servizio': servizio_obj,
                    'opzioni': opzione_obj,
                    'materiali': materiali, 
                    'allegati': attachments
                }

        response_data = {
            'servizi': servizi,
            'opzioni': opzioni,
            'aziendeRecenti': aziende_recenti,
            'progettiRecenti': progetti_recenti,
            'utenteCorrente': {
                'id': str(userid),
                'name': f"{user.firstname} {user.lastname}",
                'details': user.email
            },
            'timesheet': timesheet_formatted
        }

        return JsonResponse(response_data, safe=False)
    except Exception as e:
        logger.error(f"Errore nel fetch dei dati iniziali per la creazione di un nuovo timesheeet: {str(e)}")
        return JsonResponse({'error': f"Errore nel fetch dei dati iniziali per la creazione di un nuovo timesheeet: {str(e)}"}, status=500)


def save_timesheet(request):
    """
    Salvataggio Timesheet da BixApp mobile
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        userid = Helper.get_userid(request)
        
        # --- 1. RECUPERO DATI DAL FRONTEND ---
        fields_raw = request.POST.get('fields')
        data = json.loads(fields_raw) if fields_raw else {}

        recordid = data.get('recordid', '')

        # Inizializzo Record
        timesheet_record = None
        if recordid:
            timesheet_record = UserRecord('timesheet', recordid)
        else:
            timesheet_record = UserRecord('timesheet')
        
        # Mappatura campi base
        timesheet_record.values['recordidcompany_'] = data.get('azienda_id', '')
        timesheet_record.values['recordidproject_'] = data.get('progetto_id', '')
        timesheet_record.values['recordidticket_'] = data.get('ticket_id', '')
        timesheet_record.values['service'] = data.get('servizio', '')
        timesheet_record.values['invoiceoption'] = data.get('opzione', '')
        timesheet_record.values['description'] = data.get('descrizione', '')
        timesheet_record.values['internalnotes'] = data.get('note_interne', '')
        timesheet_record.values['decline_note'] = data.get('nota_rifiuto', '')
        timesheet_record.values['user'] = userid
        
        # Gestione Data
        fecha = data.get('data')
        if fecha:
            timesheet_record.values['date'] = datetime.datetime.strptime(fecha, '%Y-%m-%d')
        
        # Gestione Tempi
        worktime = data.get('tempo_lavoro', '00:00')
        traveltime = data.get('tempo_trasferta', '00:00')
        timesheet_record.values['worktime'] = worktime
        timesheet_record.values['traveltime'] = traveltime

        timesheet_record.save()
        new_timesheet_id = timesheet_record.recordid
        save_record_fields('timesheet', new_timesheet_id)

        return JsonResponse({'status': 'success', 'id': new_timesheet_id})

    except Exception as e:
        print(f"ERRORE save_timesheet (Base): {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def save_timesheet_material(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        timesheet_id = request.POST.get('timesheet_id')
        materiali_raw = request.POST.get('materiali')
        
        if not timesheet_id or not materiali_raw:
            return JsonResponse({'error': 'Missing data'}, status=400)

        materiali = json.loads(materiali_raw)
        saved_ids = []
        
        for mat in materiali:
            m_rec = UserRecord('timesheetline')
            m_rec.values['recordidtimesheet_'] = timesheet_id
            m_rec.values['recordidproduct_'] = mat.get('prodotto_id')
            m_rec.values['expectedquantity'] = mat.get('expectedquantity')
            m_rec.values['actualquantity'] = mat.get('actualquantity')
            m_rec.values['note'] = mat.get('note', '')
            m_rec.values['description'] = mat.get('description', '')
            m_rec.save()
            saved_ids.append(m_rec.recordid)

        return JsonResponse({'status': 'success', 'ids': saved_ids})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def remove_timesheet_material(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        timesheet_id = request.POST.get('timesheet_id')
        materiali_raw = request.POST.get('materiali')
        
        if not timesheet_id or not materiali_raw:
            return JsonResponse({'error': 'Missing data'}, status=400)

        materiali = json.loads(materiali_raw)
        
        for mat in materiali:
            line_id = mat.get('id')
            if line_id:
               rec = UserRecord('timesheetline', line_id)
               if rec and str(rec.values.get('recordidtimesheet_')) == str(timesheet_id):
                   rec.values['deleted_'] = 'Y'
                   rec.save()
            else:
                prod_id = mat.get('prodotto_id')
                if prod_id:
                    records = UserTable('timesheetline').get_records(
                        conditions_list=[
                            f"recordidtimesheet_ = '{timesheet_id}'",
                            f"recordidproduct_ = '{prod_id}'",
                            "deleted_ = 'N'"
                        ]
                    )
                    if records:
                        del_rec = UserRecord('timesheetline', records[0]['recordid_'])
                        del_rec.values['deleted_'] = 'Y'
                        del_rec.save()

        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def save_timesheet_attachment(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        timesheet_id = request.POST.get('timesheet_id')
        if not timesheet_id:
            return JsonResponse({'error': 'Timesheet ID missing'}, status=400)

        saved_ids = []

        for key in request.FILES.keys():
            if key.startswith('file_'):
                idx = key.split('_')[1]
                file_obj = request.FILES.get(key)
                meta_raw = request.POST.get(f'metadata_{idx}')
                
                if file_obj and meta_raw:
                    meta = json.loads(meta_raw)
                    att_rec = UserRecord('attachment')

                    tipo_ui = meta.get('tipo', 'Allegato generico')
                    att_rec.values['type'] = 'Signature' if tipo_ui == 'Signature' else 'Allegato generico'
                    att_rec.values['note'] = meta.get('note', '')
                    att_rec.values['date'] = meta.get('data') or datetime.date.today().strftime('%Y-%m-%d')
                    att_rec.values['recordidtimesheet_'] = timesheet_id
                    
                    fname = meta.get('filename') or file_obj.name
                    att_rec.values['filename'] = fname
                    
                    storage_path = f"timesheet/{timesheet_id}/{fname}"
                    final_path = default_storage.save(storage_path, file_obj)
                    
                    att_rec.values['file'] = final_path
                    att_rec.save()
                    saved_ids.append(att_rec.recordid)

        return JsonResponse({'status': 'success', 'ids': saved_ids})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def remove_timesheet_attachment(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        timesheet_id = request.POST.get('timesheet_id')
        attachment_id = request.POST.get('attachment_id')

        if not attachment_id:
             return JsonResponse({'error': 'Attachment ID missing'}, status=400)

        att_rec = UserRecord('attachment', attachment_id)
        
        if timesheet_id:
             if str(att_rec.values.get('recordidtimesheet_')) != str(timesheet_id):
                 return JsonResponse({'error': 'Mismatch timesheet/attachment'}, status=403)
        
        att_rec.values['deleted_'] = 'Y'
        att_rec.save()
        return JsonResponse({'status': 'success'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def search_timesheet_entities(request):
    """
    Endpoint dinamico via POST per cercare entità.
    """
    target = request.POST.get('target')
    query = request.POST.get('q', '').strip()
    azienda_id = request.POST.get('azienda_id')
    record_id = request.POST.get('id')
    
    table_map = {
        'azienda': ('company', 'companyname', 'details'),
        'progetto': ('project', 'projectname', None),
        'ticket': ('ticket', 'subject', 'description'),
        'prodotto': ('product', 'name', None),
        'rapportiLavoro': ('timesheet', 'description', None),
    }

    if target not in table_map:
        return JsonResponse({'results': []})

    table_name, name_field, detail_field = table_map[target]
    
    conditions = []
    if record_id:
        conditions.append(f"recordid_ = '{record_id}'")
    elif query:
        conditions.append(f"{name_field} LIKE '%{query}%'")

    if target == 'progetto' and azienda_id:
        conditions.append(f"recordidcompany_ = '{azienda_id}'")
        conditions.append(f"(completed != 'Si' OR completed IS NULL)")

    try:
        records = UserTable(table_name).get_records(conditions_list=conditions, limit=20)
        
        results = [
            {
                'id': str(x.get('recordid_')),
                'name': x.get(name_field) or "N/D",
                'details': x.get(detail_field) if detail_field else "",
                'address': x.get('address') or "",
                'city': x.get('city') or "",
                'email': x.get('email') or "",
                'phonenumber': x.get('phonenumber') or "",
            } for x in records
        ]
        
        return JsonResponse({'results': results}, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e), 'results': []}, status=500)


def upload_markdown_image(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito'}, status=405)

    try:
        file_obj = request.FILES.get('file')
        
        if not file_obj:
            return JsonResponse({'error': 'Nessun file ricevuto'}, status=400)
        
        fname = file_obj.name
        storage_path = f"markdown_uploads/{fname}"

        final_path = default_storage.save(storage_path, file_obj)
        
        full_url = f"/api/media-proxy?url={final_path}"
        
        att_rec = UserRecord('attachment')
        att_rec.values['type'] = 'Markdown Image'
        att_rec.values['file'] = final_path
        att_rec.save()

        return JsonResponse({
            'status': 'success',
            'url': full_url 
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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
    print("get_bixhub_initial_data")

    try: 
        userid = Helper.get_userid(request)
        username = "Utente"
        if userid:
            user_rec = SysUser.objects.get(id=userid)
            if user_rec:
                firstname = user_rec.firstname
                lastname = user_rec.lastname
                username = f"{firstname} {lastname}"

        customs_fn = SysCustomFunction.objects.all().order_by('order').values() 

        bix_apps = []
        
        timesheet_fn_obj = None 
        lenovo_fn_obj = None

        for fn in customs_fn:
            raw_params = fn.get('params')
            params_dict = {}
            
            try:
                if raw_params and isinstance(raw_params, str):
                    params_dict = json.loads(raw_params)
            except json.JSONDecodeError:
                pass
            
            app_data = {
                **fn, 
                "name": fn['title'],
                "function": fn.get('function') or fn.get('action'),
                "url": params_dict.get('url', '#'),
                "icon": params_dict.get('icon', 'squares'), 
                "logo": params_dict.get('logo', None),
                "description": params_dict.get('description', ''),
                "params": params_dict
            }

            if fn.get('tableid_id') and fn['tableid_id'].lower() == "ticket_lenovo" and params_dict.get('linkable') is True:
                lenovo_fn_obj = app_data

            if fn.get('tableid_id') and fn['tableid_id'].lower() == "timesheet" and params_dict.get('linkable') is True:
                timesheet_fn_obj = app_data

            if params_dict.get('linkable') is True:
                bix_apps.append(app_data)

        recent_timesheets = []
        if userid:
            condition_list = []
            condition_list.append(f"user='{userid}'")
            condition_list.append("(description IS NULL OR description = '' OR worktime IS NULL OR worktime = '')")
            
            ts_records = UserTable('timesheet').get_records(
                conditions_list=condition_list, 
                limit=10, 
                orderby="date desc"
            )

            for ts in ts_records:
                company_name = "N/D"
                cid = ts.get('recordidcompany_')
                if cid:
                    c_rec = UserRecord('company', cid)
                    if c_rec and hasattr(c_rec, 'values'):
                        company_name = c_rec.values.get('companyname', 'N/D')

                recent_timesheets.append({
                    "id": str(ts.get('recordid_')),
                    "date": str(ts.get('date'))[:10] if ts.get('date') else "",
                    "company": company_name,
                })

        closed_timesheets = []
        if userid:
            # Condizioni per timesheet CHIUSI: description e worktime compilati
            condition_list_closed = []
            condition_list_closed.append(f"user='{userid}'")
            condition_list_closed.append("(description IS NOT NULL AND description != '' AND worktime IS NOT NULL AND worktime != '')")
            
            ts_closed_records = UserTable('timesheet').get_records(
                conditions_list=condition_list_closed, 
                limit=5, 
                orderby="date desc"
            )

            for ts in ts_closed_records:
                company_name = "N/D"
                cid = ts.get('recordidcompany_')
                if cid:
                    c_rec = UserRecord('company', cid)
                    if c_rec and hasattr(c_rec, 'values'):
                        company_name = c_rec.values.get('companyname', 'N/D')

                is_signed = False
                condition_list_signed = []
                condition_list_signed.append(f"recordidtimesheet_='{ts.get('recordid_')}'")
                condition_list_signed.append("type = 'Signature'")
                
                ts_signed_records = UserTable('attachment').get_records(
                    conditions_list=condition_list_signed, 
                    limit=1,
                )

                if ts_signed_records:
                    is_signed = True

                closed_timesheets.append({
                    "id": str(ts.get('recordid_')),
                    "date": str(ts.get('date'))[:10] if ts.get('date') else "",
                    "company": company_name,
                    "is_signed": is_signed
                })

        lenovo_tickets = []
        if userid:
            condition_list_lenovo = []
            condition_list_lenovo.append(f"technician='{userid}'")
            condition_list_lenovo.append("status != 'Riconsegnato'")
            condition_list_lenovo.append("deleted_ = 'N'")

            lenovo_records = UserTable('ticket_lenovo').get_records(
                conditions_list=condition_list_lenovo,
                limit=10,
                orderby="reception_date desc"
            )

            for tk in lenovo_records:
                lenovo_tickets.append({
                    "id": str(tk.get('recordid_')),
                    "name": tk.get('name') or "",
                    "surname": tk.get('surname') or "",
                    "company": tk.get('company_name') or "",
                    "status": tk.get('status') or "Bozza",
                    "date": str(tk.get('reception_date'))[:10] if tk.get('reception_date') else "",
                    "problem_description": tk.get('problem_description') or "",
                    "serial": tk.get('serial') or "",
                })

        data = {
            "bixApps": bix_apps,
            "timesheets": recent_timesheets,
            "closedTimesheets": closed_timesheets,
            "lenovoTickets": lenovo_tickets,
            "user": {
                "name": username
            },
            "timesheet_fn": timesheet_fn_obj,
            "lenovo_fn": lenovo_fn_obj
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({"error": f"Errore nel prendere i dati iniziali: {str(e)}"}, status=500)


def get_widget_employee(request):
    try:
        data = json.loads(request.body)
        userid = data.get('userid')
        
        user = SysUser.objects.filter(id=userid).first()
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)
            
        today = datetime.date.today()
        start_month = today.replace(day=1)
        today_str = today.strftime("%Y-%m-%d")
        start_month_str = start_month.strftime("%Y-%m-%d")

        # 1. Timesheets di oggi
        ts_today_cond = [f"user='{userid}'", f"date='{today_str}'", "deleted_='N'"]
        ts_today = UserTable("timesheet").get_records(conditions_list=ts_today_cond)
        count_today = len(ts_today)

        today_hours = 0.0
        for ts in ts_today:
            try:
                val = float(ts.get('worktime_decimal') or 0) + float(ts.get('traveltime_decimal') or 0)
                today_hours += val
            except:
                pass

        # 2. Ore del mese
        ts_month_cond = [f"user='{userid}'", f"date>='{start_month_str}'", "deleted_='N'"]
        ts_month = UserTable("timesheet").get_records(conditions_list=ts_month_cond)
        
        month_hours = 0.0
        for ts in ts_month:
            try:
                val = float(ts.get('worktime_decimal') or 0) + float(ts.get('traveltime_decimal') or 0)
                month_hours += val
            except:
                pass
                
        # 3. Attività corrente (Timetracking o Ultimo Timesheet)
        activity_data = {
            "recordid": "",
            "status": "Stopped",
            "description": "Nessuna attività recente",
            "start_time": "",
            "project_name": "",
            "client_name": ""
        }

        # Cerca timetracking attivo
        tt_cond = [
            f"user='{userid}'",
            "stato != 'Terminato'",
            "deleted_='N'"
        ]
        active_tt_list = UserTable("timetracking").get_records(conditions_list=tt_cond)
        
        if active_tt_list:
            active_tt = active_tt_list[0]
            activity_data["recordid"] = active_tt.get("recordid_")
            activity_data["status"] = "Running"
            activity_data["description"] = active_tt.get("description") or "Senza descrizione"
            activity_data["start_time"] = active_tt.get("start")
            
            if active_tt.get('recordidcompany_'):
                c_rec = UserRecord('company', active_tt.get('recordidcompany_'))
                if c_rec.values:
                    activity_data["client_name"] = c_rec.values.get('companyname', '')
                
            if active_tt.get('recordidproject_'):
                p_rec = UserRecord('project', active_tt.get('recordidproject_'))
                if p_rec.values:
                    activity_data["project_name"] = p_rec.values.get('projectname', '')

        else:
            # Se non c'è timetracking attivo, prendiamo l'ultimo timesheet
            last_ts_cond = [f"user='{userid}'", "deleted_='N'"]
            last_ts_list = UserTable("timesheet").get_records(
                conditions_list=last_ts_cond, 
                limit=1, 
                orderby="date desc" 
            )
            
            if last_ts_list:
                last_ts = last_ts_list[0]
                activity_data["recordid"] = last_ts.get("recordid_")
                activity_data["status"] = "Stopped"
                activity_data["description"] = last_ts.get("description") or "Senza descrizione"
                activity_data["start_time"] = last_ts.get("date").strftime("%d/%m/%Y")
                
                if last_ts.get('recordidcompany_'):
                    c_rec = UserRecord('company', last_ts.get('recordidcompany_'))
                    if c_rec.values:
                        activity_data["client_name"] = c_rec.values.get('companyname', '')
                    
                if last_ts.get('recordidproject_'):
                    p_rec = UserRecord('project', last_ts.get('recordidproject_'))
                    if p_rec.values:
                        activity_data["project_name"] = p_rec.values.get('projectname', '')

        return JsonResponse({
            "user": {
                "id": user.id,
                "firstname": user.firstname,
                "lastname": user.lastname,
                "email": user.email
            },
            "stats": {
                "today_count": today_hours,
                "month_hours": month_hours
            },
            "activity": activity_data
        })
    except Exception as e:
        return JsonResponse({"error": f"Errore nel prendere i dati iniziali: {str(e)}"}, status=500)

@csrf_exempt
def get_lenovo_intake_context(request):
    """
    Returns initial context for the Lenovo Intake App, including dynamic field settings.
    """
    try:
        # Fetch field settings dynamically
        rec = UserRecord('ticket_lenovo')
        # We use a default view or just get fields. 
        # get_record_card_fields returns a list of field definitions with settings
        card_fields = rec.get_record_card_fields()
        
        field_settings = {}
        for f in card_fields:
            if 'settings' in f:
                field_id = f.get('fieldid', '')
                # Handle potential suffix like '_' if typical in this system, 
                # but UserRecord usually handles it.
                settings = f.get('settings', {})
                field_settings[field_id] = {
                    'required': settings.get('obbligatorio') == 'true',
                    'hidden': settings.get('nascosto') == 'true',
                    'label': f.get('label', ''),
                    'read_only': settings.get('sola_lettura') == 'true' # Hypothetical, check if exists
                }

            if 'lookupitems' in f and f['fieldtypewebid'] == 'multiselect':
                accessories_lookup = f['lookupitems']

            if 'lookupitems' in f and f['fieldid'] == 'pick_up':
                pick_up_lookup = f['lookupitems']

        users_qs = SysUser.objects.filter(disabled='N').values('id', 'firstname', 'lastname')
        users_lookup = [{'userid': str(u['id']), 'firstname': u['firstname'], 'lastname': u['lastname']} for u in users_qs]
        logged_in_userid = Helper.get_userid(request) if request.user.is_authenticated else None

        return JsonResponse({
            'success': True,
            'field_settings': field_settings,
            'lookups': {
                'accessories': accessories_lookup if 'accessories_lookup' in locals() else [],
                'pick_up': pick_up_lookup if 'pick_up_lookup' in locals() else [],
                'users': users_lookup
            },
            'logged_in_userid': str(logged_in_userid) if logged_in_userid else ""
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

import requests

@csrf_exempt
def get_lenovo_device_info(request):
    """
    Proxy to Lenovo's pcsupport API to fetch device data bypassing frontend CORS.
    """
    try:
        # data = json.loads(request.body)
        product_id = request.POST.get('product_id')
        if not product_id:
            return JsonResponse({'success': False, 'error': 'product_id needed'}, status=400)

        s = requests.Session()
        # Request home first to get possible required cookies (though it works for some just with POST, safer to do this)
        s.get("https://pcsupport.lenovo.com/ch/it", timeout=5)

        res = s.post(
            "https://pcsupport.lenovo.com/ch/it/api/v4/upsell/redport/getIbaseInfo",
            json={
                "serialNumber": product_id,
                "country": "ch",
                "language": "it"
            },
            headers={
                "Content-Type": "application/json",
                "x-requested-with": "XMLHttpRequest"
            },
            timeout=10
        )
        if res.status_code == 200:
            return JsonResponse({'success': True, 'data': res.json()})
        else:
            return JsonResponse({'success': False, 'error': 'Lenovo API failed'}, status=502)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

from django.core.cache import cache

@csrf_exempt
def lenovo_mobile_handoff(request):
    """
    API for Mobile to PC real-time handoff without WebSockets.
    Uses Django's cache to pass the serial number from mobile to polling PC.
    """
    try:
        data = json.loads(request.body)
    except:
        data = request.POST

    action = data.get('action')
    session_id = data.get('session_id')
    
    if not session_id:
        return JsonResponse({'success': False, 'error': 'session_id missing'}, status=400)
        
    cache_key = f"lenovo_mobile_session_{session_id}"
    
    if action == 'set':
        serial = data.get('serial')
        if not serial:
            return JsonResponse({'success': False, 'error': 'serial missing'}, status=400)
        cache.set(cache_key, serial, 300) # 5 minutes expiry
        return JsonResponse({'success': True})
        
    elif action == 'check':
        serial = cache.get(cache_key)
        if serial:
            cache.delete(cache_key) # clear immediately once read
            return JsonResponse({'success': True, 'found': True, 'serial': serial})
        return JsonResponse({'success': True, 'found': False})
        
    return JsonResponse({'success': False, 'error': 'invalid action'}, status=400)

@csrf_exempt
def search_lenovo_ticket_by_serial(request):
    try:
        serial = request.POST.get('serial')
        if not serial:
            return JsonResponse({'success': False, 'error': 'Missing serial'}, status=400)
            
        open_tickets = UserTable('ticket_lenovo').get_records(
            conditions_list=["serial = '%s'" % serial, "status != 'Riconsegnato'", "deleted_ = 'N'"]
        )
        if open_tickets:
            ticket_id = open_tickets[0]['recordid_']
            rec = UserRecord('ticket_lenovo', ticket_id)
            return JsonResponse({'success': True, 'found': True, 'recordid': rec.recordid, 'status': rec.values.get('status')})
        else:
            return JsonResponse({'success': True, 'found': False})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
def get_lenovo_ticket(request):
    """
    Fetch a specific ticket by ID.
    """
    try:
        data = json.loads(request.body)
        ticket_id = data.get('ticket_id')
        
        if not ticket_id or str(ticket_id).lower() in ('null', 'none', 'undefined', ''):
            return JsonResponse({'success': False, 'error': 'Ticket ID missing or invalid'}, status=400)
            
        rec = UserRecord('ticket_lenovo', ticket_id)
        if not rec.recordid:
             return JsonResponse({'success': False, 'error': 'Ticket not found'}, status=404)
        
        # Serialize fields securely
        ticket_data = {
            'recordid': rec.recordid,
            'name': rec.values.get('name'),
            'surname': rec.values.get('surname'),
            'recordidcompany_': rec.values.get('recordidcompany_'),
            'company_name': rec.fields.get('recordidcompany_')['convertedvalue'] if rec.fields.get('recordidcompany_')['convertedvalue'] else rec.values.get('company_name'),
            'email': rec.values.get('email'),
            'phone': rec.values.get('phone'),
            'serial': rec.values.get('serial'),
            'product_photo': rec.values.get('product_photo'),
            'problem_description': rec.values.get('problem_description'),
            'status': rec.values.get('status'),
            'reception_date': str(rec.values.get('reception_date', ''))[:10] if rec.values.get('reception_date') else '',
            'address': rec.values.get('address'),
            'place': rec.values.get('place'),
            'brand': rec.values.get('brand'),
            'model': rec.values.get('model'),
            'username': rec.values.get('username'),
            'password': rec.values.get('password'),
            'warranty': rec.values.get('warranty'),
            'warranty_type': rec.values.get('warranty_type'),
            'auth_factory_reset': rec.values.get('auth_factory_reset'),
            'request_quote': rec.values.get('request_quote'),
            'direct_repair': rec.values.get('direct_repair'),
            'direct_repair_limit': rec.values.get('direct_repair_limit'),
            'auth_formatting': rec.values.get('auth_formatting'),
            'accessories': rec.values.get('accessories'),
            'technician': rec.values.get('technician'),
            'pick_up': rec.values.get('pick_up'),
            'internal_notes': rec.values.get('internal_notes'),
            'replaced_components': rec.values.get('replaced_components'),
        }
        
        # Check for signature file (Fixed Path)
        sig_path = f"ticket_lenovo/{ticket_id}/signature.png"
        if default_storage.exists(sig_path):
            ticket_data['signatureUrl'] = sig_path
        else:
            ticket_data['signatureUrl'] = ""
            
        # Fetch Warranty History
        warranties = HelpderDB.sql_query("SELECT * FROM user_warranty WHERE recordidticket_lenovo_ = %s ORDER BY start_date DESC", [ticket_id])
        
        warranty_history = []
        for w in warranties:
            warranty_history.append({
                'name': w.get('name', ''),
                'type': w.get('type', ''),
                'level': w.get('level', ''),
                'deliveryTypeName': w.get('delivery', ''),
                'startDate': str(w.get('start_date', ''))[:10] if w.get('start_date') else '',
                'endDate': str(w.get('end_date', ''))[:10] if w.get('end_date') else '',
                'description': w.get('description', ''),
                'remainingDays': w.get('remaining_days', 0),
            })
        ticket_data['warrantyHistory'] = warranty_history
        
        return JsonResponse({'success': True, 'ticket': ticket_data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
def save_lenovo_ticket(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
    try:
        recordid = request.POST.get('recordid', None)
        fields_raw = request.POST.get('fields', '{}')
        
        # Trasforma la stringa JSON in un dizionario Python
        fields = json.loads(fields_raw)
            
        # Mappatura dei campi
        allowed_fields = [
            'name', 'surname', 'company_name', 'email', 'phone', 'serial', 'product_photo', 
            'problem_description', 'status', 'recordidcompany_',
            'address', 'place', 'brand', 'model', 'username', 'password',
            'warranty', 'warranty_type',
            'auth_factory_reset', 'request_quote', 'direct_repair', 'direct_repair_limit', 'auth_formatting', 'accessories',
            'technician', 'pick_up', 'internal_notes', 'replaced_components'
        ]

        rec = UserRecord('ticket_lenovo', recordid)

        old_status = rec.values.get('status')

        # if old_status != 'Draft':
        #     del fields['status']

        lookup_item = SysLookupTableItem.objects.filter(lookuptableid='status_ticket_lenovo').order_by(F('itemorder').asc(nulls_last=True), 'itemcode').first()
        if not recordid:
            rec.values['reception_date'] = datetime.date.today().strftime('%Y-%m-%d')
            if 'status' not in fields:
                rec.values['status'] = lookup_item.itemcode

        for key in allowed_fields:
            if key in fields:
                rec.values[key] = fields[key]
                
        new_status = rec.values.get('status')

        rec.save()
        
        warranty_history_raw = request.POST.get('warrantyHistory', '[]')
        try:
            warranty_history = json.loads(warranty_history_raw)
        except json.JSONDecodeError:
            warranty_history = []
            
        if warranty_history:
            from commonapp.bixmodels.helper_db import HelpderDB
            HelpderDB.sql_execute_safe("DELETE FROM user_warranty WHERE recordidticket_lenovo_ = %s", [rec.recordid])
            for w in warranty_history:
                w_rec = UserRecord('warranty')
                w_rec.values['recordidticket_lenovo_'] = rec.recordid
                w_rec.values['name'] = w.get('name', '')
                w_rec.values['type'] = w.get('type', '')
                w_rec.values['level'] = w.get('level', '')
                w_rec.values['delivery'] = w.get('deliveryTypeName', '')
                w_rec.values['start_date'] = w.get('startDate', '')
                w_rec.values['end_date'] = w.get('endDate', '')
                w_rec.values['description'] = w.get('description', '')
                w_rec.values['remaining_days'] = w.get('remainingDays', 0)
                w_rec.save()

        if str(new_status).lower() == str(lookup_item.itemcode).lower() and str(old_status).lower() != str(lookup_item.itemcode).lower():
            from customapp_swissbix.services.custom_save.lenovo_ticket_services import LenovoTicketService
            LenovoTicketService.send_status_update_email(rec.recordid)

        # _send_email_lenovo(rec.recordid)      
        return JsonResponse({'success': True, 'recordid': rec.recordid})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON format in fields'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
def upload_lenovo_photo(request):
    """
    Uploads a photo for the Lenovo Ticket.
    """
    from django.core.files.storage import default_storage
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
    try:
        ticket_id = request.POST.get('ticket_id')
        file_obj = request.FILES.get('file')
        
        if not ticket_id or not file_obj:
            return JsonResponse({'success': False, 'error': 'Missing ticket_id or file'}, status=400)
            
        # 1. Save file
        fname, ext = os.path.splitext(file_obj.name)
        storage_path = f"ticket_lenovo/{ticket_id}/product_photo{ext}"
        final_path = default_storage.save(storage_path, file_obj)
        
        # 2. Update Ticket 'product_photo'
        rec = UserRecord('ticket_lenovo', ticket_id)
        rec.values['product_photo'] = final_path
        rec.save()

        return JsonResponse({'success': True, 'path': final_path})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def upload_lenovo_attachment(request):
    """
    Uploads a GENERIC attachment (photo/doc) to user_attachment.
    path: attachment/{ticket_id}/{filename}
    """
    try:
        ticket_id = request.POST.get('ticket_id')
        file_obj = request.FILES.get('file')
        note = request.POST.get('note', '')
        attachment_type = request.POST.get('attachment_type', 'pre-intervento')
        
        if not ticket_id or not file_obj:
            return JsonResponse({'success': False, 'error': 'Missing ticket_id or file'}, status=400)
            
        # 1. Save file to attachment/{ticket_id}/{filename}
        import re
        clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', file_obj.name)
        storage_path = f"attachment/{ticket_id}/{clean_name}"
        final_path = default_storage.save(storage_path, file_obj)
        
        # 2. Create user_attachment record
        att = UserRecord('attachment')
        att.values['recordidticket_lenovo_'] = ticket_id
        att.values['type'] = attachment_type
        att.values['file'] = final_path
        att.values['filename'] = clean_name
        att.values['note'] = note
        att.values['date'] = datetime.date.today().strftime('%Y-%m-%d')
        att.save()

        return JsonResponse({
            'success': True, 
            'mod': {
                'id': att.recordid,
                'url': final_path,
                'filename': clean_name,
                'note': note,
                'type': attachment_type,
                'date': att.values['date']
            }
        })

    except Exception as e:
        logger.error(f"Error uploading attachment: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def get_lenovo_attachments(request):
    try:
        data = json.loads(request.body)
        ticket_id = data.get('ticket_id')
        
        if not ticket_id:
             return JsonResponse({'success': False, 'error': 'Missing ticket_id'})

        query = """
            SELECT recordid_, filename, file, note, date, type 
            FROM user_attachment 
            WHERE recordidticket_lenovo_ = %s 
            AND deleted_ = 'N'
            ORDER BY date DESC, recordid_ DESC
        """
        
        attachments = []
        with connection.cursor() as cursor:
            cursor.execute(query, [ticket_id])
            rows = cursor.fetchall()
            for row in rows:
                attachments.append({
                    'id': row[0],
                    'filename': row[1],
                    'url': row[2],
                    'note': row[3],
                    'date': row[4].strftime('%Y-%m-%d') if row[4] else '',
                    'type': row[5]
                })
                
        return JsonResponse({'success': True, 'attachments': attachments})

    except Exception as e:
        logger.error(f"Error getting attachments: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def image_to_base64(path):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as image_file:
            return "data:image/png;base64," + base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Error converting image to base64: {e}")
        return None

def generate_lenovo_pdf(recordid, signature_path=None):
    try:
        base_path = os.path.normpath(os.path.join(settings.STATIC_ROOT, 'pdf'))
        os.makedirs(base_path, exist_ok=True)
        
        # Get Ticket Data
        rec = UserRecord('ticket_lenovo', recordid)
        if not rec.recordid:
            raise Exception("Ticket not found")

        rec.values['return_date'] = datetime.date.today().strftime('%Y-%m-%d')
        rec.save()

        rec = UserRecord('ticket_lenovo', recordid)

        row = rec.values
        row['recordid'] = recordid
        
        # Attachments
        query = """
            SELECT filename, file, note 
            FROM user_attachment 
            WHERE recordidticket_lenovo_ = %s 
            AND deleted_ = 'N'
            ORDER BY date DESC, recordid_ DESC
        """
        
        attachments = []
        with connection.cursor() as cursor:
            cursor.execute(query, [recordid])
            rows = cursor.fetchall()
            for row_att in rows:
                file_rel_path = row_att[1]
                note = row_att[2]
                
                # Check extension (images only)
                ext = os.path.splitext(file_rel_path)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif']:
                     abs_att_path = os.path.join(settings.UPLOADS_ROOT, file_rel_path)
                     b64 = image_to_base64(abs_att_path)
                     if b64:
                         attachments.append({
                             'image': b64,
                             'note': note
                         })
                         
        row['attachments'] = attachments

        # Asset Paths (Logo, etc)
        # Use the frontend logo which is known to be colored/visible
        logo_path = "c:/bixdata/bixui/bixportal/public/bixdata/logos/lenovo.png"
            
        row['logoUrl'] = image_to_base64(logo_path) or ""

        certificate_path = os.path.join(settings.BASE_DIR, 'customapp_swissbix', 'static', 'images', 'lenovo_certificated.png')
        row['certificateUrl'] = image_to_base64(certificate_path) or ""

        # Signature
        if signature_path:
             row['signatureUrl'] = image_to_base64(signature_path)
        else:
             # Check for fixed signature file
             sig_rel_path = f"ticket_lenovo/{recordid}/signature.png"
             if default_storage.exists(sig_rel_path):
                 abs_sig_path = os.path.join(settings.UPLOADS_ROOT, sig_rel_path)
                 row['signatureUrl'] = image_to_base64(abs_sig_path)

        # Product Photo & Conditions
        if row.get('product_photo'):
            # Path is relative 'ticket_lenovo/...'
            # Need absolute path
            abs_photo_path = os.path.join(settings.UPLOADS_ROOT, row['product_photo'])
            row['product_photo_b64'] = image_to_base64(abs_photo_path)
        
        # Render HTML
        html_content = render_to_string('pdf/lenovo_ticket.html', row)
        pdf_filename = f"lenovo_ticket_{recordid}.pdf"
        temp_pdf_path = os.path.join(base_path, pdf_filename)
        
        css = """
            html, body { margin: 0; padding: 0; }
            body { zoom: 0.8; }
        """

        BrowserManager.generate_pdf(
            html_content=html_content,
            output_path=temp_pdf_path,
            css_styles=css
        )
        
        # Save as attachment
        att = UserRecord('attachment')
        att.values['recordidticket_lenovo_'] = recordid
        att.values['type'] = 'Ricevuta Firmata' # Or just Signature/PDF
        att.values['date'] = datetime.date.today().strftime('%Y-%m-%d')
        att.save()

        # Move file
        dest_dir = os.path.join(settings.UPLOADS_ROOT, "attachment", str(att.recordid))
        os.makedirs(dest_dir, exist_ok=True)
        final_pdf_path = os.path.join(dest_dir, pdf_filename)
        shutil.move(temp_pdf_path, final_pdf_path)

        att.values['file'] = f"attachment/{att.recordid}/{pdf_filename}"
        att.values['filename'] = pdf_filename
        att.save()
        
        return att.recordid

    except Exception as e:
        print(f"Error generating PDF: {e}")
        raise

@csrf_exempt
def save_lenovo_signature(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        recordid = request.POST.get('recordid')
        img_base64 = request.POST.get('img_base64')

        if not recordid or not img_base64:
             return JsonResponse({'success': False, 'error': 'Missing data'}, status=400)

        # Save Signature Image
        if ',' in img_base64:
            _, img_base64 = img_base64.split(',', 1)
        img_data = base64.b64decode(img_base64)
        
        # Fixed filename for signature (one per ticket)
        filename = "signature.png"
        storage_path = f"ticket_lenovo/{recordid}/{filename}"
        
        # Overwrite if exists
        if default_storage.exists(storage_path):
            default_storage.delete(storage_path)
            
        final_path = default_storage.save(storage_path, ContentFile(img_data))
        
        # Generate PDF (will use the saved signature file)
        att_id = generate_lenovo_pdf(recordid)

        rec = UserRecord('ticket_lenovo', recordid)
        rec.values['status'] = 'Ritirato'
        rec.save()
        
        return JsonResponse({'success': True, 'attachment_id': att_id})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def print_lenovo_ticket(request):
    try:
        data = json.loads(request.body)
        recordid = data.get('recordid')
        
        # Find latest PDF attachment
        query = """
            SELECT file, filename 
            FROM user_attachment 
            WHERE recordidticket_lenovo_ = %s 
            AND type = 'Ricevuta Firmata'
            AND deleted_ = 'N'
            ORDER BY recordid_ DESC LIMIT 1
        """
        row = HelpderDB.sql_query_row(query, [recordid])
        
        if row:
             relative_path = row['file']
             filename = row['filename']
        else:
             # Generate on fly? calling generate_lenovo_pdf without signature?
             # User said "Sign & Print", so likely they sign first.
             # If just printing, maybe generate draft?
             # Let's try to generate one without signature if missing
             try:
                att_id = generate_lenovo_pdf(recordid)
                rec = UserRecord('attachment', att_id)
                relative_path = rec.values['file']
                filename = rec.values['filename']
             except Exception as e:
                 return JsonResponse({'success': False, 'error': str(e)}, status=500)

        abs_path = os.path.join(settings.UPLOADS_ROOT, relative_path)
        if not os.path.exists(abs_path):
             return JsonResponse({'success': False, 'error': 'File not found'}, status=404)
             
        with open(abs_path, 'rb') as pdf_file:
            b64 = base64.b64encode(pdf_file.read()).decode('utf-8')
            return JsonResponse({'success': True, 'pdf_base64': f"data:application/pdf;base64,{b64}"})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def calculate_task_total(
    task_id,
    userid,
    timetrackings_list=None,
    condition_list=None,
):
    """
    Ritorna il totale netto (worktime - pausetime) di un task.
    """
    total = 0.0
    task_key = str(task_id) if task_id else "no_task"

    if not condition_list:
        condition_list = []
        condition_list.append(f"user={userid}")
    if not timetrackings_list:
        timetrackings_list = UserTable('timetracking').get_records(conditions_list=condition_list)

    for timetracking in timetrackings_list:
        # ---- task match ----
        tt_task_id = timetracking.get('recordidtask_')
        tt_task_key = str(tt_task_id) if tt_task_id else "no_task"
        if tt_task_key != task_key:
            continue

        # ---- solo record terminati ----
        if timetracking.get('stato') != "Terminato":
            continue

        worktime = float(timetracking.get('worktime') or 0)
        pausetime = float(timetracking.get('pausetime') or 0)

        net_time = max(worktime - pausetime, 0)
        total += net_time

    return total


def stop_active_timetracking(userid):
    print("stop_active_timetracking")
    try:
        condition_list = []
        condition_list.append(f"user={userid}")
        condition_list.append("stato='Attivo'")

        active_timetrackings = UserTable('timetracking').get_records(conditions_list=condition_list)

        for timetracking in active_timetrackings:
            timetracking = UserRecord('timetracking', timetracking.get('recordid_'))
            timetracking.values['end'] = datetime.datetime.now().strftime("%H:%M")
            timetracking.values['stato'] = "Terminato"

            worktime, worktime_string = calculate_worktime(
                timetracking.values['start'],
                timetracking.values['end']
            )

            timetracking.values['worktime'] = worktime
            timetracking.values['worktime_string'] = worktime_string

            timetracking.save()

            taskid = timetracking.values['recordidtask_']
            if taskid:
                task = UserRecord('task', taskid)
                task.values['tracked_time'] = calculate_task_total(
                    taskid,
                    userid,
                    None,
                    None,
                )
                task.save()

        return True
    except:
        return False


def calculate_pausetime(pausetime_string):
    """
    pausetime_string: stringa HH:MM
    ritorna: pausetime_decimal
    """
    if not pausetime_string:
        return 0.0

    hours, minutes = map(int, pausetime_string.split(":"))
    pausetime_decimal = hours + minutes / 60

    return round(pausetime_decimal, 2)


def calculate_worktime(start, end):
    """
    start, end: stringhe HH:MM
    ritorna: (worktime_decimal, worktime_string)
    """
    time_format = '%H:%M'

    start_dt = datetime.datetime.strptime(start, time_format)
    end_dt = datetime.datetime.strptime(end, time_format)

    if end_dt < start_dt:
        raise ValueError("End precedente allo start")

    delta = end_dt - start_dt
    total_minutes = int(delta.total_seconds() / 60)

    hours, minutes = divmod(total_minutes, 60)
    worktime_string = f"{hours:02}:{minutes:02}"
    worktime_decimal = round(delta.total_seconds() / 3600, 2)

    return worktime_decimal, worktime_string


def check_ai_server():
    """
    Verifica se il server AI è attivo e risponde correttamente.
    Restituisce un tuple (bool, message).
    """
    try:
        url = os.environ.get("AI_URL")
        
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            return True, "Il server AI è attivo e raggiungibile."
        else:
            return False, f"Il server ha risposto con codice errore: {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return False, "Errore di connessione: il server sembra essere spento o la porta 8080 è chiusa."
    except requests.exceptions.Timeout:
        return False, "Il server non ha risposto entro il tempo limite (timeout)."
    except Exception as e:
        return False, f"Si è verificato un errore imprevisto: {str(e)}"


def check_ai_chat_server():
    """
    Verifica se il server AI è attivo e risponde correttamente.
    Restituisce un tuple (bool, message).
    """
    try:
        url = os.environ.get("AI_CHAT_URL")
        
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            return True, "Il server AI è attivo e raggiungibile."
        else:
            return False, f"Il server ha risposto con codice errore: {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return False, "Errore di connessione: il server sembra essere spento o la porta 8080 è chiusa."
    except requests.exceptions.Timeout:
        return False, "Il server non ha risposto entro il tempo limite (timeout)."
    except Exception as e:
        return False, f"Si è verificato un errore imprevisto: {str(e)}"


def get_timetracking_ai_summary(tracking_data, instructions = None):
    """
    Invia la lista di descrizioni dei timetracking all'agente AI per ottenere la descrizione timesheet
    """
    url = os.environ.get("AI_URL") + "summarize"
    key = os.environ.get("AI_ENCRYPTION_KEY")
    
    if not key:
        return "Errore: AI_ENCRYPTION_KEY non configurata nel client."
    
    try:
        fernet = Fernet(key.encode())
        
        raw_payload = json.dumps({"entries": tracking_data, "instructions": instructions})
        
        encrypted_data = fernet.encrypt(raw_payload.encode()).decode()
        
        start = time.time()

        headers = {
            "Content-Type": "application/json",
            "X-Content-Type-Options": "nosniff"
        }
        
        response = requests.post(
            url,
            json={"data": encrypted_data},
            headers=headers,
            timeout=120 
        )
        response.raise_for_status()

        encrypted_response_data = response.json().get("data")
        if not encrypted_response_data:
            return "Errore: Il server ha restituito un formato non atteso."

        decrypted_response = fernet.decrypt(encrypted_response_data.encode()).decode()
        result_json = json.loads(decrypted_response)
        
        print(f"Tempo di esecuzione: {time.time() - start:.2f} secondi")
        return result_json.get("summary")
        
    except Exception as e:
        return f"Errore sicurezza o comunicazione: {str(e)}"


def get_timesheet_ai_summary(timesheets_per_user_data):
    """
    Ottiene il riassunto globale usando django-environ per le configurazioni.
    """
    url = env("AI_URL", default=None) + "summarize-team"
    key = env("AI_ENCRYPTION_KEY", default=None)
    
    if not key:
        return "Errore: AI_ENCRYPTION_KEY non configurata nel client."

    f = Fernet(key.encode())

    reports_payload = []
    for user_data in timesheets_per_user_data:
        dipendente = user_data['anagrafica']
        ts_list = user_data['timesheets']
        
        if ts_list:
            clean_entries = []
            for ts in ts_list:
                raw_desc = ts.get('description')
                desc_sicura = str(raw_desc) if raw_desc is not None else "Attività senza descrizione"
                
                try:
                    time_val = float(ts.get('totaltime_decimal', 0) or 0)
                except (ValueError, TypeError):
                    time_val = 0.0

                clean_entries.append({
                    "description": desc_sicura,
                    "worktime": time_val
                })

            reports_payload.append({
                "full_name": f"{dipendente.get('firstname', '')} {dipendente.get('lastname', '')}".strip(),
                "entries": clean_entries
            })

    if not reports_payload:
        return "Nessuna attività valida da processare."

    payload = {
        "reports": reports_payload,
        "date": datetime.datetime.now().strftime("%d/%m/%Y")
    }

    try:
        json_data = json.dumps(payload).encode()
        encrypted_payload = f.encrypt(json_data).decode()
        
        response = requests.post(url, json={"data": encrypted_payload}, timeout=120)
        
        if response.status_code == 400:
            detail = response.json().get('detail', 'Errore validazione')
            return f"Errore 400 dal server AI: {detail}"
            
        response.raise_for_status()

        enc_res = response.json().get("data")
        dec_res = json.loads(f.decrypt(enc_res.encode()).decode())
        
        return dec_res.get("summary", "Riassunto non disponibile.")
        
    except Exception as e:
        return f"Errore di comunicazione: {str(e)}"
