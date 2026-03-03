from commonapp.bixmodels.user_record import UserRecord
from commonapp.models import SysUser
from commonapp.utils.email_sender import EmailSender

class TaskService:
    @staticmethod
    def process_task(recordid: str, old_record) -> list:
        """
        Processa i campi di un task: crea l'evento associato,
        gestisce le notifiche per nuova assegnazione o completamento task.
        
        Ritorna una lista di tuple (tableid, recordid) di record collegati
        da salvare a cascata.
        """
        tableid = 'task'
        task = UserRecord(tableid, recordid)
        creator_id = task.values.get('creator')       # creatore
        assigned_to = task.values.get('user')         # assegnato a
        status = task.values.get('status')            # stato attuale

        records_to_save = []

        # 🔹 1) CREA EVENTO
        records_to_save.extend(TaskService._create_event(task, assigned_to))

        # Se non c'è il vecchio record e non è una stringa vuota passata di default
        if not getattr(old_record, 'values', None):
            return records_to_save
        
        # 🔹 2) Check e invio email
        TaskService._handle_notifications(task, old_record, creator_id, assigned_to, status, recordid)

        return records_to_save

    @staticmethod
    def _create_event(task: UserRecord, assigned_to: str) -> list:
        task.userid = assigned_to
        event_record = task.save_record_for_event()
        if event_record and event_record.recordid:
            return [('events', event_record.recordid)]
        return []

    @staticmethod
    def _handle_notifications(task: UserRecord, old_record, creator_id, assigned_to, status, recordid):
        # 🔹 2) Controlla se è cambiato l’assegnatario o solo lo status
        old_user = old_record.values.get('user')
        old_status = old_record.values.get('status')

        # === CASO A: nuovo task assegnato ===
        is_new_assignment = assigned_to != old_user

        # === CASO B: task completato ===
        is_completed = (status == "Chiuso" and old_status != "Chiuso")

        # === Nessun motivo per inviare email ===
        if not is_new_assignment and not is_completed:
            return

        # ---------------------------------------
        #  COSTRUZIONE EMAIL
        # ---------------------------------------
        email_data = {}

        # 🔹 Mittente visibile nella mail
        creator_name = task.fields.get('creator', {}).get('convertedvalue', '')
        company_name = task.fields.get('recordidcompany_', {}).get('convertedvalue', '')

        # === A) NUOVA ASSEGNAZIONE ===
        if is_new_assignment:
            recipient_id = assigned_to
            subject = f"Nuovo task assegnato da {creator_name} - {company_name}"

        # === B) TASK COMPLETATO ===
        else:
            recipient_id = creator_id
            finisher_name = task.fields.get('user', {}).get('convertedvalue', '')
            subject = f"{finisher_name} - {company_name} ha completato un task."

        if not recipient_id:
            return

        # 🔹 RECIPIENT EMAIL
        email_data["to"] = SysUser.objects.filter(id=recipient_id).values_list("email", flat=True).first()

        # Selettore senza mail skip
        if not email_data["to"]:
            return

        # 🔹 SUBJECT
        email_data["subject"] = subject

        # -----------------------------------------------------
        #   MAIL BODY GENERATO AUTOMATICAMENTE
        # -----------------------------------------------------
        TaskService._build_email_data(task, email_data)

        # 🔹 INVIO
        EmailSender.save_email('task', recordid, email_data)

    @staticmethod
    def _build_email_data(task: UserRecord, email_data: dict):
        descrizione = task.values.get("description", "")
        scadenza = task.values.get("duedate", "")
        datapianificata = task.values.get("planneddate", "")
        durata = task.values.get("duration", "")
        note = task.values.get("note", "")
        stato = task.values.get("status", "")

        # corpo email
        mailbody = f"""
        <p style="margin:0 0 6px 0;">Ciao,</p>
        <p style="margin:0 0 10px 0;">Ecco i dettagli del task:</p>

        <table style="border-collapse:collapse; width:100%; font-size:14px;">
            <tr><td style="padding:4px 0; font-weight:bold;">Descrizione:</td><td>{descrizione}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Scadenza:</td><td>{scadenza}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Data pianificata:</td><td>{datapianificata}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Durata prevista:</td><td>{durata}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Stato:</td><td>{stato}</td></tr>
        </table>
        """

        if note:
            mailbody += f"""
            <p style="margin:14px 0 6px 0;"><strong>Note:</strong></p>
            <div style="padding:8px; background:#f7f7f7; border-radius:6px;">
                {note}
            </div>
            """

        link_web = "https://bixportal.dc.swissbix.ch/home"

        mailbody += f"""
        <p style="margin:16px 0 0 0;">
            Puoi vedere maggiori dettagli accedendo alla piattaforma:
            <a href="{link_web}">{link_web}</a>
        </p>
        <p style="margin:0;">Cordiali saluti,</p>
        <p style="margin:0;">Il team</p>
        """

        email_data["text"] = mailbody

        # 🔹 Nessuna copia
        email_data["cc"] = ""
        email_data["bcc"] = ""

        # 🔹 Nessun allegato
        email_data["attachment_relativepath"] = ""
        email_data["attachment_name"] = ""
