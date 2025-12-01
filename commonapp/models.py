# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.contrib.auth.models import User
import pyotp
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import F, OuterRef, Subquery


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.IntegerField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)  # Relazione 1:1 con User
    otp_secret = models.CharField(max_length=32, default=pyotp.random_base32)  # Secret per OTP
    is_2fa_enabled = models.BooleanField(default=False)  # Flag per attivare/disattivare 2FA

    def generate_otp(self):
        """Genera un codice OTP basato sulla secret key dell'utente"""
        return pyotp.TOTP(self.otp_secret).now()

    def verify_otp(self, otp_code):
        """Verifica se un codice OTP è corretto"""
        totp = pyotp.TOTP(self.otp_secret)
        return totp.verify(otp_code)
    

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)  # Crea UserProfile automaticamente

from django.db import models

class SysAlert(models.Model):
    tableid = models.ForeignKey('SysTable', models.DO_NOTHING, db_column='tableid', blank=True, null=True)
    alert_condition = models.TextField(blank=True, null=True)
    alert_type = models.CharField(max_length=255, blank=True, null=True)
    alert_param = models.TextField(blank=True, null=True)
    alert_user = models.CharField(max_length=255, blank=True, null=True)
    alert_description = models.CharField(max_length=255, blank=True, null=True)
    alert_fieldstocheck = models.CharField(max_length=255, blank=True, null=True)
    alert_viewid = models.CharField(max_length=255, blank=True, null=True)
    alert_order = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    alert_status = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_alert'


class SysAutobatch(models.Model):
    id = models.CharField(primary_key=True, max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)
    path = models.CharField(max_length=255)
    tableid = models.CharField(max_length=32, blank=True, null=True)
    crypted = models.CharField(max_length=1)
    numfiles = models.IntegerField()
    lastfileposition = models.IntegerField()
    locked = models.CharField(max_length=1)
    creatorid = models.IntegerField(blank=True, null=True)
    creationdate = models.DateTimeField()
    originalpath = models.CharField(max_length=255, blank=True, null=True)
    split = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'sys_autobatch'


class SysAutobatchFile(models.Model):
    fileid = models.AutoField(primary_key=True)
    batchid = models.CharField(max_length=255)
    filename = models.CharField(max_length=255)
    fileext = models.CharField(max_length=6)
    description = models.CharField(max_length=255, blank=True, null=True)
    fileposition = models.IntegerField()
    crypted = models.CharField(max_length=1)
    creatorid = models.IntegerField(blank=True, null=True)
    creationdate = models.DateTimeField()
    ocr = models.TextField(blank=True, null=True)
    thumbnail = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_autobatch_file'
        unique_together = (('batchid', 'filename'),)


class SysBatch(models.Model):
    id = models.CharField(primary_key=True, max_length=32)
    description = models.CharField(max_length=255, blank=True, null=True)
    path = models.CharField(max_length=255)
    tableid = models.CharField(max_length=32, blank=True, null=True)
    crypted = models.CharField(max_length=1)
    numfiles = models.IntegerField()
    lastfileposition = models.IntegerField()
    locked = models.CharField(max_length=1)
    creatorid = models.IntegerField(blank=True, null=True)
    creationdate = models.DateTimeField()

    class Meta:
        db_table = 'sys_batch'


class SysBatchFile(models.Model):
    fileid = models.AutoField(primary_key=True)
    batchid = models.CharField(max_length=32)
    filename = models.CharField(max_length=32)
    fileext = models.CharField(max_length=6)
    description = models.CharField(max_length=255, blank=True, null=True)
    fileposition = models.IntegerField()
    crypted = models.CharField(max_length=1)
    creatorid = models.IntegerField(blank=True, null=True)
    creationdate = models.DateTimeField()
    ocr = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'sys_batch_file'
        unique_together = (('batchid', 'filename'),)


class SysCalendar(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    userid = models.ForeignKey('SysUser', models.DO_NOTHING, db_column='userid', blank=True, null=True)
    tableid = models.ForeignKey('SysTable', models.DO_NOTHING, db_column='tableid', blank=True, null=True)
    field_data = models.CharField(max_length=255, blank=True, null=True)
    field_orainizio = models.CharField(max_length=255, blank=True, null=True)
    field_orafine = models.CharField(max_length=255, blank=True, null=True)
    field_titolo = models.CharField(max_length=255, blank=True, null=True)
    field_descrizione = models.CharField(max_length=255, blank=True, null=True)
    sync_condition = models.TextField(blank=True, null=True)
    sync = models.IntegerField(blank=True, null=True)
    userid_tosync = models.CharField(max_length=255, blank=True, null=True)
    field_useridtosync = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_calendar'


class SysDashboard(models.Model):
    userid = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    order_dashboard = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_dashboard'


class SysDashboardBlock(models.Model):
    dashboardid = models.ForeignKey(SysDashboard, models.DO_NOTHING, db_column='dashboardid', blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    userid = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    viewid = models.ForeignKey('SysView', models.DO_NOTHING, db_column='viewid', blank=True, null=True)
    reportid = models.ForeignKey('SysReport', models.DO_NOTHING, db_column='reportid', blank=True, null=True)
    widgetid = models.IntegerField(blank=True, null=True)
    calendarid = models.ForeignKey(SysCalendar, models.DO_NOTHING, db_column='calendarid', blank=True, null=True)
    chartid = models.ForeignKey('SysChart', models.DO_NOTHING, db_column='chartid', blank=True, null=True)
    width = models.CharField(max_length=255, blank=True, null=True)
    height = models.CharField(max_length=255, blank=True, null=True)
    order = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)
    gsx = models.IntegerField(blank=True, null=True)
    gsy = models.IntegerField(blank=True, null=True)
    gsw = models.IntegerField(blank=True, null=True)
    gsh = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'sys_dashboard_block'


class SysField(models.Model):
    tableid = models.CharField(max_length=255)
    fieldid = models.CharField(max_length=255)
    sync_fieldid = models.CharField(max_length=255, blank=True, null=True)
    master_field = models.CharField(max_length=255, blank=True, null=True)
    linked_field = models.CharField(max_length=255, blank=True, null=True)
    fieldtypeid = models.CharField(max_length=16)
    length = models.IntegerField(blank=True, null=True)
    decimalposition = models.IntegerField(blank=True, null=True)
    description = models.CharField(max_length=100, blank=True, null=True)
    fieldorder = models.IntegerField(blank=True, null=True)
    lookuptableid = models.CharField(max_length=255, blank=True, null=True)
    lookupcodedesc = models.CharField(max_length=1, blank=True, null=True)
    lookupdesclen = models.IntegerField(blank=True, null=True)
    label = models.CharField(max_length=32)
    tablelink = models.CharField(max_length=32, blank=True, null=True)
    keyfieldlink = models.CharField(max_length=128, blank=True, null=True)
    default = models.CharField(max_length=255, blank=True, null=True)
    sublabel = models.CharField(max_length=255, blank=True, null=True)
    showedbyvalue = models.CharField(max_length=255, blank=True, null=True)
    showedbyfieldid = models.CharField(max_length=255, blank=True, null=True)
    fieldtypewebid = models.CharField(max_length=255, blank=True, null=True)
    linkfieldid = models.CharField(max_length=255, blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'sys_field'


class SysGroup(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    idmanager = models.ForeignKey('SysUser', models.DO_NOTHING, db_column='idmanager', blank=True, null=True)
    creatorid = models.IntegerField(blank=True, null=True)
    creationdate = models.DateTimeField()
    disabled = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        db_table = 'sys_group'


class SysGroupUser(models.Model):
    groupid = models.IntegerField(primary_key=True)  # The composite primary key (groupid, userid) found, that is not supported. The first column is selected.
    userid = models.ForeignKey('SysUser', models.DO_NOTHING, db_column='userid')
    disabled = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        db_table = 'sys_group_user'
        unique_together = (('groupid', 'userid'),)


class SysLog(models.Model):
    date = models.DateField()
    time = models.TimeField()
    ip = models.CharField(max_length=30)
    pcname = models.CharField(max_length=30, blank=True, null=True)
    username = models.CharField(max_length=30)
    tableid = models.CharField(max_length=30, blank=True, null=True)
    operationid = models.CharField(max_length=50)
    description = models.CharField(max_length=255, blank=True, null=True)
    recordid = models.CharField(max_length=32, blank=True, null=True)
    pageid = models.CharField(max_length=32, blank=True, null=True)
    oldrecordid = models.CharField(max_length=32, blank=True, null=True)
    oldpageid = models.CharField(max_length=32, blank=True, null=True)
    sql = models.TextField(blank=True, null=True)
    threadserverid = models.BigIntegerField(blank=True, null=True)

    class Meta:
        db_table = 'sys_log'


class SysLogquery(models.Model):
    userid = models.IntegerField(blank=True, null=True)
    funzione = models.CharField(max_length=32, blank=True, null=True)
    timestamp = models.DateTimeField(blank=True, null=True)
    post = models.TextField(blank=True, null=True)
    query = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'sys_logquery'


class SysLookupTable(models.Model):
    description = models.CharField(max_length=255, blank=True, null=True)
    tableid = models.CharField(unique=True, max_length=255, blank=True, null=True)
    itemtype = models.CharField(max_length=255, blank=True, null=True)
    codelen = models.IntegerField(blank=True, null=True)
    desclen = models.IntegerField(blank=True, null=True)
    numitems = models.IntegerField(blank=True, null=True)
    linkfieldid = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_lookup_table'


class SysLookupTableItem(models.Model):
    lookuptableid = models.CharField(primary_key=True, max_length=255)  # The composite primary key (lookuptableid, itemcode) found, that is not supported. The first column is selected.
    itemcode = models.CharField(max_length=255)
    itemdesc = models.CharField(max_length=255, blank=True, null=True)
    linkvalue = models.CharField(max_length=255, blank=True, null=True)
    hidden = models.IntegerField(blank=True, null=True)
    itemorder = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'sys_lookup_table_item'
        unique_together = (('lookuptableid', 'itemcode'),)


class SysReport(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    userid = models.CharField(max_length=255, blank=True, null=True)
    tableid = models.CharField(max_length=255, blank=True, null=True)
    fieldid = models.CharField(max_length=255, blank=True, null=True)
    operation = models.CharField(max_length=255, blank=True, null=True)
    groupby = models.CharField(max_length=255, blank=True, null=True)
    layout = models.CharField(max_length=255, blank=True, null=True)
    order = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    custom = models.TextField(blank=True, null=True)
    select_fields = models.CharField(max_length=255, blank=True, null=True)
    groupby_fields = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_report'


class SysReportViews(models.Model):
    reportid = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    viewid = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    reportorder = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)

    class Meta:
        db_table = 'sys_report_views'


class SysSchedulerLog(models.Model):
    dataora = models.DateTimeField(blank=True, null=True)
    funzione = models.CharField(max_length=255, blank=True, null=True)
    output = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'sys_scheduler_log'


class SysSchedulerTasks(models.Model):
    funzione = models.CharField(max_length=255, blank=True, null=True)
    intervallo = models.IntegerField(blank=True, null=True)
    limite = models.IntegerField(blank=True, null=True)
    inizio = models.DateTimeField(blank=True, null=True)
    fine = models.TimeField(blank=True, null=True)
    counter = models.IntegerField(blank=True, null=True)
    counter_limit = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=255, blank=True, null=True)
    active = models.IntegerField(blank=True, null=True)
    hours = models.CharField(max_length=255, blank=True, null=True)
    minutes = models.CharField(max_length=255, blank=True, null=True)
    days = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_scheduler_tasks'


class SysSettings(models.Model):
    id = models.IntegerField(primary_key=True)
    setting = models.CharField(max_length=50)
    value = models.CharField(max_length=50)
    description = models.CharField(max_length=60, blank=True, null=True)

    class Meta:
        db_table = 'sys_settings'


class SysTable(models.Model):
    id = models.CharField(primary_key=True, max_length=32)
    description = models.CharField(max_length=255, blank=True, null=True)
    sync_service = models.CharField(max_length=255, blank=True, null=True)
    sync_table = models.CharField(max_length=255, blank=True, null=True)
    sync_field = models.CharField(max_length=255, blank=True, null=True)
    sync_condition = models.CharField(max_length=255, blank=True, null=True)
    sync_order = models.CharField(max_length=255, blank=True, null=True)
    sync_type = models.CharField(max_length=50, blank=True, null=True)
    creatorid = models.IntegerField(blank=True, null=True)
    creationdate = models.DateTimeField()
    tabletypeid = models.IntegerField()
    dbtypeid = models.IntegerField()
    password = models.CharField(max_length=50, blank=True, null=True)
    lastrecordid = models.CharField(max_length=32, blank=True, null=True)
    lastpageid = models.CharField(max_length=32, blank=True, null=True)
    totpages = models.BigIntegerField(blank=True, null=True)
    namefolder = models.CharField(max_length=5)
    numfilesfolder = models.IntegerField()
    mediaid = models.CharField(max_length=32, blank=True, null=True)
    lastupdate = models.CharField(max_length=14, blank=True, null=True)
    workspace = models.CharField(max_length=256, blank=True, null=True)
    workspaceorder = models.IntegerField(blank=True, null=True)
    tableorder = models.IntegerField(blank=True, null=True)
    singular_name = models.CharField(max_length=255, blank=True, null=True)
    plural_name = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_table'

    @classmethod
    def get_user_tables(cls, userid):
    # Subquery per prendere info dal workspace in base al nome
        workspace_qs = SysTableWorkspace.objects.filter(name=OuterRef('workspace'))

        rows = (
            cls.objects
            .filter(sysusertableorder__userid=userid)
            .annotate(
                workspace_order=Subquery(workspace_qs.values('order')[:1]),
                workspace_icon=Subquery(workspace_qs.values('icon')[:1]),
                table_order=F('sysusertableorder__tableorder'),
            )
            .values(
                'id',
                'description',
                'workspace',
                'workspace_order',
                'workspace_icon',
                'sysusertableorder__userid',
                'table_order',
            )
            .order_by('workspace_order', 'table_order', 'id')
        )
        return rows

class SysTableFeature(models.Model):
    tableid = models.CharField(primary_key=True, max_length=32)  # The composite primary key (tableid, featureid) found, that is not supported. The first column is selected.
    featureid = models.IntegerField()
    enabled = models.CharField(max_length=1)

    class Meta:
        db_table = 'sys_table_feature'
        unique_together = (('tableid', 'featureid'),)


class SysTableLabel(models.Model):
    tableid = models.CharField(primary_key=True, max_length=32)  # The composite primary key (tableid, labelname) found, that is not supported. The first column is selected.
    labelname = models.CharField(max_length=32)
    labelorder = models.SmallIntegerField(blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_table_label'
        unique_together = (('tableid', 'labelname'),)


class SysTableLink(models.Model):
    tableid = models.OneToOneField(SysTable, models.DO_NOTHING, db_column='tableid', primary_key=True)  # The composite primary key (tableid, tablelinkid) found, that is not supported. The first column is selected.
    tablelinkid = models.ForeignKey(SysTable, models.DO_NOTHING, db_column='tablelinkid', related_name='systablelink_tablelinkid_set')

    class Meta:
        db_table = 'sys_table_link'
        unique_together = (('tableid', 'tablelinkid'),)


class SysTableSettings(models.Model):
    tableid = models.ForeignKey(SysTable, models.DO_NOTHING, db_column='tableid', blank=True, null=True)
    settingid = models.CharField(max_length=255, blank=True, null=True)
    value = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_table_settings'


class SysTableSublabel(models.Model):
    tableid = models.CharField(primary_key=True, max_length=32)  # The composite primary key (tableid, sublabelname) found, that is not supported. The first column is selected.
    sublabelname = models.CharField(max_length=32)
    sublabelorder = models.SmallIntegerField(blank=True, null=True)
    showedbytableid = models.CharField(max_length=255, blank=True, null=True)
    showedbyfieldid = models.CharField(max_length=255, blank=True, null=True)
    showedbyvalue = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_table_sublabel'
        unique_together = (('tableid', 'sublabelname'),)


class SysTableWorkspace(models.Model):
    workspaceid = models.AutoField(primary_key=True)
    userid = models.ForeignKey('SysUser', models.DO_NOTHING, db_column='userid', blank=True, null=True)
    name = models.CharField(max_length=50, blank=True, null=True)
    icon = models.CharField(max_length=1000, blank=True, null=True)
    order = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'sys_table_workspace'


class SysUser(models.Model):
    id = models.IntegerField(primary_key=True)
    firstname = models.CharField(max_length=50, blank=True, null=True)
    lastname = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    username = models.CharField(max_length=25)
    password = models.CharField(max_length=25)
    email = models.CharField(max_length=100, blank=True, null=True)
    creatorid = models.IntegerField(blank=True, null=True)
    creationdate = models.DateTimeField()
    disabled = models.CharField(max_length=1, blank=True, null=True)
    superuser = models.CharField(max_length=1, blank=True, null=True)
    folder = models.CharField(max_length=128, blank=True, null=True)
    folder_serverside = models.CharField(max_length=256, blank=True, null=True)
    enablesendmail = models.IntegerField(blank=True, null=True)
    bixid = models.IntegerField(blank=True, null=True)
    hubspot_dealuser = models.CharField(max_length=50, blank=True, null=True)
    adiutoid = models.IntegerField(blank=True, null=True)
    lock_recordid = models.CharField(max_length=45, blank=True, null=True)
    lock_tableid = models.CharField(max_length=45, blank=True, null=True)
    lock_time = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = 'sys_user'


class SysUserColumnWidth(models.Model):
    tableid = models.CharField(max_length=50, blank=True, null=True)
    userid = models.IntegerField(blank=True, null=True)
    column_width = models.CharField(max_length=1000, blank=True, null=True)

    class Meta:
        db_table = 'sys_user_column_width'


class SysUserDashboard(models.Model):
    userid = models.ForeignKey(SysUser, models.DO_NOTHING, db_column='userid', blank=True, null=True)
    dashboardid = models.ForeignKey(SysDashboard, models.DO_NOTHING, db_column='dashboardid', blank=True, null=True)
    height = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    width = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    order = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    position = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'sys_user_dashboard'


class SysUserDashboardBlock(models.Model):
    userid = models.ForeignKey(SysUser, models.DO_NOTHING, db_column='userid', blank=True, null=True)
    dashboard_block = models.ForeignKey(SysDashboardBlock, models.DO_NOTHING, blank=True, null=True)
    dashboardid = models.ForeignKey(SysDashboard, models.DO_NOTHING, db_column='dashboardid', blank=True, null=True)
    gsx = models.IntegerField(blank=True, null=True)
    gsy = models.IntegerField(blank=True, null=True)
    gsw = models.IntegerField(blank=True, null=True)
    gsh = models.IntegerField(blank=True, null=True)
    size = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = 'sys_user_dashboard_block'


class SysUserDefaultView(models.Model):
    userid = models.ForeignKey(SysUser, models.DO_NOTHING, db_column='userid', blank=True, null=True)
    tableid = models.ForeignKey(SysTable, models.DO_NOTHING, db_column='tableid', blank=True, null=True)
    viewid = models.ForeignKey('SysView', models.DO_NOTHING, db_column='viewid', blank=True, null=True)

    class Meta:
        db_table = 'sys_user_default_view'


class SysUserFavoriteTables(models.Model):
    sys_user_id = models.IntegerField(blank=True, null=True)
    tableid = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = 'sys_user_favorite_tables'


class SysUserFieldOrder(models.Model):
    userid = models.ForeignKey(SysUser, models.DO_NOTHING, db_column='userid', blank=True, null=True)
    tableid = models.ForeignKey(SysTable, models.DO_NOTHING, db_column='tableid', blank=True, null=True)
    fieldid = models.ForeignKey(SysField, models.DO_NOTHING, db_column='fieldid', blank=True, null=True)
    fieldorder = models.IntegerField(blank=True, null=True)
    typepreference = models.CharField(max_length=32, blank=True, null=True)
    master_tableid = models.ForeignKey(SysTable, models.DO_NOTHING, db_column='master_tableid', related_name='sysuserfieldorder_master_tableid_set', blank=True, null=True)
    step = models.ForeignKey('SysStep', on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        db_table = 'sys_user_field_order'


class SysUserFieldSettings(models.Model):
    userid = models.ForeignKey(SysUser, models.DO_NOTHING, db_column='userid', blank=True, null=True)
    tableid = models.CharField(max_length=255, blank=True, null=True)
    fieldid = models.CharField(max_length=32, blank=True, null=True)
    settingid = models.CharField(max_length=255, blank=True, null=True)
    value = models.CharField(max_length=255, blank=True, null=True)
    context = models.CharField(max_length=50, blank=True, null=True)
    order = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'sys_user_field_settings'


class SysUserOrder(models.Model):
    userid = models.ForeignKey(SysUser, models.DO_NOTHING, db_column='userid', blank=True, null=True)
    tableid = models.ForeignKey(SysTable, models.DO_NOTHING, db_column='tableid', blank=True, null=True)
    fieldid = models.CharField(max_length=32, blank=True, null=True)
    fieldorder = models.IntegerField(blank=True, null=True)
    typepreference = models.CharField(max_length=32, blank=True, null=True)
    step = models.ForeignKey('SysStep', on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        db_table = 'sys_user_order'


class SysUserPermission(models.Model):
    userid = models.IntegerField(primary_key=True)  # The composite primary key (userid, permissionid) found, that is not supported. The first column is selected.
    permissionid = models.IntegerField()
    enabled = models.CharField(max_length=1)

    class Meta:
        db_table = 'sys_user_permission'
        unique_together = (('userid', 'permissionid'),)


class SysUserPreferenceIndexTable(models.Model):
    userid = models.IntegerField(blank=True, null=True)
    tableid = models.CharField(max_length=32, blank=True, null=True)
    indexid = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        db_table = 'sys_user_preference_index_table'


class SysUserPreferencesLayout(models.Model):
    userid = models.IntegerField(blank=True, null=True)
    typepreference = models.CharField(max_length=32, blank=True, null=True)
    dashboard = models.CharField(max_length=32, blank=True, null=True)
    dati = models.CharField(max_length=32, blank=True, null=True)
    allegati = models.CharField(max_length=32, blank=True, null=True)
    tema = models.CharField(max_length=32, blank=True, null=True)

    class Meta:
        db_table = 'sys_user_preferences_layout'


class SysUserSchedesalvate(models.Model):
    tableid = models.CharField(max_length=32, blank=True, null=True)
    recordid = models.CharField(max_length=32, blank=True, null=True)
    userid = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'sys_user_schedesalvate'


class SysUserSettings(models.Model):
    userid = models.ForeignKey(SysUser, models.DO_NOTHING, db_column='userid', blank=True, null=True)
    setting = models.CharField(max_length=255, blank=True, null=True)
    value = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_user_settings'


class SysUserTableDefaultvalue(models.Model):
    userid = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    tableid = models.CharField(max_length=255, blank=True, null=True)
    fieldid = models.CharField(max_length=255, blank=True, null=True)
    origintableid = models.CharField(max_length=255, blank=True, null=True)
    custom_param = models.CharField(max_length=255, blank=True, null=True)
    defaultvalue = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_user_table_defaultvalue'


class SysUserTableOrder(models.Model):
    userid = models.ForeignKey(SysUser, models.DO_NOTHING, db_column='userid', blank=True, null=True)
    tableid = models.ForeignKey(SysTable, models.DO_NOTHING, db_column='tableid', blank=True, null=True)
    tableorder = models.IntegerField(blank=True, null=True)
    typepreference = models.CharField(max_length=255, blank=True, null=True)
    master_tableid = models.ForeignKey(SysTable, models.DO_NOTHING, db_column='master_tableid', related_name='sysusertableorder_master_tableid_set', blank=True, null=True)

    class Meta:
        db_table = 'sys_user_table_order'


class SysUserTableSearchField(models.Model):
    userid = models.IntegerField(primary_key=True)  # The composite primary key (userid, tableid, fieldid) found, that is not supported. The first column is selected.
    tableid = models.CharField(max_length=32)
    linkedtableid = models.CharField(max_length=50, blank=True, null=True)
    linkedmastetableid = models.CharField(max_length=50, blank=True, null=True)
    fieldid = models.CharField(max_length=32)
    fieldorder = models.IntegerField()

    class Meta:
        db_table = 'sys_user_table_search_field'
        unique_together = (('userid', 'tableid', 'fieldid'),)


class SysUserTableSettings(models.Model):
    userid = models.ForeignKey(SysUser, models.DO_NOTHING, db_column='userid', blank=True, null=True)
    tableid = models.ForeignKey(SysTable, models.DO_NOTHING, db_column='tableid', blank=True, null=True)
    settingid = models.CharField(max_length=255, blank=True, null=True)
    value = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_user_table_settings'


class SysView(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    userid = models.ForeignKey(SysUser, models.DO_NOTHING, db_column='userid', blank=True, null=True)
    tableid = models.ForeignKey(SysTable, models.DO_NOTHING, db_column='tableid', blank=True, null=True)
    post = models.TextField(blank=True, null=True)
    creation = models.DateTimeField(blank=True, null=True)
    query_conditions = models.TextField(blank=True, null=True)
    order_field = models.CharField(max_length=255, blank=True, null=True)
    order_ascdesc = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'sys_view'


class SysViewReport(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    viewsql = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'sys_view_report'


class SysWidget(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = 'sys_widget'


class SysCustomFunction(models.Model):
    CONTEXT_CHOICES = [
        ("results", "Results"),
        ("card", "Card"),
    ]

    tableid = models.ForeignKey('SysTable', models.DO_NOTHING, db_column='tableid', blank=True, null=True)
    context = models.CharField(max_length=20, choices=CONTEXT_CHOICES)
    title = models.CharField(max_length=255)
    function = models.CharField(max_length=100)
    params = models.CharField(max_length=100, null=True, blank=True)
    conditions = models.JSONField(blank=True, null=True)
    order = models.IntegerField(blank=True, null=True)
    css = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "sys_custom_function"
        verbose_name = "Custom Function"
        verbose_name_plural = "Custom Functions"

    def __str__(self):
        return f"{self.title} ({self.tableid})"


class SysChart(models.Model):
    name = models.CharField(max_length=255)
    userid = models.ForeignKey(
        SysUser,
        on_delete=models.CASCADE,
        db_column="userid",
    )
    layout = models.CharField(max_length=100)
    config = models.JSONField()
    colors = models.CharField(max_length=255, blank=True, null=True)
    function_button = models.ForeignKey('SysCustomFunction', models.DO_NOTHING, db_column='function_button', blank=True, null=True)

    class Meta:
        db_table = "sys_chart"
        verbose_name = "Grafico"
        verbose_name_plural = "Grafici"

    def __str__(self):
        return f"{self.name} ({self.layout})"



class SysStep(models.Model):
    STEP_TYPES = [
        ('campi', 'Campi'),
        ('allegati', 'Allegati'),
        ('collegate', 'Tabelle collegate'),
        ('aggiuntivi', 'Campi aggiuntivi'),
    ]

    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=50, choices=STEP_TYPES, blank=True, null=True)

    tables = models.ManyToManyField(
        SysTable,
        through='SysStepTable',
        related_name='steps'
    )

    class Meta:
        db_table = 'sys_steps'
        verbose_name = 'Step di sistema'
        verbose_name_plural = 'Steps di sistema'

    def __str__(self):
        return self.name
    
    def get_table_order(self, table_name):
        rel = self.tables.through.objects.filter(step=self, table__name=table_name).first()
        return rel.order if rel else None


class SysStepTable(models.Model):
    step = models.ForeignKey(SysStep, on_delete=models.CASCADE)
    table = models.ForeignKey(SysTable, on_delete=models.CASCADE)
    user = models.ForeignKey(SysUser, on_delete=models.CASCADE, default=1)
    order = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'sys_steps_tables'
        verbose_name = 'Associazione Step-Tabella'
        verbose_name_plural = 'Associazioni Step-Tabella'
        unique_together = ('step', 'table', 'user')
        ordering = ['order']

    def __str__(self):
        return f"{self.table.name} - {self.step.name} (ordine: {self.order})"
    

# ------------------- Users Tables ------------------- #
class BaseUserTable(models.Model):
    record_id = models.CharField(
        max_length=32,
        primary_key=True,
        db_column='recordid_'
    )
    creator_id = models.IntegerField(
        null=True,
        blank=True,
        db_column='creatorid_'
    )
    created_at = models.DateTimeField(
        null=True,
        blank=True,
        db_column='creation_'
    )
    last_updater_id = models.IntegerField(
        null=True,
        blank=True,
        db_column='lastupdaterid_'
    )
    last_update = models.DateTimeField(
        null=True,
        blank=True,
        db_column='lastupdate_'
    )
    total_pages = models.IntegerField(
        null=True,
        blank=True,
        db_column='totpages_'
    )
    first_page_filename = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='firstpagefilename_'
    )
    record_status = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='recordstatus_'
    )
    deleted_flag = models.CharField(
        max_length=1,
        default='N',
        db_default='N',
        db_column='deleted_'
    )
    id = models.IntegerField(null=True, blank=True)

    class Meta:
        abstract = True   # 👈 Non crea tabella fisica


class UserChart(BaseUserTable):
    name = models.CharField(max_length=255, null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    type = models.CharField(max_length=255, null=True, blank=True)
    fields = models.CharField(max_length=255, null=True, blank=True)
    dynamic_field_1 = models.CharField(max_length=255, null=True, blank=True)
    dynamic_field_1_label = models.CharField(max_length=255, null=True, blank=True)
    operation = models.CharField(max_length=255, null=True, blank=True)
    grouping = models.CharField(max_length=255, null=True, blank=True)
    grouping_type = models.CharField(max_length=255, null=True, blank=True)
    pivot_total_field = models.CharField(max_length=255, null=True, blank=True)
    fields_2 = models.CharField(max_length=255, null=True, blank=True)
    dynamic_field_2 = models.CharField(max_length=255, null=True, blank=True)
    dynamic_field_2_label = models.CharField(max_length=255, null=True, blank=True)
    operation2 = models.CharField(max_length=255, null=True, blank=True)
    operation2_total = models.CharField(max_length=255, null=True, blank=True)
    icon = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=255, null=True, blank=True)
    report_id = models.CharField(max_length=255, null=True, blank=True)
    table_name = models.CharField(max_length=255, null=True, blank=True)
    dashboards = models.CharField(max_length=255, null=True, blank=True)
    category_dashboard = models.CharField(max_length=255, null=True, blank=True)
    views = models.CharField(max_length=255, null=True, blank=True)
    date_granularity = models.CharField(max_length=255, null=True, blank=True)
    function_button = models.ForeignKey('SysCustomFunction', models.DO_NOTHING, db_column='function_button', null=True, blank=True)
    colors = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'user_chart'
        verbose_name_plural = 'Grafici'


    def __str__(self):
        return self.name or self.title or str(self.recordid_)
    

class UserEmail(BaseUserTable):
    subject = models.CharField(max_length=255, null=True, blank=True)
    recipients = models.CharField(max_length=255, null=True, blank=True)
    mailbody = models.TextField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    sent_timestamp = models.CharField(max_length=255, null=True, blank=True)
    cc = models.CharField(max_length=255, null=True, blank=True)
    ccn = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=255, null=True, blank=True)
    attachment = models.CharField(max_length=255, null=True, blank=True)
    attachment_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'user_email'
        verbose_name_plural = 'Email'

    

class UserSchedulerLog(BaseUserTable):
    date = models.DateField(null=True, blank=True)
    hour = models.CharField(max_length=255, null=True, blank=True)
    function = models.CharField(max_length=255, null=True, blank=True)
    output = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'user_scheduler_log'
        verbose_name_plural = 'Log scheduler'



class UserSystemLog(BaseUserTable):
    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    function = models.CharField(max_length=255, null=True, blank=True)
    output = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'user_system_log'
        verbose_name_plural = 'Log sistema'



class UserUserLog(BaseUserTable):
    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    user = models.ForeignKey(SysUser, models.DO_NOTHING, null=True, blank=True)
    function = models.CharField(max_length=255, null=True, blank=True)
    output = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'user_user_log'
        verbose_name_plural = 'Log utente'


class UserAttachment(BaseUserTable):
    type = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    file = models.CharField(max_length=255, null=True, blank=True)
    filename = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'user_attachment'
        verbose_name_plural = 'Allegati'

class UserEvents(BaseUserTable):
    tableid = models.ForeignKey(SysTable, models.DO_NOTHING, null=True, blank=True, db_column='tableid')
    recordidtable = models.CharField(max_length=255, null=True, blank=True, db_column='recordidtable')

    graph_event_id = models.CharField(max_length=255, null=True, blank=True)
    userid = models.ForeignKey(SysUser, models.DO_NOTHING, null=True, blank=True, db_column='userid')

    owner = models.CharField(max_length=255, null=True, blank=True)
    subject = models.CharField(max_length=255, null=True, blank=True) # Title
    body_content = models.TextField(blank=True) # Description
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=100, default='UTC')

    organizer_email = models.EmailField(max_length=255, blank=True, null=True)
    categories = models.CharField(max_length=255, blank=True, null=True)
    
    m365_calendar_id = models.CharField(max_length=255, blank=True, null=True)
    calendar_delta_link = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'user_events'
        verbose_name_plural = 'Eventi'

class UserJobStatus(BaseUserTable):
    description = models.TextField(null=True, blank=True)
    source = models.CharField(max_length=255, null=True, blank=True)
    sourcenote = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=255, null=True, blank=True)
    creationdate = models.DateField(null=True, blank=True)
    closedate = models.DateField(null=True, blank=True)
    technote = models.TextField(null=True, blank=True)
    context = models.CharField(max_length=255, null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    file = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'user_job_status'
        verbose_name_plural = 'Stato Lavori'