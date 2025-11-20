import os
import re
import json
import mimetypes
from pathlib import Path
from django.db import connection, connections, DatabaseError
from django.core.mail import EmailMultiAlternatives, BadHeaderError
from django.core.files.storage import default_storage
from django.conf import settings


class HelpderDB:
    """
    Utility sicure per interagire con il database e gestire file/upload/email.
    """

    # ==========================
    #  SQL EXECUTION METHODS
    # ==========================

    @classmethod
    def sql_query(cls, sql: str, params = None):
        """Esegue una query SQL e restituisce tutti i risultati come lista di dizionari."""
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute(sql, params)
                rows = cls.dictfetchall(cursor)
            return rows
        except DatabaseError as e:
            print(f"[DB ERROR] sql_query: {e}")
            return []

    @classmethod
    def sql_query_row(cls, sql: str, params = None):
        """Esegue una query SQL e restituisce solo la prima riga."""
        try:
            rows = cls.sql_query(sql, params)
            return rows[0] if rows else None
        except Exception as e:
            print(f"[DB ERROR] sql_query_row: {e}")
            return None

    @classmethod
    def sql_query_value(cls, sql: str, column: str, params = None):
        """Esegue una query e restituisce un singolo valore (colonna specifica)."""
        row = cls.sql_query_row(sql, params)
        return row.get(column) if row else None

    @classmethod
    def sql_execute(cls, sql: str):
        """Esegue un comando SQL (senza parametri)."""
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute(sql)
            return True
        except DatabaseError as e:
            print(f"[DB ERROR] sql_execute: {e}")
            return False

    @classmethod
    def sql_execute_safe(cls, sql: str, params_list: list):
        """Esegue un comando SQL parametrizzato in modo sicuro."""
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute(sql, tuple(params_list))
            return True
        except DatabaseError as e:
            print(f"[DB ERROR] sql_execute_safe: {e}")
            return False

    @classmethod
    def dictfetchall(cls, cursor):
        """Converte un cursore Django in lista di dizionari."""
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    # ==========================
    #  EMAIL METHODS
    # ==========================

    @classmethod
    def send_email(
        cls,
        emails,
        subject,
        html_message=None,
        cc=None,
        bcc=None,
        recordid=None,
        attachment=None,
    ):
        """Invia una mail HTML con opzioni di CC, BCC e allegati."""
        cc = cls.ensure_list(cc)
        bcc = cls.ensure_list(bcc)
        to_list = cls.ensure_list(emails)

        msg = EmailMultiAlternatives(
            subject=subject,
            body="",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
            to=to_list,
            cc=cc,
            bcc=bcc,
        )

        if html_message:
            msg.attach_alternative(html_message, "text/html")

        if attachment and Path(attachment).is_file():
            mime, _ = mimetypes.guess_type(attachment)
            mime = mime or "application/octet-stream"
            with open(attachment, "rb") as f:
                msg.attach(Path(attachment).name, f.read(), mime)

        try:
            msg.send(fail_silently=False)
        except (BadHeaderError, Exception) as e:
            print(f"[EMAIL ERROR] send_email: {e}")
            return False

        # Aggiorna lo stato nel DB
        if recordid:
            cls.sql_execute_safe(
                "UPDATE user_email SET status = 'Inviata' WHERE recordid_ = %s",
                [recordid],
            )

        return True

    # ==========================
    #  FILE PATH METHODS
    # ==========================

    @classmethod
    def validate_path_components(cls, *args):
        """Valida che ogni parte di un percorso contenga solo caratteri sicuri."""
        pattern = re.compile(r"^[\w\-]+$")
        for part in args:
            if not pattern.match(str(part)):
                raise ValueError(f"Invalid path component: {part}")

    @classmethod
    def get_upload_fullpath(cls, tableid, recordid, field):
        """Restituisce il percorso assoluto di un file caricato (PDF)."""
        cls.validate_path_components(tableid, recordid, field)
        file_path = os.path.join(settings.UPLOADS_ROOT, f"{tableid}/{recordid}/{field}.pdf")
        return default_storage.path(file_path)

    @classmethod
    def get_uploadedfile_fullpath(cls, tableid, recordid, field):
        """Restituisce il percorso assoluto del file caricato se esiste, altrimenti None."""
        cls.validate_path_components(tableid, recordid, field)
        file_path = os.path.join(settings.UPLOADS_ROOT, f"{tableid}/{recordid}/{field}.pdf")

        if default_storage.exists(file_path):
            full_path = default_storage.path(file_path)
            if os.path.exists(full_path):
                return full_path

        print(f"[FILE WARNING] File non trovato: {file_path}")
        return None

    @classmethod
    def get_uploadedfile_relativepath(cls, tableid, recordid, field):
        """Restituisce il percorso relativo del file caricato."""
        cls.validate_path_components(tableid, recordid, field)
        return f"{tableid}/{recordid}/{field}.pdf"

    # ==========================
    #  UTILITY METHODS
    # ==========================

    @classmethod
    def ensure_list(cls, value):
        """Converte vari tipi in una lista di stringhe pulite."""
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value if v]
        return [v.strip() for v in str(value).split(";") if v.strip()]

    # ==========================
    #  LINKED RECORDS
    # ==========================

    @classmethod
    def get_linked_records_by_ids(cls, table_name: str, key_field: str, record_ids: list):
        """Recupera in modo sicuro record collegati da una tabella user_*."""
        if not record_ids:
            return []

        # Sicurezza contro SQL injection
        if not table_name.isidentifier() or not key_field.isidentifier():
            raise ValueError("Invalid table or field name.")

        placeholders = ", ".join(["%s"] * len(record_ids))
        sql = f"""
            SELECT recordid_, {key_field}
            FROM user_{table_name}
            WHERE recordid_ IN ({placeholders})
        """

        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, record_ids)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except DatabaseError as e:
            print(f"[DB ERROR] get_linked_records_by_ids: {e}")
            return []
