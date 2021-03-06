from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import QueryDict, Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from ..models import Course, Term, Subject, Session, Enrollment, ClassTime
from ..forms import EmailInstructorForm, EvaluationForm
from notify.models import NotifyCourse
from lablackey.utils import get_or_none
from event.utils import make_ics,ics2response

from paypal.standard.ipn.models import *
import datetime, json

def get_course_values(user):
  if not user.is_authenticated():
    return { 'term': Term.objects.all()[0] }
  user_sessions = Session.objects.filter(enrollment__user=user.id)
  return {
    'user_sessions': sorted(list(user_sessions),key=lambda s: s.first_date,reverse=True),
    'instructor_sessions': Session.objects.filter(user=user).reverse(),
    'pending_evaluations': Enrollment.objects.pending_evaluation(user=user),
    'future_sessions': user_sessions.filter(last_date__gte=datetime.date.today()).count(),
    'past_sessions': user_sessions.filter(last_date__lt=datetime.date.today()).count(),
  }

def index(request):
  return TemplateResponse(request,"course/index.html",get_course_values(request.user))

def user_ajax(request,template):
  return TemplateResponse(request,"course/_%s.html"%template,get_course_values(request.user))

#the old way we did classes had session detail pages
def detail_redirect(request,slug):
  pk = slug.split("_")[-1]
  if pk.isdigit():
    try:
      return HttpResponseRedirect(Session.objects.get(pk=pk).get_absolute_url())
    except Session.DoesNotExist:
      pass
  return HttpResponseRedirect("/classes/")

def detail(request,pk,slug):
  course = get_object_or_404(Course,pk=pk)
  enrollment = None
  notify_course = None
  if request.user.is_authenticated():
    _e = Enrollment.objects.filter(session__course=course,user=request.user)
    enrollment = (_e or [None])[0]
    notify_course = get_or_none(NotifyCourse,user=request.user,course=course)
  kwargs = dict(active=True,subjects__in=course.subjects.all())
  related_courses = Course.objects.filter(**kwargs).exclude(id=course.id)
  values = {
    'course': course,
    'enrollment': enrollment,
    'related_courses': related_courses,
    'notify_course': notify_course,
  }
  return TemplateResponse(request,"course/detail.html",values)

def ics_classes_all(request,fname):
  occurrences = ClassTime.objects.all()
  calendar_object = make_ics(occurrences,title="%s Classes"%settings.SITE_NAME)
  return ics2response(calendar_object,fname=fname)

def ics_classes_user(request,u_id,api_key,fname):
  user = get_object_or_404(get_user_model(),pk=u_id,usermembership__api_key=api_key)
  enrollments = user.enrollment_set.all()
  sessions = [e.session for e in enrollments]
  sessions += user.session_set.all()
  occurrences = []
  for session in sessions:
    occurrences += session.classtime_set.all()
  calendar_object = make_ics(occurrences,title="%sMy Classes"%settings.EMAIL_SUBJECT_PREFIX)
  return ics2response(calendar_object,fname=fname)

@staff_member_required
def course_full(request):
  dt = datetime.date.today()-datetime.timedelta(14)
  values = {
    'sessions': Session.objects.filter(first_date__gte=dt).order_by('first_date'),
    }
  return TemplateResponse(request,"course/occupancy.html",values)

def course_totals(request):
  if not request.user.is_superuser:
    raise Http404('Page not found')
  term_list = []
  args = ('session','session__course')
  enrollments = Enrollment.objects.select_related(*args)
  for term in Term.objects.all():
    _dict = {
      'term': term,
      'sessions': {},
      'money': 0,
      'attendance': 0,
      }
    _enrollments = enrollments.filter(session__term=term)
    for e in _enrollments:
      session_dict = _dict['sessions'].get(e.session,{})
      session_dict['money'] = session_dict.get('money',0) + e.session.course.fee
      session_dict['attendance'] = session_dict.get('attendance',0) + e.quantity
      _dict['sessions'][e.session] = session_dict
      _dict['money'] += e.session.course.fee
      _dict['attendance'] += e.quantity
    term_list.append(_dict)
  values = { 'term_list': term_list }
  return TemplateResponse(request,'course/course_totals.html',values)

def rsvp(request,session_pk):
  session = get_object_or_404(Session,pk=session_pk)
  if session.course.fee > 0:
    raise ValueError("Some one tried to rsvp for a class that costs money!")
  if not request.user.is_authenticated():
    m = "You must be logged in to rsvp. Click the icon at the top right of the page to login or register"
    return HttpResponse(json.dumps([0,m,session.full]))
  enrollment,new = Enrollment.objects.get_or_create(user=request.user,session=session)
  if "unrsvp" in request.path:
    enrollment.delete()
    q = 0
    m = "You are no longer signed up for this."
  elif session.full:
    q = enrollment.quantity
    m = "Sorry, this event is full. Visit the class page to see when it will be offered again."    
  else:
    q = 1
    m = "You have RSVP'd for this event. If you can't make it, please come back and unenroll."
  return HttpResponse(json.dumps({'quantity': q,'message': m,'full':session.full}))

def start_checkout(request):
  if not 'cart' in request.GET:
    raise Http404('cart information missing from request')
  cart_items = json.loads(request.GET['cart'])
  out = []
  for cart_item in cart_items:
    session = Session.objects.get(pk=cart_item['pk'])
    new_total = session.total_students + cart_item['quantity']
    if new_total > session.course.max_students:
      out.append({'pk': session.pk,'remaining': session.course.max_students-session.total_students})
  return HttpResponse(json.dumps(out))

def delay_reschedule(request,course_pk,n_months):
  user = request.user
  if not (user.is_superuser or user.groups.filter(name="Class Coordinator")):
    raise Http404('Page not found.')
  course = get_object_or_404(Course,pk=course_pk)
  if n_months == "close":
    course.active = False
    messages.success(request,"%s has been marked as inactive"%course)
  else:
    course.reschedule_on = datetime.datetime.now()+datetime.timedelta(int(n_months)*30)
    messages.success(request,"%s has been delayed for %s months"%(course,n_months))
  course.save()
  return HttpResponseRedirect(reverse("admin:index"))

@staff_member_required
def toggle_enrollment(request):
  enrollment = get_object_or_404(Enrollment,pk=request.GET["enrollment_id"])
  if not request.user.is_toolmaster or request.user == enrollment.session.user:
    return HttpResponseForbidden("You do not have permission to modify this enrollment")
  enrollment.completed = not enrollment.completed
  enrollment.save()
  return HttpResponse(json.dumps(enrollment.as_json))

@staff_member_required
def clone_session(request,course_pk):
  session = Course.objects.get(pk=course_pk).session_set.order_by("-first_date")[0]
  clone = Session(
    course_id = session.course_id,
    user_id = session.user_id,
    first_date = session.first_date,
    last_date = session.last_date,
    active=False,
  )
  clone.save()
  for classtime in session.classtime_set.all():
    ClassTime(
      start=classtime.start,
      end_time=classtime.end_time,
      session=clone
    ).save()
  messages.success(request,"Session has been cloned. Modify dates and mark active.")
  return HttpResponseRedirect("/admin/course/session/%s/"%clone.pk)
