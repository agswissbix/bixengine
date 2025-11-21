from django.shortcuts import render
from django.http import JsonResponse
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import HelpderDB
from commonapp.helper import *
from .helper import Helper as WegolfHelper





# Create your views here.

def get_benchmark_filters(request):
    golfclub_table=UserTable('golfclub')
    userid = Helper.get_userid(request)
    
    sql = f"""
        SELECT g.nome_club AS title,
               g.recordid_ AS recordid,
               g.Logo AS logo,
               g.paese AS paese
        FROM user_golfclub AS g
        JOIN user_metrica_annuale AS m
           ON g.recordid_ = m.recordidgolfclub_
        WHERE (g.dati_anonimi = 'false' OR g.dati_anonimi IS NULL) 
            AND g.deleted_ = 'N' AND m.deleted_ = 'N'
        GROUP BY title, recordid
        ORDER BY title ASC
    """

    clubs = HelpderDB.sql_query(sql)

    sql_user_club = f"SELECT nome_club as title, recordid_ as recordid, logo, paese FROM user_golfclub WHERE utente = '{userid}'"
    logged_club = HelpderDB.sql_query(sql_user_club)

    if logged_club:
        logged_club = logged_club[0]

    already_present = any(c['recordid'] == logged_club['recordid'] for c in clubs)

    if already_present:
        clubs = [c for c in clubs if c['recordid'] != logged_club['recordid']]
    clubs.insert(0, logged_club)

    fields = SysField.objects.filter(tableid='metrica_annuale', fieldtypewebid='Numero').values('fieldid', 'description').order_by('description')

    for field in fields:
        translation = WegolfHelper.get_translation('metrica_annuale', field.get('fieldid'), userid = userid, translation_type="Field")
        if translation:
            field['description'] = translation
    
    fieldsClub = SysField.objects.filter(tableid='golfclub', fieldtypewebid='Numero').values('fieldid', 'description').order_by('description')
    for field in fieldsClub:
        translation = WegolfHelper.get_translation('golfclub', field.get('fieldid'), userid = userid, translation_type="Field")
        if translation:
            field['description'] = translation

    response_data = {
            'filterOptionsNumbers': [
                {'field': field['fieldid'], 'label': field['description']}
                for field in fields
            ],
            'filterOptionsDemographic': [
                {'field': field['fieldid'], 'label': field['description']}
                for field in fieldsClub
            ],
            'availableClubs': clubs
        }
        
    # Restituisce il dizionario completo come risposta JSON
    # 'safe=True' (default) è corretto perché stiamo restituendo un dizionario
    return JsonResponse(response_data)


def check_data_anonymous(request):
    userid = Helper.get_userid(request)
    sql = f"SELECT dati_anonimi FROM user_golfclub WHERE utente = %s"
    dati_anonimi = HelpderDB.sql_query_value(sql, 'dati_anonimi', [userid])

    if dati_anonimi == 'true':
        return JsonResponse({'success': False, 'is_anonymous': True})

    return JsonResponse({'success': True, 'is_anonymous': False})

def get_filtered_clubs(request):
    data = json.loads(request.body)
    userid = Helper.get_userid(request)
    filters = data.get('filters', {})

    conditions = " TRUE"
    numeric_filters = filters.get('numericFilters', [])
    demographic_filters = filters.get('demographicFilters', [])

    # --------------------------------------------------------
    # 1. FILTRI NUMERICI → inclusi nella SQL
    # --------------------------------------------------------
    for nf in numeric_filters:
        field = nf.get('field')
        operator = nf.get('operator')
        value = nf.get('value')
        if value is not None:
            conditions += f" AND m.{field} {operator} {value}"

    # --------------------------------------------------------
    # 2. FILTRI DEMOGRAFICI (tranne distance) → inclusi nella SQL
    # --------------------------------------------------------
    # li tengo da parte per il filtro distanza
    distance_filter = None

    for df in demographic_filters:
        field = df.get('field')
        operator = df.get('operator')
        value = df.get('value')

        if field == "distance":
            distance_filter = df  # verrà gestito DOPO la query
            continue

        # campi booleani
        if field in ['colelgamenti_pubblici', 'infrastrutture_turistiche']:
            if isinstance(value, bool):
                value_db = 'Si' if value else 'No'
                conditions += f" AND g.{field} = '{value_db}'"
            continue

        # anno fondazione
        if field == "anno_fondazione":
            if value is not None:
                conditions += f" AND g.{field} {operator} {value}"
            continue

        # altri campi testuali
        if value:
            conditions += f" AND g.{field} = '{value}'"

    # --------------------------------------------------------
    # 3. ESECUZIONE QUERY senza distanza
    # --------------------------------------------------------
    sql = f"""
        SELECT g.nome_club AS title,
               g.recordid_ AS recordid,
               g.Logo AS logo,
               g.paese AS paese
        FROM user_golfclub AS g
        JOIN user_metrica_annuale AS m
           ON g.recordid_ = m.recordidgolfclub_
        WHERE (g.dati_anonimi = 'false' OR g.dati_anonimi IS NULL) 
            AND g.deleted_ = 'N' AND m.deleted_ = 'N' 
            AND {conditions}
        GROUP BY title, recordid
        ORDER BY title ASC
    """

    # # --------------------------------------------------------
    # # 2. COSTRUZIONE DEI JOIN DINAMICI PER FILTRI NUMERICI
    # # --------------------------------------------------------
    # join_clauses = []
    # select_fields = []

    # for i, nf in enumerate(numeric_filters, start=1):
    #     field = nf.get('field')
    #     operator = nf.get('operator')
    #     value = nf.get('value')

    #     alias = f"m{i}"
    #     select_fields.append(f"{alias}.{field} AS {field}_value")

    #     join_clause = f"""
    #     LEFT JOIN (
    #         SELECT m.recordidgolfclub_, m.{field}
    #         FROM user_metrica_annuale m
    #         WHERE m.deleted_ = 'N'
    #         AND m.{field} IS NOT NULL
    #         AND m.anno = (
    #             SELECT MAX(m2.anno)
    #             FROM user_metrica_annuale m2
    #             WHERE m2.recordidgolfclub_ = m.recordidgolfclub_
    #                 AND m2.deleted_ = 'N'
    #                 AND m2.{field} IS NOT NULL
    #         )
    #         {"AND m." + field + f" {operator} {value}" if value is not None else ""}
    #     ) {alias} ON {alias}.recordidgolfclub_ = g.recordid_
    #     """
    #     join_clauses.append(join_clause)

    # # --------------------------------------------------------
    # # 3. COSTRUZIONE QUERY FINALE
    # # --------------------------------------------------------
    # sql = f"""
    #     SELECT g.nome_club AS title,
    #         g.recordid_ AS recordid,
    #         g.Logo AS logo,
    #         g.paese AS paese,
    #         {', '.join(select_fields)}
    #     FROM user_golfclub AS g
    #     {" ".join(join_clauses)}
    #     WHERE (g.dati_anonimi = 'false' OR g.dati_anonimi IS NULL)
    #     AND g.deleted_ = 'N'
    #     AND {conditions_g}
    #     ORDER BY title ASC
    # """

    clubs = HelpderDB.sql_query(sql)

    sql_user_club = f"SELECT nome_club as title, recordid_ as recordid, logo, paese FROM user_golfclub WHERE utente = '{userid}'"
    logged_club = HelpderDB.sql_query(sql_user_club)

    if logged_club:
        logged_club = logged_club[0]

    # --------------------------------------------------------
    # 4. Filtro distanza applicato DOPO la query
    # --------------------------------------------------------
    if distance_filter:
        operator = distance_filter.get('operator')
        max_distance = distance_filter.get('value')

        # paese dell’utente
        user_country = logged_club['paese']

        user_coords = WegolfHelper.cached_safe_geocode(user_country)
        if not user_coords:
            return JsonResponse({'availableClubs': []}, safe=False)

        # costruisci una cache dei paesi dei club → 1 geocode per paese, non per club!
        unique_countries = {club['paese'] for club in clubs if club.get('paese')}
        geocoded_countries = {c: WegolfHelper.cached_safe_geocode(c) for c in unique_countries}

        filtered = []
        for club in clubs:
            country = club.get('paese')
            coords = geocoded_countries.get(country)

            if not coords:
                continue

            from geopy.distance import geodesic
            dist = geodesic(user_coords, coords).km

            if operator == "<=" and dist <= max_distance:
                filtered.append(club)
            elif operator == ">=" and dist >= max_distance:
                filtered.append(club)

        clubs = filtered

    # --------------------------------------------------------

    already_present = any(c['recordid'] == logged_club['recordid'] for c in clubs)

    if already_present:
        clubs = [c for c in clubs if c['recordid'] != logged_club['recordid']]
    clubs.insert(0, logged_club)

    return JsonResponse({'availableClubs': clubs}, safe=False)

def get_wegolf_welcome_data(request):
    userid = Helper.get_userid(request)
    recordidgolfclub = HelpderDB.sql_query_value(
        f"SELECT recordid_ FROM user_golfclub WHERE utente = {userid}", 
        "recordid_"
    )
    sql = f"SELECT nome_club, logo FROM user_golfclub WHERE recordid_ = '{recordidgolfclub}'"
    golfclub_name = HelpderDB.sql_query_value(sql, "nome_club")
    golfclub_logo = HelpderDB.sql_query_value(sql, "logo")
    response_data = {
        'golfclubName': golfclub_name or '',
        'golfclubLogo': golfclub_logo or '',
        'recordidGolfclub': recordidgolfclub or ''
    }
    return JsonResponse(response_data)


def get_settings_data(request):
    try:
        userid = Helper.get_userid(request)

        recordidgolfclub = HelpderDB.sql_query_value(
            f"SELECT recordid_ FROM user_golfclub WHERE utente = {userid}", 
            "recordid_"
        )

        if not recordidgolfclub:
            return JsonResponse({"error": "Nessun golf club associato all'utente"}, status=404)

        club_data = HelpderDB.sql_query_row(
            f"SELECT * FROM user_golfclub WHERE recordid_ = '{recordidgolfclub}'"
        )

        if not club_data:
            return JsonResponse({"error": "Dati del golf club non trovati"}, status=404)

        settings = {
            "id": str(recordidgolfclub),
            "nome": club_data.get("nome_club", ""),
            "paese": club_data.get("paese", ""),
            "nazione": club_data.get("nazione", ""),
            "indirizzo": club_data.get("indirizzo", ""),
            "email": club_data.get("email", ""),
            "annoFondazione": club_data.get("anno_fondazione", ""),
            "collegamentiPubblici": club_data.get("colelgamenti_pubblici", ""),
            "direttore": club_data.get("direttore", ""),
            "infrastruttureTuristiche": club_data.get("infrastrutture_turistiche", ""),
            "pacchettiGolf": club_data.get("pacchetti_golf", ""),
            "struttureComplementari": club_data.get("strutture_complementari", ""),
            "territorioCircostante": club_data.get("territorio_circostante", ""),
            "tipoGestione": club_data.get("tipo_gestione", ""),
            "note": club_data.get("note", ""),
            "datiAnonimi": str(club_data.get("dati_anonimi")).lower() == 'true',
            "lingua": club_data.get("Lingua", ""),
            "valuta": club_data.get("valuta", ""),
            "formatoNumerico": club_data.get("formato_numerico", ""),
            "formatoData": club_data.get("formato_data", ""),
            "logo": club_data.get("Logo", "")
        }

        languages = []
        available_languages = WegolfHelper.get_available_languages()

        for lang in available_languages:
            languages.append(
                {
                    "code": lang.get("code"),
                    "value": lang.get("fieldid"),
                    "label": WegolfHelper.get_translation("translations", lang.get("fieldid"), userid= userid)
                }
            )

        response = {
            "settings": settings,
            "languages": languages
        }

        return JsonResponse(response, safe=False, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def update_club_settings(request):
    try:
        if request.method != "POST":
            return JsonResponse({"error": "Metodo non consentito"}, status=405)

        # Recupera i dati inviati nel form
        data = request.POST
        logo_file = request.FILES.get("logo")

        userid = Helper.get_userid(request)

        recordidgolfclub = HelpderDB.sql_query_value(
            f"SELECT recordid_ FROM user_golfclub WHERE utente = {userid}", 
            "recordid_"
        )

        if not recordidgolfclub:
            return JsonResponse({"error": "Nessun golf club associato all'utente"}, status=404)

        club = UserRecord('golfclub', recordidgolfclub)

        # Aggiorna i campi testuali
        club.values['nome_club'] = data.get("nome", club.values.get('nome_club'))
        club.values['paese'] = data.get("paese", club.values.get('paese'))
        club.values['nazione'] = data.get("nazione", club.values.get('nazione'))
        club.values['indirizzo'] = data.get("indirizzo", club.values.get('indirizzo'))
        club.values['email'] = data.get("email", club.values.get('email'))
        club.values['anno_fondazione'] = data.get("annoFondazione", club.values.get('anno_fondazione'))
        club.values['colelgamenti_pubblici'] = data.get("collegamentiPubblici", club.values.get('collegamenti_pubblici'))
        club.values['direttore'] = data.get("direttore", club.values.get('direttore'))
        club.values['infrastrutture_turistiche'] = data.get("infrastruttureTuristiche", club.values.get('infrastrutture_turistiche'))
        club.values['pacchetti_golf'] = data.get("pacchettiGolf", club.values.get('pacchetti_golf'))
        club.values['strutture_complementari'] = data.get("struttureComplementari", club.values.get('strutture_complementari'))
        club.values['territorio_circostante'] = data.get("territorioCircostante", club.values.get('territorio_circostante'))
        club.values['tipo_gestione'] = data.get("tipoGestione", club.values.get('tipo_gestione'))
        club.values['note'] = data.get("note", club.values.get('note'))
        club.values['dati_anonimi'] = data.get("datiAnonimi", club.values.get('dati_anonimi')) 
        club.values['Lingua'] = data.get("lingua", club.values.get('lingua'))
        club.values['valuta'] = data.get("valuta", club.values.get('valuta'))
        club.values['formato_numerico'] = data.get("formatoNumerico", club.values.get('formato_numerico'))
        club.values['formato_data'] = data.get("formatoData", club.values.get('formato_data'))

        # Elimino il file se in delete o update
        if (data.get("logo", None) == "$remove$" and club.values.get('Logo', None)) or (club.values.get('Logo', None) and logo_file):
            if default_storage.exists(club.values.get('Logo', '')):
                default_storage.delete(club.values['Logo'])
            club.values['Logo'] = None

        # Se è stato caricato un logo, salvalo sul server
        if logo_file:
            # Percorso completo: BACKUP_DIR/golfclub/<recordid>/logo/
            save_dir = os.path.join(settings.UPLOADS_ROOT, "golfclub", str(recordidgolfclub))
            os.makedirs(save_dir, exist_ok=True)

            # name, ext = logo_file

            # Nome del file e percorso finale
            file_path = os.path.join(save_dir, logo_file.name)

            # Salvataggio fisico del file
            with default_storage.open(file_path, "wb+") as destination:
                for chunk in logo_file.chunks():
                    destination.write(chunk)

            # Salva il path relativo nel DB (ad esempio per usarlo nel frontend)
            relative_path = f"golfclub/{recordidgolfclub}/{logo_file.name}"
            club.values['Logo'] = relative_path

        # Salva nel DB
        club.save()

        updated_settings = {
            "id": str(recordidgolfclub),
            "nome": club.values.get("nome_club", ""),
            "paese": club.values.get("paese", ""),
            "nazione": club.values.get("nazione", ""),
            "indirizzo": club.values.get("indirizzo", ""),
            "email": club.values.get("email", ""),
            "annoFondazione": club.values.get("anno_fondazione", ""),
            "collegamentiPubblici": club.values.get("colelgamenti_pubblici", ""),
            "direttore": club.values.get("direttore", ""),
            "infrastruttureTuristiche": club.values.get("infrastrutture_turistiche", ""),
            "pacchettiGolf": club.values.get("pacchetti_golf", ""),
            "struttureComplementari": club.values.get("strutture_complementari", ""),
            "territorioCircostante": club.values.get("territorio_circostante", ""),
            "tipoGestione": club.values.get("tipo_gestione", ""),
            "note": club.values.get("note", ""),
            "datiAnonimi": str(club.values.get("dati_anonimi")).lower() == 'true',
            "lingua": club.values.get("Lingua", ""),
            "valuta": club.values.get("valuta", ""),
            "formatoNumerico": club.values.get("formato_numerico", ""),
            "formatoData": club.values.get("formato_data", ""),
            "logo": club.values.get("Logo", "")
        }

        languages = []
        available_languages = WegolfHelper.get_available_languages()

        for lang in available_languages:
            languages.append(
                {
                    "code": lang.get("code"),
                    "value": lang.get("fieldid"),
                    "label": WegolfHelper.get_translation("translations", lang.get("fieldid"), userid= userid)
                }
            )


        return JsonResponse({
            "success": True,
            "message": "Impostazioni del club aggiornate correttamente.",
            "settings": updated_settings,
            "languages": languages
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def get_documents(request):
    user_id = Helper.get_userid(request)
    documents_table=UserTable('documents', userid=user_id)
    documents=documents_table.get_records(conditions_list=[])

    data = []

    for document in documents:
        categories = []
        categorie = document.get('categoria', '').split(',')

        for category in categorie:
            categories.append(category.strip())

        file = document.get('file', '')

        file_type = ""
        if file:
            file_type = file.split('.')[-1]

        date = document.get('data')
        
        if date:
            if hasattr(date, 'date'):
                date = date.date().isoformat()
            elif hasattr(date, 'isoformat'):
                date = date.isoformat()
            elif isinstance(date, str):
                date = date[:10]
        else:
            date = ""

        if document.get('stato', '') == "Pubblicato":
            data.append({
                'id': document.get('recordid_', ''),
                'title': document.get('titolo', ''),
                'description': document.get('descrizione', ''),
                'fileType': file_type,
                'categories': categories,
                'record_id': file,
                'data': date,
            })

    return JsonResponse({"documents": data}, safe=False)

def request_new_document(request):
    user_id = Helper.get_userid(request)
    
    try:
        title = request.POST.get('title', '')
        description = request.POST.get('description', '')
        
        categories_str = request.POST.get('categories', '[]') 
        try:
            categories = json.loads(categories_str)
        except:
            categories = []

        categorie = ",".join(categories)

        file_obj = request.FILES.get('file')

        document = UserRecord('documents', userid=user_id)
        document.values['titolo'] = title
        document.values['descrizione'] = description
        document.values['categoria'] = categorie
        
        document.values['data'] = datetime.datetime.now() 
        document.values['stato'] = "Bozza"
        

        document.save()

        if file_obj:
            target_dir = os.path.join(settings.UPLOADS_ROOT, "documents", document.recordid)
            
            os.makedirs(target_dir, exist_ok=True)

            filename = file_obj.name
            _, ext = os.path.splitext(filename)
            ext = ext.lstrip('.')

            full_file_path = os.path.join(target_dir, filename)

            with open(full_file_path, "wb+") as destination:
                for chunk in file_obj.chunks():
                    destination.write(chunk)

            relative_path = f"documents/{document.recordid}/{filename}"

            document = UserRecord('documents', document.recordid)
            document.values['file'] = relative_path

            document.save()
        
        return JsonResponse({'success': True})

    except Exception as e:
        print(f"Errore nel salvataggio documento: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

def request_new_project(request):
    user_id = Helper.get_userid(request)
    data = json.loads(request.body)

    try:
        title = data.get('title', '')
        description = data.get('description', '')

        categorie = ""
        categories = data.get('categories', [])
        for category in categories:
            categorie += category + ","
        categorie = categorie[:-1]

        document = UserRecord('projects', userid=user_id)
        document.values['titolo'] = title
        document.values['descrizione'] = description
        document.values['categoria'] = categorie
        document.values['data'] = datetime.datetime.now() 
        document.values['stato'] = "Bozza"
        document.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_projects(request):
    userid = Helper.get_userid(request)
    project_table = UserTable('projects', userid)
    projects = project_table.get_records(conditions_list=[])

    data = []

    for project in projects:
        stato = project.get('stato', '')
        if stato != "Pubblicato":
            continue

        categories = []
        categories.append(project.get('categoria', ''))

        documents = project.get('documents', [])

        formatted_documents = []
        for document in documents:
            document_categories = []
            document_categories.append(document.get('categoria', ''))

            file = document.get('file', '')

            file_type = ""
            if file:
                file_type = file.split('.')[-1]

            document_date = document.get('data')
        
            if document_date:
                if hasattr(document_date, 'date'):
                    document_date = document_date.date().isoformat()
                elif hasattr(document_date, 'isoformat'):
                    document_date = document_date.isoformat()
                elif isinstance(document_date, str):
                    document_date = document_date[:10]
            else:
                document_date = ""

            formatted_documents.append({
                'id': document.get('recordid_', ''),
                'title': document.get('titolo', ''),
                'description': document.get('descrizione', ''),
                'fileType': file_type,
                'categories': document_categories,
                'record_id': file,
                'data': document_date,
            })


        project_date = project.get('data', '')
        
        if project_date:
            if hasattr(project_date, 'date'):
                project_date = project_date.date().isoformat()
            elif hasattr(project_date, 'isoformat'):
                project_date = project_date.isoformat()
            elif isinstance(project_date, str):
                project_date = project_date[:10]
        else:
            project_date = ""

        projectid = project.get('recordid_', '')

        like = HelpderDB.sql_query_row(f"SELECT * FROM user_like WHERE recordidprojects_='{projectid}' AND utente='{userid}'")

        likes = HelpderDB.sql_query(f"SELECT * FROM user_like WHERE recordidprojects_='{projectid}'")

        data.append({
            'id':projectid,
            'title': project.get('titolo', ''),
            'description': project.get('descrizione', ''),
            'categories': categories,
            'documents': formatted_documents,
            'data': project_date,
            'like': like is not None,
            'like_number': len(likes)
        })
    
    
    return JsonResponse({"projects": data}, safe=False)

def like_project(request):
    try:
        data = json.loads(request.body)
        projectid = data.get("project", "")

        date = datetime.datetime.now().date() 

        userid = Helper.get_userid(request)
        if not userid:
             return JsonResponse({"error": "Autenticazione richiesta"}, status=401)

        project = UserTable('projects', userid=userid).get_records(conditions_list=[
            f"recordid_='{projectid}'"
        ])
        
        if not project:
            return JsonResponse({"error": "Project not found"}, status=404)
        
        like_record = HelpderDB.sql_query_row(f"SELECT * FROM user_like WHERE recordidprojects_='{projectid}' AND utente='{userid}'")

        if not like_record:
            like = UserRecord('like',)
            like.values['recordidprojects_'] = projectid
            like.values['utente'] = userid
            like.values['data'] = date
            like.save()
            return JsonResponse({"message": "Project liked successfully"}, status=200)
        else:
            return JsonResponse({"error": "Project already liked"}, status=400)
            
    except Exception as e:
        print(f"Error while liking project: {e}")
        return JsonResponse({"error": "Error while liking project", "detail": str(e)}, status=500)

def unlike_project(request):
    try:
        data = json.loads(request.body)
        project = data.get("project", "")
        user = Helper.get_userid(request)
        
        if not user:
             return JsonResponse({"error": "Autenticazione richiesta"}, status=401)

        like_record = HelpderDB.sql_query_row(f"SELECT * FROM user_like WHERE recordidprojects_='{project}' AND utente='{user}'")

        if not like_record:
            return JsonResponse({"error": "Project not liked"}, status=400)
        
        query = f"DELETE FROM user_like WHERE recordidprojects_='{project}' AND utente='{user}'"
        HelpderDB.sql_execute(query)

        return JsonResponse({"message": "Project unliked successfully"}, status=200)

    except Exception as e:
        print(f"Error while unliking project: {e}")
        return JsonResponse({"error": "Error while unliking project", "detail": str(e)}, status=500)
    

def get_languages(request):
    lang_data = WegolfHelper.get_cached_languages_data()

    return JsonResponse({"languages": lang_data["list"]})
    
def get_language(request):
    userid = Helper.get_userid(request)
    language_code = WegolfHelper.get_user_language(userid) 

    return JsonResponse({"language": language_code})

    
def sync_translation_fields(request):
    try:
        translations_table = UserTable('translations')

        all_fields = HelpderDB.sql_query("SELECT * from sys_field")

        existing_translations_raw = translations_table.get_records(
            conditions_list=[],
            limit=1000
        )
        
        existing_set = set()
        for tr in existing_translations_raw:
            existing_set.add((
                tr.get('type'), 
                tr.get('tableid'), 
                tr.get('identifier')
            ))

        
        fields_to_translate = set()    # (tableid, fieldid, description)
        labels_to_translate = set()    # (tableid, label)
        sublabels_to_translate = set() # (tableid, sublabel)

        for field in all_fields:
            table_id = field.get('tableid')
            if not table_id:
                continue

            field_id = field.get('fieldid')
            label = field.get('label')
            sublabel = field.get('sublabel')
            description = field.get('description')

            if field_id and description:
                fields_to_translate.add((table_id, field_id, description))
            
            if label:
                labels_to_translate.add((table_id, label))
                
            if sublabel:
                sublabels_to_translate.add((table_id, sublabel))
        
        new_records_to_save = []

        for (table_id, field_id, description) in fields_to_translate:
            if ('Field', table_id, field_id) not in existing_set:
                print(f"Aggiungo Field: {table_id}.{field_id}")
                new_record = UserRecord('translations')
                new_record.values['type'] = 'Field'
                new_record.values['tableid'] = table_id
                new_record.values['identifier'] = field_id
                new_record.values['italian'] = description
                new_records_to_save.append(new_record)

        for (table_id, label) in labels_to_translate:
            if ('Label', table_id, label) not in existing_set:
                print(f"Aggiungo Label: {table_id}.{label}")
                new_record = UserRecord('translations')
                new_record.values['type'] = 'Label'
                new_record.values['tableid'] = table_id
                new_record.values['identifier'] = label
                new_record.values['italian'] = label 
                new_records_to_save.append(new_record)

        for (table_id, sublabel) in sublabels_to_translate:
            if ('Sublabel', table_id, sublabel) not in existing_set:
                print(f"Aggiungo Sublabel: {table_id}.{sublabel}")
                new_record = UserRecord('translations')
                new_record.values['type'] = 'Sublabel'
                new_record.values['tableid'] = table_id
                new_record.values['identifier'] = sublabel
                new_record.values['italian'] = sublabel
                new_records_to_save.append(new_record)

        if not new_records_to_save:
            print("Nessuna nuova traduzione da aggiungere. Sincronizzazione completata.")
        else:
            print(f"Salvataggio di {len(new_records_to_save)} nuove traduzioni...")
            for record in new_records_to_save:
                record.values["english"] = ""
                record.values["french"] = ""
                record.values["german"] = ""
                record.save()
            print("Salvataggio completato.")

        return JsonResponse({"success": True, "added": len(new_records_to_save)})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
def sync_translation_dashboards(request):
    try:
        translations_table = UserTable('translations')

        all_dashboards = HelpderDB.sql_query("SELECT id, name, description from sys_dashboard")

        existing_translations_raw = translations_table.get_records(
            conditions_list=[],
            limit=2000 
        )
        
        existing_map = {}
        for tr in existing_translations_raw:
            key = (
                tr.get('type'), 
                tr.get('tableid'), 
                tr.get('identifier')
            )
            existing_map[key] = tr

        new_records_to_save = []
        updated_count = 0

        for dash in all_dashboards:
            dash_id = dash.get('id')
            name = dash.get('name')
            description = dash.get('description')

            if not dash_id:
                continue

            if name:
                key_name = ('Dashboard', 'sys_dashboard', dash_id)
                
                if key_name in existing_map:
                    record = existing_map[key_name]
                    current_italian = record.get('italian') 
                    
                    if current_italian != name:
                        print(f"Aggiorno Dashboard Name: {name} (prima era: {current_italian})")
                        record.values['italian'] = name
                        record.save()
                        updated_count += 1
                else:
                    print(f"Aggiungo Dashboard Name: {name}")
                    new_record = UserRecord('translations')
                    new_record.values['type'] = 'Dashboard'
                    new_record.values['tableid'] = 'sys_dashboard'
                    new_record.values['identifier'] = dash_id
                    new_record.values['italian'] = name
                    new_records_to_save.append(new_record)

            if description:
                key_desc = ('DashboardDescription', 'sys_dashboard', dash_id)
                
                if key_desc in existing_map:
                    record = existing_map[key_desc]
                    current_italian = record.get('italian')
                    
                    if current_italian != description:
                        print(f"Aggiorno Dashboard Description per ID {dash_id}")
                        record.values['italian'] = description
                        record.save()
                        updated_count += 1
                else:
                    print(f"Aggiungo Dashboard Description: {dash_id}")
                    new_record = UserRecord('translations')
                    new_record.values['type'] = 'DashboardDescription'
                    new_record.values['tableid'] = 'sys_dashboard'
                    new_record.values['identifier'] = dash_id
                    new_record.values['italian'] = description
                    new_records_to_save.append(new_record)

        if not new_records_to_save:
            print(f"Nessuna nuova dashboard creata. Aggiornati {updated_count} record esistenti.")
        else:
            print(f"Salvataggio di {len(new_records_to_save)} nuove traduzioni...")
            for record in new_records_to_save:
                record.values["english"] = ""
                record.values["french"] = ""
                record.values["german"] = ""
                record.save()
            print("Salvataggio nuovi record completato.")

        return JsonResponse({
            "success": True, 
            "added": len(new_records_to_save), 
            "updated": updated_count
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
 


def get_notifications(request):
    try:
        userid = Helper.get_userid(request)

        title_field = ""
        message_field = ""
        language = WegolfHelper.get_user_language(userid)

        if not language or language == "it":
            title_field = "title"
            message_field = "message"
        else:
            title_field = "titolo_" + language
            message_field = "messaggio_" + language

        golfclub = HelpderDB.sql_query_row(f"SELECT * FROM user_golfclub WHERE utente = {userid}")

        data = []

        notifications_table = UserTable('notification')
        notifications = notifications_table.get_records(conditions_list=[])

        notifications_statuses_table  = UserTable('notification_status', userid=userid)
        notifications_statuses = notifications_statuses_table.get_records(conditions_list=[f"recordidgolfclub_={golfclub.get('recordid_')}"])

        for notification in notifications:
            date = notification.get('date')
            time = notification.get('time')

            isodate = f"{date}T{time}"

            read = False

            found_status = next(
                (s for s in notifications_statuses if str(s.get('recordidnotification_')) == str(notification.get('recordid_'))),
                None
            )

            if found_status:
                status = found_status.get('status')
                if status == 'Read':
                    read = True

                if status != 'Hidden':
                    data.append({
                        'id': notification.get('id', ''),
                        'title': notification.get(title_field, ''),
                        'message': notification.get(message_field, ''),
                        'date': isodate,
                        'read': read,
                        'status_id': found_status.get('recordid_') if found_status else None
                    })

        return JsonResponse({"notifications": data}, safe=False)
    except Exception as e:
        print(e)
        return JsonResponse({"success": False, "error": str(e)}, safe=False)

def mark_all_notifications_read(request):
    try:
        userid = Helper.get_userid(request)
        golfclub = HelpderDB.sql_query_row(f"SELECT * FROM user_golfclub WHERE utente = {userid}")

        notifications_statuses_table  = UserTable('notification_status', userid=userid)
        notifications_statuses = notifications_statuses_table.get_records(conditions_list=[f"recordidgolfclub_={golfclub.get('recordid_')}"])

        for status in notifications_statuses:
            record = UserRecord('notification_status', status.get('recordid_'))
            record.values['status'] = 'Read'
            record.save()

        return JsonResponse({"success": True}, safe=False)
    except Exception as e:
        print(e)
        return JsonResponse({"success": False, "error": str(e)}, safe=False)


def mark_notification_read(request):
    try:
        userid = Helper.get_userid(request)

        data = json.loads(request.body)
        status_id = data.get('status_id', '')

        notifications_statuses_table  = UserTable('notification_status', userid=userid)
        notifications_statuses = notifications_statuses_table.get_records(conditions_list=[f"recordid_={status_id}"])

        if notifications_statuses:
            record = UserRecord('notification_status', status_id)
            record.values['status'] = 'Read'
            record.save()
            return JsonResponse({"success": True}, safe=False)
        else:
            return JsonResponse({"success": False}, safe=False)
    except Exception as e:
        print(e)
        return JsonResponse({"success": False, "error": str(e)}, safe=False)
    
def mark_notification_hidden(request):
    try:
        userid = Helper.get_userid(request)

        data = json.loads(request.body)
        status_id = data.get('status_id', '')

        notifications_statuses_table  = UserTable('notification_status', userid=userid)
        notifications_statuses = notifications_statuses_table.get_records(conditions_list=[f"recordid_={status_id}"])

        if notifications_statuses:
            record = UserRecord('notification_status', status_id)
            record.values['status'] = 'Hidden'
            record.save()
            return JsonResponse({"success": True}, safe=False)
        else:
            return JsonResponse({"success": False}, safe=False)
    except Exception as e:
        print(e)
        return JsonResponse({"success": False, "error": str(e)}, safe=False)