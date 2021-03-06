from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.mail import send_mail, mail_admins
from django.template.defaultfilters import striptags
from django.template.loader import render_to_string

from course.models import Session
from lablackey.mail import mail_on_fail
from membership.models import LimitedAccessKey

import datetime

class Command (BaseCommand):
  def handle(self, *args, **options):
    new_sessions = Session.objects.filter(active=True,notified__isnull=True).exclude(private=True)
    count = new_sessions.count()
    if not new_sessions:
      mail_admins("No classes","No new classes to notify anyone about :(")
      return
    courses = list(set([s.course for s in new_sessions]))
    users = get_user_model().objects.filter(notifycourse__course__in=courses).distinct()
    for user in users:
      sessions = [s for s in new_sessions if user.notifycourse_set.filter(course=s.course)]
      _dict = {
        'user': user,
        'la_key': LimitedAccessKey.new(user),
        'SITE_URL': settings.SITE_URL,
        'new_sessions': sessions,
        }
      send_mail(
        "New classes at the hackerspace",
        render_to_string("notify/notify_course.html",_dict),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        )
    new_sessions.update(notified=datetime.datetime.now())
    print "Notified %s users of %s classes"%(len(users),count)
