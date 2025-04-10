import json
import datetime
from django.contrib.auth.decorators import login_required
import time
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db import connection, connections
from django.http import JsonResponse
from django.contrib.auth.models import Group, Permission, User, Group
from django_user_agents.utils import get_user_agent
from django import template
from bs4 import BeautifulSoup
from django.db.models import OuterRef, Subquery
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *


class HelperSys:

    @classmethod     
    def get_users(cls):
        sql="SELECT id, username, firstname, lastname, email FROM sys_user"
        users = HelpderDB.sql_query(sql)
        return users
    