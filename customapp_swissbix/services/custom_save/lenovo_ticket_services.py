from commonapp.bixmodels.user_record import UserRecord
from commonapp.utils.email_sender import EmailSender
from django.http import JsonResponse
from commonapp.models import SysUser

class LenovoTicketService:
    @staticmethod
    def send_status_update_email(recordid: str) -> JsonResponse:
        """
        Invia un'email di notifica al cliente quando il ticket Lenovo 
        viene "preso in consegna".
        """
        ticket = UserRecord('ticket_lenovo', recordid)
        
        # Recupera l'email dal ticket
        recipient_email = ticket.values.get('email')
        
        # Se non c'è l'email, non possiamo inviare la notifica
        if not recipient_email:
            return JsonResponse({'success': False, 'error': 'Email non trovata'}), 400

        # Email al backoffice
        email_backoffice = "backoffice@swissbix.ch"
            
        # Costruzione email
        email_data = {}
        to_addresses = [recipient_email]
        if email_backoffice:
            to_addresses.append(email_backoffice)
            
        email_data['to'] = ",".join(to_addresses)
        
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
        
        email_data['subject'] = f"{customer_name} - Il tuo dispositivo è stato preso in consegna - Swissbix"
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
        <p style="margin:0;">Swissbix SA</p>
        """
        
        email_data['text'] = mailbody
        email_data['cc'] = ""
        email_data['bcc'] = ""
        email_data['attachment_relativepath'] = ""
        email_data['attachment_name'] = ""
        
        # Invio
        EmailSender.save_email('ticket_lenovo', recordid, email_data)


    @staticmethod
    def send_repair_completed_email(recordid: str) -> JsonResponse:
        """
        Invia un'email di notifica al cliente quando il ticket Lenovo 
        risulta "Riparato" e pronto per il ritiro/riconsegna.
        """
        ticket = UserRecord('ticket_lenovo', recordid)
        
        # Recupera l'email dal ticket
        recipient_email = ticket.values.get('email')
        
        # Se non c'è l'email, non possiamo inviare la notifica
        if not recipient_email:
            return JsonResponse({'success': False, 'error': 'Email cliente non trovata'}), 400

        # Email al backoffice (ID 50 come nel tuo esempio)
        email_backoffice = "backoffice@swissbix.ch"
        
        # Costruzione email
        email_data = {}
        # Inviamo a entrambi (cliente e backoffice in copia)
        to_addresses = [recipient_email]
        if email_backoffice:
            to_addresses.append(email_backoffice)
            
        email_data['to'] = ",".join(to_addresses)
        
        # Dettagli del ticket
        name = ticket.values.get('name', None)
        surname = ticket.values.get('surname', None)
        brand = ticket.values.get('brand', 'N/A')
        model = ticket.values.get('model', 'N/A')
        serial = ticket.values.get('serial', 'N/A')
        companyname = ticket.values.get('company_name', 'Signore/a')

        if not name and not surname:
            customer_name = companyname
        else:
            if name is None:
                name = "Signore/a"
            if surname is None:
                surname = ""
            customer_name = f"{name} {surname}".strip()
        
        email_data['subject'] = f"{customer_name} - Riparazione Completata - Swissbix"
        device_info = f"{brand} {model}".strip()
        
        # Corpo email per riparazione completata
        mailbody = f"""
        <p style="margin:0 0 6px 0;">Gentile {customer_name},</p>
        <p style="margin:0 0 10px 0;">Siamo lieti di informarti che l'intervento tecnico sul tuo dispositivo è stato <strong>completato con successo</strong>.</p>
        <p style="margin:0 0 10px 0;">Il dispositivo è ora pronto per il ritiro.</p>

        <table style="border-collapse:collapse; width:100%; font-size:14px; margin-top: 15px; border: 1px solid #eee;">
            <tr style="background-color: #f9f9f9;"><td style="padding:8px; font-weight:bold; width: 120px;">Dispositivo:</td><td style="padding:8px;">{device_info}</td></tr>
            <tr><td style="padding:8px; font-weight:bold;">Seriale:</td><td style="padding:8px;">{serial}</td></tr>
            <tr style="background-color: #f9f9f9;"><td style="padding:8px; font-weight:bold;">Stato attuale:</td><td style="padding:8px;"><span style="color: #28a745; font-weight: bold;">Riparazione Completata</span></td></tr>
        </table>
        
        <p style="margin:16px 0 0 0;">
            In caso di ritiro presso la nostra sede, i nostri orari rimangono invariati.
        </p>
        <p style="margin:15px 0 0;">Cordiali saluti,</p>
        <p style="margin:0;"><strong>Swissbix SA</strong></p>
        """
        
        email_data['text'] = mailbody
        email_data['cc'] = ""
        email_data['bcc'] = ""
        email_data['attachment_relativepath'] = ""
        email_data['attachment_name'] = ""
        
        # Invio e salvataggio log
        EmailSender.save_email('ticket_lenovo', recordid, email_data)
        
        return JsonResponse({'success': True, 'message': 'Email di riparazione completata inviata'})
