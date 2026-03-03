from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.helper_db import HelpderDB
from commonapp import views

class EventService:
    @staticmethod
    def process_event(recordid: str) -> list:
        event_record = UserRecord('events', recordid)
        
        graph_event_id = event_record.values.get('graph_event_id')
        table = event_record.values.get('tableid')
        subject = event_record.values.get('subject')
        start_date = event_record.values.get('start_date')
        end_date = event_record.values.get('end_date')
        user = event_record.values.get('userid')
        owner = event_record.values.get('owner')
        body_content = event_record.values.get('body_content')
        timezone = event_record.values.get('timezone')

        if not timezone:
            timezone = 'Europe/Zurich'
            event_record.values['timezone'] = timezone

        organizer_email = event_record.values.get('organizer_email')

        categories = []
        if event_record.values.get('categories'):
            categories = event_record.values.get('categories').split(',')

        if table not in categories:
            categories.append(table)
            event_record.values['categories'] = ','.join(categories)
        
        sys_user_details = None
        if user:
            sys_user_details = HelpderDB.sql_query_row(f"SELECT * FROM sys_user WHERE id = {user}")
        
        if not owner and user:
            if sys_user_details and sys_user_details.get('email'):
                owner = sys_user_details['email']
                event_record.values['owner'] = owner

        if not organizer_email and sys_user_details and sys_user_details.get('email'):
            organizer_email = sys_user_details['email']
            event_record.values['organizer_email'] = organizer_email

        if not start_date and end_date:
            start_date = end_date
            event_record.values['start_date'] = start_date

        if not end_date and start_date:
            end_date = start_date
            event_record.values['end_date'] = end_date

        event_data = {
            'graph_event_id': graph_event_id,
            'table': table,
            'subject': subject,
            'start_date': start_date,
            'end_date': end_date,
            'user': user,
            'owner': owner,
            'body_content': body_content,
            'timezone': timezone,
            'organizer_email': organizer_email,
            'categories': categories,
        }

        if graph_event_id:
            result = views.update_event(event_data)
        else:
            result = views.create_event(event_data)

        if not "error" in result:
            event_record.values['graph_event_id'] = result.get('id')
            event_record.values['m365_calendar_id'] = result.get('calendar', {}).get('id')
        else:
            print(result)
        
        event_record.save()
        return []
