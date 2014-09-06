from paypal.standard.ipn.signals import payment_was_successful, payment_was_flagged
from django.dispatch import receiver
from django.http import QueryDict
from django.conf import settings
from django.core.mail import send_mail, mail_admins
from django.template.loader import render_to_string

from .utils import get_or_create_student
from notify.models import NotifyCourse

import traceback

@receiver(payment_was_successful, dispatch_uid='course.signals.handle_successful_payment')
def handle_successful_payment(sender, **kwargs):
  from course.models import Enrollment, Session
  #add them to the classes they're enrolled in
  params = QueryDict(sender.query)
  user,new_user = get_or_create_student(sender.payer_email,u_id=params.get('custom',None))
  try:
    class_count = int(params['num_cart_items'])
  except:
    class_count = 1

  enrollments = []
  error_sessions = []
  admin_subject = "New course enrollment"
  for i in range(1, class_count+1):
    section_cost = int(float(params['mc_gross_%d'%i]))
    quantity = int(params['quantity%s'%i])

    try:
      session = Session.objects.get(id=int(params['item_number%d' % (i, )]))
    except Session.DoesNotExist:
      mail_admins("Session not found",traceback.format_exc())
      continue
    except ValueError:
      mail_admins("Non-integer session number",traceback.format_exc())
      continue

    enrollment,new = Enrollment.objects.get_or_create(user=user, session=session)
    notifys = NotifyCourse.objects.filter(user=user,course=session.section.course)
    if notifys:
      notifys.delete()
    if new:
      enrollment.quantity = quantity
    else:
      enrollment.quantity += quantity
    enrollment.save()
    enrollments.append(enrollment)
    if section_cost != session.section.fee * int(quantity):
      l = [
        "PP cost: %s"%section_cost,
        "Session Fee: %s"%session.section.fee,
        "Session Id:%s"%session.id,
        "Quantity:%s"%enrollment.quantity,
        "PP Email:%s"%sender.payer_email,
        "U Email:%s"%user.email,
      ]
      error_sessions.append("\n".join(l))

  values = {
    'enrollments': enrollments,
    'user': user,
    'new_user': new_user,
  }
  body = render_to_string("email/course_enrollment.html",values)
  send_mail("Course enrollment confirmation",body,settings.DEFAULT_FROM_EMAIL,[user.email,'chris@lablackey.com'])
  if error_sessions:
    mail_admins("Enrollment Error","\n\n".join(error_sessions))

@receiver(payment_was_flagged, dispatch_uid='course.signals.handle_flagged_payment')
def handle_flagged_payment(sender, **kwargs):
  #email people to let them intervene manually
  handle_successful_payment(sender, **kwargs)
