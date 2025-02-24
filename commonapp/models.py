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
    otp_secret = models.CharField(max_length=32, default=pyotp.random_base32, unique=True)  # Secret per OTP
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

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userprofile.save()  # Salva UserProfile quando si salva User