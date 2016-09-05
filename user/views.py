from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from .models import User, UserCheckin, RFID
from event.models import RSVP
from course.models import Enrollment, ClassTime
from course.utils import get_or_create_student
from geo.models import Room
from membership.utils import temp_user_required
from redtape.models import Document
from tool.models import Criterion, UserCriterion, Permission

from lablackey.utils import get_or_none

import json, datetime

def checkin_json(user):
  today = datetime.date.today()
  tomorrow = today + datetime.timedelta(1)
  if settings.DEBUG:
    tomorrow = tomorrow+datetime.timedelta(10)
  _q = Q(session__enrollment__user=user) | Q(session__user=user)
  _ct = ClassTime.objects.filter(_q,start__gte=today,start__lte=tomorrow)
  _sq = Q(canceled__gte=datetime.datetime.now()-datetime.timedelta(90)) | Q(canceled__isnull=True)
  _s = user.subscription_set.filter(_sq).order_by("-canceled")
  if user.level and user.level.order >= 10:
    required_document_ids = getattr(settings,"REQUIRED_DOCUMENT_IDS",[])
  else:
    required_document_ids = getattr(settings,"NONMEMBER_DOCUMENT_IDS",[])
  documents = [d.get_json_for_user(user) for d in Document.objects.filter(id__in=required_document_ids)]
  return {
    'classtimes': [c.as_json for c in _ct],
    'sessions': {c.session_id: c.session.as_json for c in _ct},
    'permission_ids': [p.pk for p in Permission.objects.all() if p.check_for_user(user)],
    'user_id': user.id,
    'user_display_name': user.get_full_name(),
    'subscriptions': [s.as_json for s in _s],
    'documents': documents,
  }

@staff_member_required
def todays_checkins_json(request):
  checkins = UserCheckin.objects.filter(time_in__gte=datetime.datetime.now().replace(hour=0,minute=0))
  return JsonResponse({
    'checkins': [checkin_json(checkin.user) for checkin in checkins],
  })

@temp_user_required
def checkin_ajax(request):
  messages = []
  user = request.temp_user
  defaults = {'content_object': Room.objects.get(name='')}
  if not request.POST.get('no_checkin',None):
    checkin, new = UserCheckin.objects.checkin_today(user=user,defaults=defaults)
    messages.append({'level': 'success', 'body': '%s checked in at %s'%(user,checkin.time_in)})
  out = {
    'messages': messages,
    'checkin': checkin_json(user),
  }
  return JsonResponse(out)

@temp_user_required
def add_rfid(request):
  rfid = request.POST['rfid']
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
    return JsonResponse({})
  enrollments = Enrollment.objects.filter(user=request.user,completed__isnull=False)
  usercriteria = UserCriterion.objects.filter(user=request.user)
  _c = Criterion.objects.filter(courses__session__user=request.user).distinct()
  master_criterion_ids = list(_c.values_list('id',flat=True))
  out = {
    'id': request.user.id,
    'username': request.user.username,
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
  }
  #valuestools = Tool.objects.filter(permission__id__in=permission_ids).distinct()
  return JsonResponse(out);

@staff_member_required
def set_rfid(request):
  user = get_object_or_404(get_user_model(),pk=request.GET['user_id'])
  RFID.objects.get_or_create(user=user,number=request.GET['rfid'])
  response = {
    'rfids': list(RFID.objects.filter(user=user).values_list("number",flat=True)),
  }
  return JsonResponse(response)

@staff_member_required
def remove_rfid(request):
  user = get_object_or_404(get_user_model(),pk=request.GET['user_id'])
  RFID.objects.get(user=user,number=request.GET['rfid']).delete()
  response = {
    'rfids': list(RFID.objects.filter(user=user).values_list("number",flat=True)),
  }
  return JsonResponse(response)
