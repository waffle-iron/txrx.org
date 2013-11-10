from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

import shutil, os

class Command(BaseCommand):
  def handle(self, *args, **options):
    default = settings.DATABASES['default']['NAME']
    anon = os.path.join(settings.SPATH,'../scripts/anon.db')
    if not 'sqlite3' in settings.DATABASES['default']['ENGINE']:
      raise NotImplementedError("This management command is only set up to restore sqlite3 databases.")
    while True:
      answer = raw_input("This will delete the current database (%s) and replace it with the most recent copy of the anonymous database. \nAre you sure you want to do this? Type yes or no."%default)
      if answer == 'yes':
        shutil.copy(anon,default)
        print "database successfully reset. user__1 is a superuser, all passwords are now \'hackerspace\'."
        break
      if answer == 'no':
        print "no action taken"
        break
      print "Invalid entry, please try again."
                    