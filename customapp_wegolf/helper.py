
from functools import lru_cache
from commonapp.bixmodels.user_table import *

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
from commonapp.helper import Helper as CommonHelper

class Helper:
    DEFAULT_LANG = "it"
    geolocator = Nominatim(user_agent="golf_app")

    @classmethod
    @lru_cache(maxsize=256)
    def cached_safe_geocode(cls, location_name):
        return cls.safe_geocode(location_name)

    @classmethod
    def safe_geocode(cls, location_name, retries=2):
        """Tenta di geocodificare un nome paese, con retry e gestione errori."""
        if not location_name or not isinstance(location_name, str):
            return None
        
        for _ in range(retries):
            try:
                loc = cls.geolocator.geocode(location_name, timeout=5)
                return (loc.latitude, loc.longitude) if loc else None
            except (GeocoderTimedOut, GeocoderServiceError):
                time.sleep(1)  # piccolo delay e retry
            except Exception:
                break
        return None

    @classmethod
    @functools.lru_cache(maxsize=1) 
    def get_cached_languages_data(cls):
        """
        Recupera le lingue e le mette in cache
        """
        try:
            languages_table = UserTable("languages")
            languages_list = languages_table.get_records(conditions_list=[])
            if not languages_list:
                languages_list = [{"language": "italiano", "code": "it", "fieldid": "italian"}]
        except Exception as e:
            languages_list = [{"language": "italiano", "code": "it", "fieldid": "italian"}]

        code_to_field_map = {}
        field_to_code_map = {}
        
        for lang in languages_list:
            code = lang.get("code")
            fieldid = lang.get("fieldid") 
            
            if code and fieldid:
                code_to_field_map[code] = fieldid
                field_to_code_map[fieldid] = code

        return {
            "list": languages_list,
            "code_to_field": code_to_field_map,
            "field_to_code": field_to_code_map
        }

    @classmethod
    def get_available_languages(cls):
        """
        Recupera la lista delle lingue disponibili
        """
        try:
            languages_table = UserTable("languages")
            languages = languages_table.get_records(conditions_list=[])
            
            if not languages:
                languages = [{"language": "italiano", "code": "it"}]
            
            return languages

        except Exception as e:
            languages = [{"language": "italiano", "code": "it"}]


    @classmethod
    def get_user_language(cls, userid):
        try:
            if not userid:
                return cls.DEFAULT_LANG
            
            golf_club = HelpderDB.sql_query_row(f"SELECT Lingua FROM user_golfclub WHERE utente = {userid}") 

            if not golf_club:
                return cls.DEFAULT_LANG
            
            language_string = golf_club.get("Lingua", "")

            if not language_string:
                return cls.DEFAULT_LANG


            lang_data = cls.get_cached_languages_data()
            
            language_code = lang_data["field_to_code"].get(language_string, cls.DEFAULT_LANG)

            return language_code
        
        except Exception as e:
            return cls.DEFAULT_LANG

    @classmethod
    def get_localized_labels_fields_chart(cls, chart_config, request=None):
        if request:
            userid = CommonHelper.get_userid(request)
            language = Helper.get_user_language(userid)
        else:
            userid = None
            language = cls.DEFAULT_LANG

        tableid = chart_config.get("from_table")
        field_ids = []

        # --- recupero alias nei datasets ---
        for ds in chart_config.get("datasets", []):
            if "alias" in ds:
                field_ids.append(ds["alias"])

        # --- recupero alias nei datasets2 (se presenti) ---
        for ds in chart_config.get("datasets2", []):
            if "alias" in ds:
                field_ids.append(ds["alias"])

        # --- recupero alias nel group_by_field ---
        gb = chart_config.get("group_by_field")
        if gb and "alias" in gb:
            field_ids.append(gb["alias"])

        labels = []

        # --- esecuzione query sys_field per ciascun fieldid ---
        sql = """
            SELECT label 
            FROM sys_field
            WHERE tableid = %s AND fieldid = %s
        """

        exclude_labels = ['golfclub', 'Dati']

        for fieldid in field_ids:
            label = Helper.get_translation(tableid, fieldid, userid=userid, code=language)
            if not label:
                label = HelpderDB.sql_query_value(sql, 'label', [tableid, fieldid])
            if not label or label in labels or label in exclude_labels:
                continue
            labels.append(label)

        return labels

    @classmethod
    def get_translation(cls, tableid, fieldid, userid=None, code=None, translation_type="Field"):
        language_code = cls.DEFAULT_LANG

        if code:
            language_code = code
        elif userid:
            language_code = cls.get_user_language(userid)
        
        lang_data = cls.get_cached_languages_data()
        language_field = lang_data["code_to_field"].get(language_code, lang_data["code_to_field"][cls.DEFAULT_LANG])

        try:
            translations_table = UserTable('translations')
            condition_list = [
                f"`type`='{translation_type}'",
                f"tableid='{tableid}'",
                f"identifier='{fieldid}'",
            ]

            translation = translations_table.get_records(conditions_list=condition_list)

            if not translation:
                return fieldid
            
            word = translation[0].get(language_field)
            return word if word else fieldid
        
        except Exception as e:
            return fieldid
        
    @classmethod
    def get_cached_translation(cls, translations, fieldid, userid=None, code=None, translation_type="Field"):
        if not translations:
            return ""

        language_code = cls.DEFAULT_LANG

        if code:
            language_code = code
        elif userid:
            language_code = cls.get_user_language(userid)
        
        lang_data = cls.get_cached_languages_data()
        language_field = lang_data["code_to_field"].get(language_code, lang_data["code_to_field"][cls.DEFAULT_LANG])

        try: 
            found_translation = next(
                (item for item in translations if 
                item.get('type') == translation_type and 
                item.get('identifier') == fieldid
                ), 
                None
            )

            if not found_translation:
                return ""
            
            word = found_translation.get(language_field)
            return word if word else ""

        except Exception as e:
            return ""

    @classmethod
    def resolve_localized_chart_title(cls, sys_chart_name, user_chart_row, user_language):
        """
        Risolve il titolo localizzato accedendo a user_chart_row.
        Usa title_{lingua} se la lingua != 'en', altrimenti (o come fallback) usa title.
        """
        if not user_chart_row:
            return sys_chart_name
            
        loc_title = None
        if user_language and user_language != 'en':
            loc_title = user_chart_row.get(f"title_{user_language}")
            
        if not loc_title:
            loc_title = user_chart_row.get("title")
            
        return loc_title if loc_title else sys_chart_name