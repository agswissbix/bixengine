import mimetypes
from pathlib import Path
from django.core.mail import EmailMultiAlternatives
from django.db import connections
from commonapp.bixmodels.user_record import *
import shutil


class EmailSender:

    @classmethod
    def ensure_list(cls, value):
        if not value:
            return []
        if isinstance(value, str):
            # Split by comma and strip whitespace
            return [email.strip() for email in value.split(',') if email.strip()]
        if isinstance(value, list):
            # Handle case where list contains comma-separated emails
            result = []
            for item in value:
                if isinstance(item, str):
                    result.extend([email.strip() for email in item.split(',') if email.strip()])
                else:
                    result.append(item)
            return result
        return [value]

    @classmethod
    def send_email(
        cls, emails, subject,
        html_message=None,
        cc=None, bcc=None,
        recordid=None,
        attachment=None,
        attachment_name=None,
    ):
        cc      = cls.ensure_list(cc)
        bcc     = cls.ensure_list(bcc)
        to_list = cls.ensure_list(emails)

        # Corpo testuale minimo
        text_message = ""

        msg = EmailMultiAlternatives(
            subject    = subject,
            body       = text_message,
            from_email = "segreteria@pitservice.ch",
            to         = to_list,
            cc         = cc,
            bcc        = bcc,
        )

        # Aggiunta HTML
        if html_message:
            msg.attach_alternative(html_message, "text/html")

        # Allegato
        if attachment and Path(attachment).exists():
            mime, _ = mimetypes.guess_type(attachment)
            mime = mime or "application/pdf"
            with open(attachment, "rb") as f:
                filename = attachment_name or Path(attachment).name
                msg.attach(filename, f.read(), mime)

        msg.send(fail_silently=False)

  

        return True
    
    @classmethod
    def save_email(cls, tableid, recordid, email_data):
        #TODO 
        if tableid == 'rendicontolavanderia':
            record_rendiconto=UserRecord('rendicontolavanderia',recordid)
            if record_rendiconto.values['stato']=='Nessuna ricarica':
                record_rendiconto.values['stato']="Inviato - Nessuna ricarica"
            else:
                record_rendiconto.values['stato']="Inviato"
            record_rendiconto.save()
        record_email=UserRecord('email')
        record_email.values['recipients']=email_data['to']
        record_email.values['subject']=email_data['subject']  
        mail_body=email_data['text']
        if mail_body:
            mail_body=mail_body.replace('<p>','<p style="margin:0 0 4px 0;">')  
        record_email.values['mailbody']=mail_body
        record_email.values['cc']=email_data['cc']
        record_email.values['ccn']=email_data['bcc']
        
        record_email.values['status']="Da inviare"
        record_email.save()

        attachment_relativepath=email_data['attachment_relativepath']
        if attachment_relativepath != '':   
            record_email.values['attachment_name']=email_data['attachment_name'] 
            if attachment_relativepath.startswith("commonapp/static"):
                base_dir=settings.BASE_DIR
                file_path = os.path.join(settings.BASE_DIR, attachment_relativepath)
                #fullpath_originale = default_storage.path(file_path)
                fullpath_originale = Path(file_path)
                fullpath_originale=str(fullpath_originale)
            else:
                    fullpath_originale=HelpderDB.get_uploadedfile_fullpath(tableid,recordid,'allegato')
            
            fullpath_email=HelpderDB.get_upload_fullpath('email',record_email.recordid,'attachment')
            #  Assicurati che la cartella di destinazione esista
            os.makedirs(os.path.dirname(fullpath_email), exist_ok=True)

            # ------------------ copia dell’allegato -------------
            if os.path.isfile(fullpath_originale):
                shutil.copy2(fullpath_originale, fullpath_email)
            
            record_email.values['attachment']=f"email/{record_email.recordid}/attachment.pdf"

        record_email.save()
