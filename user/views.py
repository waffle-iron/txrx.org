from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from .models import User, UserCheckin, RFID
from event.models import RSVP
from course.models import Enrollment
from course.utils import get_or_create_student
from geo.models import Room
from redtape.models import Signature
from tool.models import Criterion, UserCriterion, Permission

from lablackey.utils import get_or_none, JsonResponse

import json, datetime

def checkin_ajax(request):
  rfid = request.GET.get('rfid',None)
  user = get_or_none(User,rfid__number=rfid or 'notavalidrfid')
  email = request.GET.get("email",None) or "notavaildemail"
  user = user or get_or_none(User,email=email)
  user = user or get_or_none(User,usermembership__paypal_email=email)
  if rfid and not user:
    return JsonResponse({'next': "new-rfid", 'rfid': rfid})
  if not user:
    return JsonResponse({'errors': {'non_field_errors': 'Unable to find user. Contact the staff'}})
  if not user.signature_set.filter(document_id=2):
    return HttpResponse(json.dumps({'no_waiver': email}))
  defaults = {'content_object': Room.objects.get(name='')}
  checkin, new = UserCheckin.objects.get_or_create(user=user,time_out__isnull=True,defaults=defaults)
  if not new:
    checkin.time_out = datetime.datetime.now()
    checkin.save()
  out = {
    'messages': [{'level': 'success', 'body': '%s checked in at %s'%(user,checkin.time)}]
  }
  return HttpResponse(json.dumps(out))

def add_rfid(request):
  rfid = request.POST['rfid']
  username = request.POST['username']
  user = get_or_none(User,username=username)
  user = user or get_or_none(User,email=username)
  user = user or get_or_none(User,usermembership__paypal_email=username)
  if not user or not user.check_password(request.POST['password']):
    return JsonResponse({'errors': {'non_field_errors': ['Incorrect username/email and password combination.']}})
  if user.rfid_set.count():
    m = 'You already have an RFID card registered. Please see staff if you need to change cards.'
    messages = [{'level': 'danger', 'body': m}]
    return JsonResponse({'messages': messages})
  RFID.objects.get_or_create(user=user,number=rfid)
  messages = [{'level': 'success', 'body': 'RFID set. Please swipe now to checkin.'}]
  return JsonResponse({'messages': messages})

def checkin_register(request):
  keys = ['email','first_name','last_name',"password"]
  user,new = get_or_create_student({k: request.POST[k] for key in keys})

def user_json(request):
  if not request.user.is_authenticated():
    return TemplateResponse(request,"user.json",{'user_json':'{}'});
  enrollments = Enrollment.objects.filter(user=request.user,completed__isnull=False)
  usercriteria = UserCriterion.objects.filter(user=request.user)
  _c = Criterion.objects.filter(courses__session__user=request.user).distinct()
  master_criterion_ids = list(_c.values_list('id',flat=True))
  values = {
    'user_json': json.dumps({
      'id': request.user.id,
      'permission_ids': [p.pk for p in Permission.objects.all() if p.check_for_user(request.user)],
      'criterion_ids': list(usercriteria.values_list('criterion_id',flat=True)),
      'master_criterion_ids': master_criterion_ids,
      'session_ids': list(request.user.session_set.all().values_list('id',flat=True)),
      'completed_course_ids': [e.session.course_id for e in enrollments],
      'is_toolmaster': request.user.is_toolmaster,
      'is_staff': request.user.is_staff,
      'is_superuser': request.user.is_superuser,
      'enrollments': {e.session_id:e.quantity for e in request.user.enrollment_set.all()},
      'member_discount_percent': request.user.level.discount_percentage,
    })
  }
  return TemplateResponse(request,"user.json",values)

@staff_member_required
def set_rfid(request):
  user = get_object_or_404(get_user_model(),pk=request.GET['user_id'])
  RFID.objects.get_or_create(user=user,number=request.GET['rfid'])
  response = {
    'rfids': list(RFID.objects.filter(user=user).values_list("number",flat=True)),
  }
  return HttpResponse(json.dumps(response))

@staff_member_required
def remove_rfid(request):
  user = get_object_or_404(get_user_model(),pk=request.GET['user_id'])
  RFID.objects.get(user=user,number=request.GET['rfid']).delete()
  response = {
    'rfids': list(RFID.objects.filter(user=user).values_list("number",flat=True)),
  }
  return HttpResponse(json.dumps(response))
