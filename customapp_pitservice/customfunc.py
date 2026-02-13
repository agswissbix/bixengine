from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
import pyodbc
import environ
from django.conf import settings
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from datetime import *

from commonapp.helper import Helper
from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.user_table import UserTable
from commonapp.bixmodels.helper_db import HelpderDB

# Initialize environment variables
env = environ.Env()
environ.Env.read_env()

def save_record_fields(tableid,recordid,old_record=None):

    # ---ORE MENSILI---
    if tableid == 'oremensili':
        oremensili_record = UserRecord('oremensili', recordid)
        dipendente_recordid = oremensili_record.values['recordiddipendente_']
        save_record_fields('dipendente', dipendente_recordid)


    # ---ASSENZE---
    if tableid == 'assenze':
        assenza_record = UserRecord('assenze', recordid)
        dipendente_recordid= assenza_record.values['recordiddipendente_']
        dipendente_record = UserRecord('dipendente', dipendente_recordid)
        assenza_record.values['riferimento'] = dipendente_record.values['riferimento'] + " - " + assenza_record.values['tipo_assenza']
        assenza_record.values['ruolo'] = dipendente_record.values['ruolo']
        assenza_record.save()

    # ---DIPENDENTE---
    if tableid == 'dipendente':
        dipendente_record = UserRecord('dipendente', recordid)
        if Helper.isempty(dipendente_record.values['cognome']):
            dipendente_record.values['cognome'] = ""
        if Helper.isempty(dipendente_record.values['nome']):
            dipendente_record.values['nome'] = ""
        riferimento = dipendente_record.values['nome'] + " " + dipendente_record.values['cognome']
        dipendente_record.values['riferimento'] = riferimento

        allegati= HelpderDB.sql_query(f"SELECT * FROM user_attachment WHERE recordiddipendente_='{recordid}' AND deleted_='N'")
        nrallegati=len(allegati) 
        dipendente_record.values['nrallegati'] = nrallegati

        ore_mensili_table=UserTable('oremensili')
        oremensili_recente_records=ore_mensili_table.get_records(conditions_list=[f"recordiddipendente_='{recordid}'","deleted_='N'"], limit=1, orderby="recordid_ DESC")
        if oremensili_recente_records:
            oremensili_recente_record= oremensili_recente_records[0]
            dipendente_record.values['saldoore'] = oremensili_recente_record['saldo_ore']
            dipendente_record.values['saldovacanze'] = oremensili_recente_record['saldo_vacanze']
        
        dipendente_record.save()


    if tableid == 'stabile':
        stabile_record = UserRecord('stabile', recordid)
        if Helper.isempty(stabile_record.values['titolo_stabile']):
            stabile_record.values['titolo_stabile'] = ""
        if Helper.isempty(stabile_record.values['indirizzo']):
            stabile_record.values['indirizzo'] = ""
        riferimento = stabile_record.values['titolo_stabile'] + " " + stabile_record.values['indirizzo']
        stabile_record.values['riferimento'] = riferimento
        stabile_record.save()
        sql_riferimentocompleto = """
            UPDATE user_stabile AS stabile
            JOIN user_cliente AS cliente
            ON stabile.recordidcliente_ = cliente.recordid_
            SET stabile.riferimentocompleto = CONCAT(cliente.nome_cliente, ' ', stabile.riferimento);
        """
        HelpderDB.sql_execute(sql_riferimentocompleto)

    
        
        

    if tableid == 'contatti':
        contatto_record = UserRecord('contatti', recordid)
        if Helper.isempty(contatto_record.values['nome']):
            contatto_record.values['nome'] = ""
        if Helper.isempty(contatto_record.values['cognome']):
            contatto_record.values['cognome'] = ""
        riferimento = contatto_record.values['nome'] + " " + contatto_record.values['cognome']
        contatto_record.values['riferimento'] = riferimento
        contatto_record.save()

    #---CONTATTO STABILE---
    if tableid == 'contattostabile':
        contattostabile_record = UserRecord('contattostabile', recordid)
        contatto_record = UserRecord('contatti', contattostabile_record.values['recordidcontatti_'])
        contattostabile_record.values['nome'] = contatto_record.values['nome']
        contattostabile_record.values['cognome'] = contatto_record.values['cognome']
        contattostabile_record.values['email'] = contatto_record.values['email']
        contattostabile_record.values['telefono'] = contatto_record.values['telefono']
        contattostabile_record.values['ruolo'] = contatto_record.values['ruolo']
        contattostabile_record.save()

    #---ARTIGIANO STABILE---
    if tableid == 'artigianostabile':
        artigianostabile_record = UserRecord('artigianostabile', recordid)
        artigiano_record = UserRecord('artigiano', artigianostabile_record.values['recordidartigiano_'])
        artigianostabile_record.values['email'] = artigiano_record.values['email']
        artigianostabile_record.values['telefono'] = artigiano_record.values['telefono']
        artigianostabile_record.values['ruolo'] = artigiano_record.values['ramo']
        artigianostabile_record.save()

    # ---LETTURE GASOLIO---
    if tableid == 'letturagasolio':
        letturagasolio_record = UserRecord('letturagasolio', recordid)
        stabile_record = UserRecord('stabile', letturagasolio_record.values['recordidstabile_'])
        informazionigasolio_record = UserRecord('informazionigasolio', letturagasolio_record.values['recordidinformazionigasolio_'])

        capienzacisterna = Helper.safe_float(informazionigasolio_record.values['capienzacisterna'])
        letturacm = Helper.safe_float(letturagasolio_record.values['letturacm'])

        if capienzacisterna:
            if capienzacisterna == 1500:
                if letturacm:
                    letturagasolio_record.values['letturalitri'] = letturacm * 10
            if capienzacisterna == 2000:
                if letturacm:
                    letturagasolio_record.values['letturalitri'] = letturacm * 13

        #TODO anno dinamico
        #letturagasolio_record.values['anno']='2025'
        letturagasolio_record.values['recordidcliente_'] = stabile_record.values['recordidcliente_']
        letturagasolio_record.values['capienzacisterna'] = capienzacisterna
        letturagasolio_record.values['livellominimo'] = informazionigasolio_record.values['livellominimo']
        letturagasolio_record.save()

    # ---BOLLETTINI---
    if tableid == 'bollettini':
        bollettino_record = UserRecord('bollettini', recordid)
        tipo_bollettino = bollettino_record.values['tipo_bollettino']
        data_bollettino = bollettino_record.values['data']
        nr = bollettino_record.values['nr']
        if not nr:
            if not tipo_bollettino:
                tipo_bollettino = ''
            
            current_year = datetime.now().year
            and_year = f" AND YEAR(creation_) = '{current_year}'"

            sql = f"SELECT * FROM user_bollettini WHERE tipo_bollettino='{tipo_bollettino}'{and_year} AND creation_>='2026-02-01' AND deleted_='N' ORDER BY nr desc LIMIT 1"
            bollettino_recorddict = HelpderDB.sql_query_row(sql)
            if bollettino_recorddict['nr'] is None:
                nr = 1
            else:
                nr = int(bollettino_recorddict['nr']) + 1
            bollettino_record.values['nr'] = nr

        allegato = bollettino_record.values['allegato']
        if allegato:
            bollettino_record.values['allegatocaricato'] = 'Si'
        else:
            bollettino_record.values['allegatocaricato'] = 'No'

        stabile_record = UserRecord('stabile', bollettino_record.values['recordidstabile_'])
        cliente_recordid = stabile_record.values['recordidcliente_']
        bollettino_record.values['recordidcliente_'] = cliente_recordid
        bollettino_record.save()

    if tableid == 'rendicontolavanderia':
        rendiconto_record = UserRecord('rendicontolavanderia', recordid)
        if rendiconto_record.values['stato'] == 'Da fare' and rendiconto_record.values['allegato']:
            rendiconto_record.values['stato'] = 'Preparato'
        rendiconto_record.save()

    if tableid == 'richieste':
        richieste_record = UserRecord('richieste', recordid)
        richieste_record.values['stato'] = 'Merce spedita'
        richieste_record.save()

    # ---OFFERTE---
    if tableid == 'offerta':
        offerta_record = UserRecord('offerta', recordid)
        offerta_id = offerta_record.values['id']
        offerta_record.values['nrofferta'] = offerta_id
        offerta_record.save()

    #---CONTRATTO---
    if tableid == 'contratto':
        contratto_record = UserRecord('contratto', recordid)
        pianificazioni=contratto_record.get_linkedrecords_dict('pianificazione_contrattuale')
        if pianificazioni and len(pianificazioni) > 0:
            contratto_record.values['pianificazioni'] = 'Si'

        righe=contratto_record.get_linkedrecords_dict('righe')
        if righe and len(righe) > 0:
            contratto_record.values['dettagli'] = 'Si'
        
        contratto_record.save()

    #---PIANIFICAZiONE CONTRATTUALE---
    if tableid == 'pianificazione_contrattuale':
        pianificazione_contrattuale_record = UserRecord('pianificazione_contrattuale', recordid)
        contratto_recordid=pianificazione_contrattuale_record.values['recordidcontratto_']
        save_record_fields('contratto', contratto_recordid)

    #---RIGHE DI DETTAGLIO---
    if tableid == 'righe':
        righe_record = UserRecord('righe', recordid)
        contratto_recordid=righe_record.values['recordidcontratto_']
        save_record_fields('contratto', contratto_recordid)
    

    # ---ATTACHMENT---
    if tableid == 'attachment':
        attachment_record = UserRecord('attachment', recordid)
        dipendente_recordid=attachment_record.values['recordiddipendente_']
        if dipendente_recordid:
            save_record_fields('dipendente', dipendente_recordid)
        #dipendente_record = UserRecord('dipendente', dipendente_recordid)
        #allegati= HelpderDB.sql_query(f"SELECT * FROM user_attachment WHERE recordiddipendente_='{attachment_record.values['recordiddipendente_']}' AND deleted_='N'")
        #nrallegati=len(allegati) 
        #dipendente_record.values['nrallegati'] = nrallegati
        #dipendente_record.save()



    

    

    # ---RISCALDAMENTO---
    if tableid == 'riscaldamento':
        riscaldamento_record = UserRecord('riscaldamento', recordid)
        stabile_record = UserRecord('stabile', riscaldamento_record.values['recordidstabile_'])
        riscaldamento_record.values['recordidcliente_'] = stabile_record.values['recordidcliente_']
        riscaldamento_record.save()

    # ---PISCINA---
    if tableid == 'piscina':
        piscina_record = UserRecord('piscina', recordid)
        stabile_record = UserRecord('stabile', piscina_record.values['recordidstabile_'])
        piscina_record.values['recordidcliente_'] = stabile_record.values['recordidcliente_']
        piscina_record.save()










def calculate_dependent_fields(request):
    data = json.loads(request.body)
    updated_fields = {}
    recordid=data.get('recordid')
    tableid=data.get('tableid')
    return JsonResponse({'status': 'success', 'updated_fields': updated_fields})
