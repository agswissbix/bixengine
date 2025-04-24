import mimetypes
from pathlib import Path
from django.core.mail import EmailMultiAlternatives
from django.db import connections

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
        attachment=None
    ):
        cc      = cls.ensure_list(cc)
        bcc     = cls.ensure_list(bcc)
        to_list = cls.ensure_list(emails)

        # Corpo testuale minimo
        text_message = ""

        msg = EmailMultiAlternatives(
            subject    = subject,
            body       = text_message,
            from_email = "pitservice-bixdata@sender.swissbix.ch",
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
                msg.attach(Path(attachment).name, f.read(), mime)

        msg.send(fail_silently=False)

  

        return True
