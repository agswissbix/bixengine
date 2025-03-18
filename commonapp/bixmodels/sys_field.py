from django.contrib.sessions.models import Session


from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.core.mail import send_mail, BadHeaderError, EmailMessage
from django.http import HttpResponse
from django.template.loader import render_to_string
import requests
import json
import datetime
from django.contrib.auth.decorators import login_required
import time
import os
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db import connection, connections
from django.http import JsonResponse
from django.contrib.auth.models import Group, Permission, User, Group
from django_user_agents.utils import get_user_agent
#from bixdata_app.models import MyModel
from django import template
from bs4 import BeautifulSoup
from django.db.models import OuterRef, Subquery
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *

bixdata_server = os.environ.get('BIXDATA_SERVER')

class SysField:
    
    def __init__(self,fieldid,value='',userid=1):
        self.fieldid=fieldid
        self.userid=userid
        self.value=value
        self.columns=dict()

    def get_value_converted(self):
        if self.columns['typeField']=='date':
            return self.value.strftime('%Y-%m-%d')
        return self.value
