from datetime import date, datetime
import os
import pprint
import subprocess
from django.http import HttpResponse, JsonResponse
from django_q.models import Schedule, Task
from django.db import connection
import psutil, shutil

import requests
from commonapp.bixmodels.user_record import UserRecord
from commonapp.utils.email_sender import EmailSender
from commonapp.bixmodels.helper_db import *
from commonapp.bixmodels.user_table import *
from customapp_swissbix.customfunc import *
from django.conf import settings
from commonapp.bixmodels.helper_db import HelpderDB
import xml.etree.ElementTree as ET
import json
from django.http import JsonResponse
from bixscheduler.decorators.safe_schedule_task import safe_schedule_task

import pyodbc
from cryptography.fernet import Fernet, InvalidToken

from commonapp import views

   
def sync_notifications(request):
    print("Sync notifications")

    notification_table = UserTable("notification")
    notifications = notification_table.get_records(conditions_list=[])

    for notification in notifications:
        notification_id = notification.get('recordid_')

        create_notification(notification_id)

    return HttpResponse()


def create_notification(notification_id):
    print("Creating notification")
    try:
        notification_status_table = UserTable("notification_status")
        condition_list = [
            f"recordidnotification_={notification_id}"
        ]

        notification_statuses = notification_status_table.get_records(conditions_list=condition_list)

        clubs_table = UserTable("golfclub")
        clubs = clubs_table.get_records(conditions_list=[])

        for club in clubs:
            print("club")
            
            found_status = next(
                (s for s in notification_statuses if str(s.get('recordidgolfclub_')) == str(club.get('recordid_'))),
                None
            )

            if not found_status:
                new_notification = UserRecord("notification_status")
                new_notification.values["recordidnotification_"] = notification_id
                new_notification.values["recordidgolfclub_"] = club.get("recordid_")
                new_notification.values["status"] = "Unread"
                new_notification.save()

    except:
        print("Error creating notification statuses")