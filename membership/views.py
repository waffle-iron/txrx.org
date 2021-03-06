from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.flatpages.models import FlatPage
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from .models import Level, Group, MeetingMinutes, Officer, UserMembership, Subscription, Flag, Container
from .forms import UserForm, UserMembershipForm, RegistrationForm
from .utils import limited_login_required, verify_unique_email

from blog.models import Post
from course.models import Course, Session
from thing.models import Thing
from tool.models import Permission, Tool, APIKey, DoorGroup, Schedule, Holiday

from lablackey.utils import FORBIDDEN
from lablackey.mail import send_template_email

import datetime, json

def join_us(request):
  values = {
    'groups': Group.objects.all(),
    'flatpage':lambda:FlatPage.objects.get(url='/join-us/'),
    }
  return TemplateResponse(request,"membership/memberships.html",values)

@login_required
def user_settings(request):
  user = request.user
  user_form = UserForm(request.POST or None, instance=user)
  usermembership_form = UserMembershipForm(request.POST or None, request.FILES or None, instance=user.usermembership)
  if request.POST and all([user_form.is_valid(),usermembership_form.is_valid()]):
    user_form.save()
    usermembership_form.save()
    messages.success(request,'Your settings have been saved.')
    return HttpResponseRedirect(request.path)
  values = {
    'forms': [user_form, usermembership_form],
    'notify_courses': user.notifycourse_set.all(),
    }
  return TemplateResponse(request,'membership/settings.html',values)

@login_required
def minutes(request,datestring):
  date = datetime.datetime.strptime(datestring,"%Y-%m-%d")
  minutes = get_object_or_404(MeetingMinutes,date=date)
  values = {
    'minutes': minutes,
    }
  return TemplateResponse(request,'membership/minutes.html',values)

@login_required
def minutes_index(request):
  values = {
    'minutes_set': MeetingMinutes.objects.all(),
    }
  return TemplateResponse(request,'membership/minutes_index.html',values)

def register(request,*args,**kwargs):
  email = request.POST.get('email','')
  paypal_email = request.POST.get('paypal_email','')
  form = RegistrationForm(request,request.POST or None)
  if form.is_valid():
    if request.POST and not (verify_unique_email(email) and verify_unique_email(paypal_email)):
      m = "Please use the form below to reset your password. "
      m += "<br />If you believe this is in error, please email %s"%settings.CONTACT_LINK
      m = "An account with the email address %s already exists. %s"%(email,m)
      messages.error(request,m,extra_tags='danger')
      return HttpResponseRedirect(reverse('password_reset'))
    user = form.save(request)
    return HttpResponseRedirect(reverse('registration_complete'))
  values = {
    'form': form,
  }
  return TemplateResponse(request,'registration/registration_form.html',values)

def roland_email(request,y=2012,m=1,d=1):
  if not request.user.is_superuser:
    raise Http404
  import csv
  dt = datetime.date(int(y),int(m),int(d))
  # Create the HttpResponse object with the appropriate CSV header.
  response = HttpResponse(content_type='text/csv')
  response['Content-Disposition'] = 'attachment; filename="txrx_emails_%s-%s-%s.csv"'%(y,m,d)

  writer = csv.writer(response)
  for user in get_user_model().objects.filter(date_joined__gt=dt,is_active=True):
    if "email" in request.GET:
      writer.writerow([user.email])
    else:
      writer.writerow([user.email,user.username,str(user.date_joined)])

  return response

def officers(request):
  officers = Officer.objects.all()
  values = {'officers': officers}
  return TemplateResponse(request,'membership/officers.html',values)

def verify_api(request):
  if not getattr(settings,'PORTAL_KEY','') == request.REQUEST.get('api_key',''):
    raise Http404

def user_emails(request):
  verify_api(request)
  out = []
  for u in get_user_model().objects.all():
    out.append(','.join([str(u.id),u.email or '',u.paypal_email or '']))
  return HttpResponse('\n'.join(out))

def course_names(request):
  verify_api(request)
  out = []
  for c in Course.objects.all():
    out.append(','.join([str(c.id),c.name]))
  return HttpResponse('\n'.join(out))

def member_index(request,username=None):
  instructors = UserMembership.objects.list_instructors()
  values = { 'instructors': instructors }
  return TemplateResponse(request,"membership/member_index.html",values)

def member_detail(request,username=None):
  user = get_object_or_404(get_user_model(),username=username)
  things = Thing.objects.filter(user=user,active=True)
  posts = Post.objects.filter(user=user, status = 'published').order_by("-publish_dt")
  values = {
    'thing_header': user.username + "'s Things",
    'post_header' : user.username + "'s Blog Posts",
    'user': user,
    'profile': user.usermembership,
    'things': things,
    'posts': posts
  }
  return TemplateResponse(request,"membership/member_detail.html",values)

@staff_member_required
def analysis(request):
  order = request.GET.get('order','-subscription__status')
  orders = [
    ('-subscription__status','Last Payment'),
    ('-subscription__owed','Money owed'),
  ]
  level_users = []
  for level in Level.objects.filter(order__gt=0):
    users = get_user_model().objects.filter(level=level)
    if not "canceled" in request.GET:
      users = users.filter(subscription__canceled__isnull=True)
    level_users.append((level,users.order_by(order).distinct()))
  values = {
    'level_users': level_users,
    'order': order,
    'orders': orders
  }
  return TemplateResponse(request,"membership/analysis.html",values)

@staff_member_required
def force_cancel(request,pk):
  subscription = Subscription.objects.get(pk=pk)
  if "undo" in request.GET:
    subscription.canceled = None
    subscription.save()
    subscription.recalculate()
    messages.success(request,"Subscription #%s un-canceled"%pk)
  else:
    subscription.force_canceled()
    messages.success(request,"Subscription #%s set to canceled"%pk)
  if request.GET.get("next",None):
    return HttpResponseRedirect(request.GET['next'])
  return HttpResponse('')

@staff_member_required
def flag_subscription(request,pk):
  subscription = Subscription.objects.get(pk=pk)
  flag,new = Flag.objects.get_or_create(
    subscription=subscription,
    reason="manually_flagged",
  )
  messages.success(request,"Subscription #%s flagged, you can edit it below"%pk)
  return HttpResponseRedirect("/admin/membership/flag/%s/"%flag.pk)

@staff_member_required
def containers(request):
  return TemplateResponse(request,'membership/containers.html',{})

@staff_member_required
def update_flag_status(request,flag_pk,new_status=None):
  flag = get_object_or_404(Flag,pk=flag_pk)
  if not new_status:
    new_status = flag.PAYMENT_ACTIONS[flag.status][0]
  flag.apply_status(new_status)
  if request.is_ajax():
    return HttpResponse("Membership status changed to %s"%flag.get_status_display())
  messages.success(request,"Membership status changed to %s"%flag.get_status_display())
  return HttpResponseRedirect('/admin/membership/flag/%s/'%flag_pk)

def door_access(request):
  fail = HttpResponseForbidden("I am Vinz Clortho keymaster of Gozer... Gozer the Traveller, he will come in one of the pre-chosen forms. During the rectification of the Vuldronaii, the Traveller came as a large and moving Torb! Then, during the third reconciliation of the last of the Meketrex Supplicants they chose a new form for him... that of a Giant Sloar! many Shubs and Zulls knew what it was to be roasted in the depths of the Sloar that day I can tell you.")
  valid = request.META['REMOTE_ADDR'] in getattr(settings,'DOOR_IPS',[])
  valid = valid or APIKey.objects.filter(key=request.GET.get("api_key"))
  if not valid and not request.user.is_authenticated():
    return fail
  valid = valid or request.user.is_superuser

  _Q = Q(canceled__isnull=True) | Q(canceled__gte=datetime.datetime.now())
  base_subs = Subscription.objects.filter(_Q,owed__lte=0)
  base_subs = base_subs.exclude(user__rfid__isnull=True)

  obj = None
  out = {
    'schedule': {},
    'rfids': {},
    'holidays': {}
  }

  if 'permission_id' in request.GET:
    obj = get_object_or_404(Permission,id=request.GET['permission_id'])
    valid = valid or request.user.is_toolmaster
    superQ = Q(is_superuser=True)|Q(is_toolmaster=True)

    # only return subscriptions where the user has this permission
    base_subs = base_subs.filter(user_id__in=obj.get_all_user_ids())

  if 'door_id' in request.GET:
    obj = get_object_or_404(DoorGroup,id=request.GET['door_id'])
    valid = valid or request.user.is_gatekeeper
    superQ = Q(is_superuser=True)|Q(is_gatekeeper=True)
    _hids = [99999]+list(Level.objects.filter(holiday_access=True).values_list("id",flat=True))
    _hids = [str(h) for h in _hids]
    out['holidays'] = { h.date.strftime("%Y-%m-%d"):_hids for h in Holiday.objects.all()}

  if not (valid and obj):
    return fail

  #fieldname is intended to be used only for testing
  fieldname = request.GET.get('fieldname','rfid__number')
  if fieldname in ['email','paypal_email','password']:
    return fail

  schedule_jsons = { s.id: s.as_json for s in Schedule.objects.all() }
  for level in Level.objects.all():
    subscriptions = base_subs.filter(product__level=level).distinct()
    out['rfids'][level.order] = list(subscriptions.values_list('user__'+fieldname,flat=True))
    out['schedule'][level.order] = schedule_jsons.get(level.get_schedule_id(obj),{})
  staff = get_user_model().objects.filter(superQ).exclude(rfid__isnull=True)
  out['rfids'][99999] = list(staff.values_list(fieldname,flat=True))
  out['schedule'][99999] = schedule_jsons[settings.ALL_HOURS_ID]
  if 'api_key' in request.GET:
    return HttpResponse(json.dumps(out))
  return HttpResponse("<pre>%s</pre>"%json.dumps(out,indent=4))

@staff_member_required
def rfid_permission_table(request):
  permissions = Permission.objects.all().order_by("name")
  permissions_tools = [(p,p.tool_set.all().order_by('name')) for p in permissions]
  permissions_tools.append((None,Tool.objects.filter(permission=None).order_by('name')))
  values = {
    'permission_tools': permissions_tools,
    'levels': Level.objects.all(),
    'doorgroups': DoorGroup.objects.all()
  }
  return TemplateResponse(request,'membership/rfid_permission_table.html',values)

@staff_member_required
def container(request,pk):
  container = get_object_or_404(Container,pk=pk)
  action = request.GET['action']
  if action == "send_mail":
    container.status = "emailed"
    container.save()
    values = {'container': container}
    send_template_email("email/canceled_container",container.subscription.user.email,
                        from_email="info@txrxlabs.org",context=values)
    messages.success(request,"%s has been marked as emailed."%(container))
  if action in ["emailed", "open","maintenance"]:
    container.status = action
    container.save()
    messages.success(request,"%s has been marked as %s."%(container,action))
  return HttpResponseRedirect("/admin/membership/container/%s"%container.pk)
