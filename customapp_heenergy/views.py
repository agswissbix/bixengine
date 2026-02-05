import json
import logging
import os
import uuid
import datetime
import base64
from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import JsonResponse, HttpResponseNotFound, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from bixengine.settings import BASE_DIR
from commonapp.bixmodels.user_record import UserRecord
from customapp_swissbix.utils.browser_manager import BrowserManager

logger = logging.getLogger(__name__)

def to_base64(path):
    """Converte immagine locale in Base64 per l'incorporamento nel PDF."""
    if path and os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception as e:
            print(f"Errore conversione Base64: {e}")
    return None

@csrf_exempt
def print_pdf_heenergy(request):
    """
    Generates PDF for Heenergy invoice.
    Expects 'recordid' in the request body (UUID of the invoice/fattura).
    """
    try:
        data = json.loads(request.body)
        recordid_fattura = data.get('recordid', None)
        if not recordid_fattura:
            return JsonResponse({'error': 'Missing recordid'}, status=400)

        # 1. Fetch Invoice Data
        fattura_record = UserRecord('fattura', recordid_fattura)
        if not fattura_record.values:
            return JsonResponse({'error': f'Invoice with id {recordid_fattura} not found'}, status=404)
        
        fattura_data = fattura_record.values
        
        # 2. Prepare Context
        # Structure matches what the new template will expect
        # 1. Demo Data (Rich Structure for "ActiveMind-style" template)
        
        # 1. Demo Data (Heenergy Invoice + Swiss QR)

        company = UserRecord('azienda', fattura_data.get('recordidazienda_', None))
        company_data = company.values
        if not company_data:
            return JsonResponse({'error': f'Company with id {fattura_data.get("recordidazienda_", None)} not found'}, status=404)
            
        # Mocking the structure 
        client_info = {
            "nome": company_data.get('nominativo', ''),
            "appellativo": company_data.get('appellativo', ''),
            "indirizzo": company_data.get('Via', ''),
            "citta": company_data.get('Comune', ''),
            "cap": company_data.get('nap', ''),
            "paese": company_data.get('cantone', ''),
            "id": int(company_data.get('codicecliente', ''))
        }

        riga_fattura_records = fattura_record.get_linkedrecords_dict('riga_fattura')

        lines = []
        total = 0
        for riga_fattura_record in riga_fattura_records:
            riga_fattura_data = riga_fattura_record
            recordidprodotto_ = riga_fattura_data.get('recordidprodotto_', '')
            prodotto = UserRecord('prodotto', recordidprodotto_)
            prodotto_data = prodotto.values
            lines.append({
                "title": riga_fattura_data.get('descrizione', ''),
                "code": prodotto_data.get('codice', 'N/'),
                "um": "N.", # Demo default
                "quantity": riga_fattura_data.get('quantita', 0),
                "unitPrice": riga_fattura_data.get('prezzo_vendita', 0),
                "discount": 0, # Placeholder
                "total": riga_fattura_data.get('totale_prezzo_vendita', 0)
            })
            if riga_fattura_data.get('totale_prezzo_vendita', 0):
                total += riga_fattura_data.get('totale_prezzo_vendita', 0)
        
        offer_data = {
            "products": lines,
            "totals": {
                "imponibile": total,
                "iva": total * 0.081,
                "grand_total": total + (total * 0.081)
            }
        }
        
        # QR Swiss Data
        qr_data = {
            "iban": "CH18 8080 8003 0084 3120 9",
            "ref": f"RFXX {fattura_data.get('nr_documento', '')}",
            "amount": total + (total * 0.081),
            "currency": "CHF",
            "payable_to": "HE-Energy Sagl\nVia Campagna 32\n6934 Bioggio",
            "payable_by": f"{client_info['nome']}\n{client_info['indirizzo']}\n{client_info['cap']} {client_info['citta']}",
        }
        
        # --- BASE64 IMAGES CONVERSION ---
        static_img_path = os.path.join(settings.BASE_DIR, "customapp_heenergy/static/images")
        
        img_heenergy = to_base64(os.path.join(static_img_path, "heenergy.png"))
        img_paradigma = to_base64(os.path.join(static_img_path, "para_digma.png"))
        img_kronoterm = to_base64(os.path.join(static_img_path, "kronoterm.png"))
        img_saj = to_base64(os.path.join(static_img_path, "saj.png"))
        img_messana = to_base64(os.path.join(static_img_path, "messana.png"))
        img_sinum = to_base64(os.path.join(static_img_path, "sinum.png"))
        img_qrcode_placeholder = to_base64(os.path.join(static_img_path, "qrcode.png"))

        context = {
            "client_info": client_info,
            "offer_data": offer_data,
            "qr_data": qr_data,
            "date": datetime.datetime.now().strftime("%d.%m.%Y"),
            # Images
            "img_heenergy": img_heenergy,
            "img_paradigma": img_paradigma,
            "img_kronoterm": img_kronoterm,
            "img_saj": img_saj,
            "img_messana": img_messana,
            "img_sinum": img_sinum,
            "img_qrcode_placeholder": img_qrcode_placeholder,
        }
        
        # Uncomment to use real DB data later
        if fattura_data:
           context.update({
               "nr_documento": fattura_data.get('nr_documento', ''),
               "data": fattura_data.get('data', ''),
               "nominativo_cliente": fattura_data.get('nominativo_cliente', ''),
               "riferimento": fattura_data.get('riferimento', ''),
               "tipologia_pagamento": fattura_data.get('tipologia_pagamento', ''),
               "imponibile": fattura_data.get('imponibile', 0),
               "imposta": fattura_data.get('imposta', 0),
               "totale": fattura_data.get('totale', 0),
               "status": fattura_data.get('stato', ''),
           })

        # 3. Render HTML
        html_content = render_to_string(
            'heenergy/pdf_template.html',
            context,
            request=request
        )

        # 4. Generate PDF path
        pdf_filename = f"heenergy_invoice_{recordid_fattura}_{uuid.uuid4().hex}.pdf"
        temp_pdf_path = os.path.join(
            BASE_DIR, "tmp", pdf_filename
        )
        os.makedirs(os.path.dirname(temp_pdf_path), exist_ok=True)

        # 5. Generate PDF with Playwright
        BrowserManager.generate_pdf(
            html_content=html_content,
            output_path=temp_pdf_path,
        )

        # 6. Stream and Delete
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
            return HttpResponseNotFound("PDF generation failed.")

    except Exception as e:
        logger.error(f"Error generating Heenergy PDF: {str(e)}")
        return JsonResponse({'error': f'Error generating PDF: {str(e)}'}, status=500)
