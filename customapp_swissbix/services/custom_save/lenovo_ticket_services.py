from commonapp.bixmodels.user_record import UserRecord
from commonapp.utils.email_sender import EmailSender

class LenovoTicketService:
    @staticmethod
    def send_status_update_email(recordid: str) -> None:
        """
        Invia un'email di notifica al cliente quando il ticket Lenovo 
        viene "preso in consegna".
        """
        ticket = UserRecord('ticket_lenovo', recordid)
        
        # Recupera l'email dal ticket
        recipient_email = ticket.values.get('email')
        
        # Se non c'è l'email, non possiamo inviare la notifica
        if not recipient_email:
            return
            
        # Costruzione email
        email_data = {}
        email_data['to'] = recipient_email
        email_data['subject'] = "Il tuo dispositivo è stato preso in consegna - Swissbix"
        
        # Dettagli del ticket per la mail
        name = ticket.values.get('name', None)
        surname = ticket.values.get('surname', None)
        brand = ticket.values.get('brand', 'N/A')
        model = ticket.values.get('model', 'N/A')
        serial = ticket.values.get('serial', 'N/A')
        companyname = ticket.values.get('company_name', 'Signore/a')

        if not name and not surname:
            customer_name = companyname
        else:
            customer_name = f"{name} {surname}".strip()
        
        device_info = f"{brand} {model}".strip()
        
        mailbody = f"""
        <p style="margin:0 0 6px 0;">Gentile {customer_name},</p>
        <p style="margin:0 0 10px 0;">Ti informiamo che il tuo dispositivo è stato preso in consegna e verrà preso in gestione dal nostro team tecnico.</p>

        <table style="border-collapse:collapse; width:100%; font-size:14px; margin-top: 15px;">
            <tr><td style="padding:4px 0; font-weight:bold; width: 120px;">Dispositivo:</td><td>{device_info}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Seriale:</td><td>{serial}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Stato attuale:</td><td>Preso in consegna</td></tr>
        </table>
        
        <p style="margin:16px 0 0 0;">
            Ti aggiorneremo non appena ci saranno novità.
        </p>
        <p style="margin:15px 0 0;">Cordiali saluti,</p>
        <p style="margin:0;">Il team Swissbix</p>
        """
        
        email_data['text'] = mailbody
        email_data['cc'] = ""
        email_data['bcc'] = ""
        email_data['attachment_relativepath'] = ""
        email_data['attachment_name'] = ""
        
        # Invio
        EmailSender.save_email('ticket_lenovo', recordid, email_data)
