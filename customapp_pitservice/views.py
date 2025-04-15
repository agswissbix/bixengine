from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt
from commonapp.bixmodels.helper_db import *
import pdfkit
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.helper import *


        
@csrf_exempt
def stampa_bollettino(request):
    post_data = json.loads(request.body)
    data={}
    filename='bollettino.pdf'
    
    recordid_bollettino = ''
    if request.method == 'POST':
        recordid_bollettino = post_data.get('recordid')
    record_bollettino = UserRecord('bollettini',recordid_bollettino)
    recordid_stabile=record_bollettino.get_field('recordidstabile_')['value']
    record_stabile=UserRecord('stabile',recordid_stabile)
    recordid_dipendente=record_bollettino.get_field('recordiddipendente_')['value']
    record_dipendente=UserRecord('dipendente',recordid_dipendente)
    recordid_cliente=record_bollettino.get_field('recordidcliente_')['value']
    record_cliente=UserRecord('cliente',recordid_cliente)
    data['nome_cliente']=record_cliente.get_field('nome_cliente')['value']
    data['indirizzo_cliente']=record_cliente.get_field('indirizzo')['value']
    data['cap_cliente']=record_cliente.get_field('cap')['value']
    data['citta_cliente']=record_cliente.get_field('citta')['value']
    data['riferimento']=record_stabile.get_field('riferimento')['value']
    data['data']=record_bollettino.get_field('data')['value']
    data['dipendente']=record_dipendente.get_field('nome')['value']+' '+record_dipendente.get_field('cognome')['value']
    data['informazioni']=record_bollettino.get_field('informazioni')['value']
    data['contattatoda']=record_bollettino.get_field('contattatoda')['value']
    data['causa']=record_bollettino.get_field('causa')['value']
    data['interventorichiesto']=record_bollettino.get_field('interventorichiesto')['value']
    data['id']=record_bollettino.get_field('id')['value']
    data['nr']=record_bollettino.get_field('nr')['value']
    data['sostituzionedal']=record_bollettino.get_field('sostituzionedal')['value']
    data['sostituzioneal']=record_bollettino.get_field('sostituzioneal')['value']
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


    #return HttpResponse(content)

    try:
        with open(filename_with_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/pdf")
            response['Content-Disposition'] = f'inline; filename={filename}'
            return response
        return response

    finally:
        os.remove(filename_with_path)


@csrf_exempt
def stampa_bollettino_test(request):
    data={}
    filename='bollettino.pdf'
    
    recordid_bollettino = ''
    data = json.loads(request.body)
    recordid_bollettino = data.get('recordid')
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    
    content = render_to_string('pdf/bollettino_test.html', data)

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


    #return HttpResponse(content)

    try:
        with open(filename_with_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/pdf")
            response['Content-Disposition'] = f'inline; filename={filename}'
            return response
        return response

    finally:
        os.remove(filename_with_path)