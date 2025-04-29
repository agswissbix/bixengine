from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt
import pdfkit
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *
import locale
import re


@csrf_exempt
def stampa_bollettino(request):
    post_data = json.loads(request.body)
    data = {}
    

    recordid_bollettino = ''
    if request.method == 'POST':
        recordid_bollettino = post_data.get('recordid', '')

    record_bollettino = UserRecord('bollettini', recordid_bollettino)

    # Estrazione sicura degli ID
    recordid_stabile = record_bollettino.get_field('recordidstabile_').get('value', '') or ''
    recordid_dipendente = record_bollettino.get_field('recordiddipendente_').get('value', '') or ''
    recordid_cliente = record_bollettino.get_field('recordidcliente_').get('value', '') or ''

    # Creazione sicura dei record
    try:
        record_stabile = UserRecord('stabile', recordid_stabile) if recordid_stabile.strip() else None
        if record_stabile and record_stabile.values is None:
            record_stabile = None
    except:
        record_stabile = None

    try:
        record_dipendente = UserRecord('dipendente', recordid_dipendente) if recordid_dipendente.strip() else None
        if record_dipendente and record_dipendente.values is None: 
            record_dipendente = None
    except:
        record_dipendente = None

    try:
        record_cliente = UserRecord('cliente', recordid_cliente) if recordid_cliente.strip() else None
        if record_cliente and record_cliente.values is None:
            record_cliente = None
    except:
        record_cliente = None

    # Safe access ai campi
    def get_value_safe(record, fieldname):
        try:
            return record.get_field(fieldname).get('value', '') if record else ''
        except:
            return ''

    data['nome_cliente'] = get_value_safe(record_cliente, 'nome_cliente')
    data['indirizzo_cliente'] = get_value_safe(record_cliente, 'indirizzo')
    data['cap_cliente'] = get_value_safe(record_cliente, 'cap')
    data['citta_cliente'] = get_value_safe(record_cliente, 'citta')
    data['riferimento'] = get_value_safe(record_stabile, 'riferimento')
    if get_value_safe(record_bollettino, 'data'):
        data['data'] = datetime.datetime.strptime(get_value_safe(record_bollettino, 'data'), "%Y-%m-%d").strftime("%d.%m.%Y")
    else:
        data['data'] = ''
    data['dipendente'] = f"{get_value_safe(record_dipendente, 'nome')} {get_value_safe(record_dipendente, 'cognome')}".strip()
    data['informazioni'] = get_value_safe(record_bollettino, 'informazioni')
    data['contattatoda'] = get_value_safe(record_bollettino, 'contattatoda')
    data['causa'] = get_value_safe(record_bollettino, 'causa')
    data['interventorichiesto'] = get_value_safe(record_bollettino, 'interventorichiesto')
    data['id'] = get_value_safe(record_bollettino, 'id')
    data['nr'] = get_value_safe(record_bollettino, 'nr')
    data['sostituzionedal'] = get_value_safe(record_bollettino, 'sostituzionedal')
    data['sostituzioneal'] = get_value_safe(record_bollettino, 'sostituzioneal')
    data['notelavoro'] = get_value_safe(record_bollettino, 'notelavoro')

    script_dir = os.path.dirname(os.path.abspath(__file__))
    wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    
    tipo_bollettino=record_bollettino.get_field('tipo_bollettino')['value']

    if tipo_bollettino=='Generico':
        content = render_to_string('pdf/bollettino_generico.html', data)
    if tipo_bollettino=='Sostituzione':
        content = render_to_string('pdf/bollettino_sostituzione.html', data)
    if tipo_bollettino=='Pulizia':
        content = render_to_string('pdf/bollettino_pulizia.html', data)
    if tipo_bollettino=='Tinteggio':
        content = render_to_string('pdf/bollettino_tinteggio.html', data)
    if tipo_bollettino=='Picchetto':
        content = render_to_string('pdf/bollettino_picchetto.html', data)
    if tipo_bollettino=='Giardino':
        content = render_to_string('pdf/bollettino_giardino.html', data)

    filename = f"Nr.{data['nr']} {record_stabile.values['indirizzo']} {tipo_bollettino} .pdf"
    if tipo_bollettino=='Sostituzione':
        filename = f"Nr.{data['nr']} {record_stabile.values['indirizzo']} Sostituzione Dal {data['sostituzionedal']} Al {data['sostituzioneal']}.pdf"
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    filename_with_path = os.path.dirname(os.path.abspath(__file__))
    filename_with_path = filename_with_path.rsplit('views', 1)[0]
    filename_with_path = filename_with_path + '\\static\\pdf\\' + filename
    print(filename_with_path)
    #filename_with_path2 = os.path.join(settings.BASE_DIR, 'static', 'pdf', filename)
    #print(filename_with_path2)
    pdfkit.from_string(
    content,
    filename_with_path,
    configuration=config,
    options={
        "enable-local-file-access": "",
        # "quiet": ""  # <-- rimuovilo!
    }
    )


    #return HttpResponse(content)

    try:
        with open(filename_with_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/pdf")
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response
        return response

    finally:
        os.remove(filename_with_path)


@csrf_exempt
def stampa_bollettino_test(request):
    data={}
    filename='test.pdf'
    

    content = render_to_string('pdf/bollettino_test.html', data)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    filename_with_path = os.path.dirname(os.path.abspath(__file__))
    filename_with_path = filename_with_path.rsplit('views', 1)[0]
    filename_with_path = filename_with_path + '\\static\\pdf\\' + filename
    pdfkit.from_string(
        content,
        filename_with_path,
        configuration=config,
        options={
            "enable-local-file-access": "",
            # "quiet": ""  # <-- rimuovilo!
        }
    )

    try:
        with open(filename_with_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/pdf")
            response['Content-Disposition'] = f'inline; filename={filename}'
            return response
        return response

    finally:
        os.remove(filename_with_path)

@csrf_exempt
def stampa_gasoli(request):
    data={}
    filename='report gasolio'
    recordid_stabile = ''
    data = json.loads(request.body)
    if request.method == 'POST':
        recordid_stabile = data.get('recordid')
        #meseLettura=data.get('date')
        meseLettura="2025 04-Aprile"
        anno, mese = meseLettura.split(' ')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    
    record_stabile=UserRecord('stabile',recordid_stabile)
    data['stabile']=record_stabile.values
    sql=f"""
    SELECT t.recordid_,t.anno,t.mese,t.datalettura,t.lettura, i.riferimento, i.livellominimo, i.capienzacisterna
    FROM user_letturagasolio t
    INNER JOIN (
        SELECT recordidinformazionigasolio_, MAX(datalettura) AS max_datalettura
        FROM user_letturagasolio
        WHERE anno='{anno}' AND mese like '%{mese}%' AND deleted_='N' AND recordidstabile_ = '{recordid_stabile}'
        GROUP BY recordidinformazionigasolio_
        
    ) subquery
    ON t.recordidinformazionigasolio_ = subquery.recordidinformazionigasolio_ 
    AND t.datalettura = subquery.max_datalettura
    INNER JOIN user_informazionigasolio i
    ON t.recordidinformazionigasolio_ = i.recordid_
    WHERE t.recordidstabile_ = '{recordid_stabile}' AND t.deleted_ = 'N' 
            """
    ultimeletturegasolio = HelpderDB.sql_query(sql)
    data['ultimeletturegasolio']=ultimeletturegasolio
    
    content = render_to_string('pdf/gasolio.html', data)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    filename_with_path = os.path.dirname(os.path.abspath(__file__))
    filename_with_path = filename_with_path.rsplit('views', 1)[0]
    filename_with_path = filename_with_path + '\\static\\pdf\\' + filename
    pdfkit.from_string(
        content,
        filename_with_path,
        configuration=config,
        options={
            "enable-local-file-access": "",
            # "quiet": ""  # <-- rimuovilo!
        }
    )

    try:
        with open(filename_with_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/pdf")
            response['Content-Disposition'] = f'inline; filename={filename}'
            return response
        return response

    finally:
        os.remove(filename_with_path)



def crea_lista_lavanderie(request):
    # Extract any needed data from the request, if relevant
    # mese = request.POST.get('mese')
    # Ottieni la data attuale
    # Imposta la localizzazione in italiano
    post_data = json.loads(request.body)
    meserichiesto=  post_data.get('mese')
    locale.setlocale(locale.LC_TIME, "it_IT.utf8")

    now = datetime.datetime.now()
    current_year=now.year
    current_month_num = now.month
    
    # Mese corrente
    if meserichiesto == 'mesecorrente':
        month = current_month_num # Formato numerico (es. 2)
        year=current_year
        month_2digit = f"{month:02d}"  # Due cifre (es. "02")
        month_name = now.strftime("%B").capitalize()  # Nome esteso con prima lettera maiuscola (es. "Febbraio")
    else:
        # Mese successivo
        month = current_month_num + 1 if current_month_num < 12 else 1  # Gestisce il passaggio da dicembre a gennaio
        year = current_year  if current_month_num < 12 else current_year + 1
        month_2digit = f"{month:02d}"  # Due cifre (es. "03")
        month_name = datetime.date(now.year if month > 1 else now.year + 1, month, 1).strftime("%B").capitalize()

    mese=month_2digit+'-'+month_name
    sql=f"""
            SELECT DISTINCT recordidstabile_
            FROM user_informazionilavanderia
            WHERE deleted_ = 'N'
            AND recordidstabile_ NOT IN (
                SELECT recordidstabile_
                FROM user_rendicontolavanderia
                WHERE anno = '{year}' 
                AND mese = '{mese}'
                AND deleted_ = 'N'
            );


    """
    informazionilavanderia_records=HelpderDB.sql_query(sql)
    counter=0
    for informazionelavanderia in informazionilavanderia_records:
        record_rendiconto=UserRecord('rendicontolavanderia')
        record_rendiconto.values['recordidstabile_']=informazionelavanderia['recordidstabile_']
        record_stabile=UserRecord('stabile',informazionelavanderia['recordidstabile_'])
        record_rendiconto.values['recordidcliente_']=record_stabile.values['recordidcliente_']
        record_rendiconto.values['mese']=mese
        record_rendiconto.values['anno']=year
        record_rendiconto.values['stato']="Da fare"
        record_rendiconto.save()
        counter=counter+1
    # Return them in a JSON response (or use as needed)
    return JsonResponse({
        'success': True,
        'counter': counter
    })

