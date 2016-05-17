from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from course.models import Enrollment
from redtape.models import Signature
from tool.models import Tool, Lab, Group, Permission, Criterion, UserCriterion

import json, datetime

def lab_index(request):
  values = {'labs': Lab.objects.all()}
  return TemplateResponse(request,'tool/lab_index.html',values)

def lab_detail(request,lab_slug,pk):
  values = {'lab': get_object_or_404(Lab,pk=pk) }
  return TemplateResponse(request,'tool/lab_detail.html',values)

def tool_detail(request,tool_slug,pk):
  tool = get_object_or_404(Tool,pk=pk)
  values = {
    'tool': tool,
    'lab': tool.lab,
  }
  return TemplateResponse(request,'tool/tool_detail.html',values)

@staff_member_required
def toggle_criterion(request):
  User = get_user_model()
  user = get_object_or_404(User,pk=request.GET['user_id'])
  if request.GET.get('criterion_id'):
    criterion = get_object_or_404(Criterion,pk=request.GET['criterion_id'])
    if not criterion.user_can_grant(request.user):
      return HttpResponseForbidden("You do not have permission to assign this criterion.")
    ucs = UserCriterion.objects.filter(criterion=criterion,user=user)

    if ucs:
      ucs.delete()
    else:
      defaults = {'content_object': request.user}
      UserCriterion.objects.get_or_create(criterion=criterion,user=user,defaults=defaults)
  if request.GET.get('enrollment_id'):
    enrollment = get_object_or_404(Enrollment,pk=request.GET["enrollment_id"])
    if not (request.user.is_toolmaster or request.user == enrollment.session.user):
      return HttpResponseForbidden("You do not have permission to modify this enrollment")
    enrollment.completed = None if enrollment.completed else datetime.datetime.now()
    enrollment.save()
  if request.GET.get('signature_id'):
    signature = get_object_or_404(Signature,pk=request.GET["signature_id"])
    if not request.user.is_toolmaster:
      return HttpResponseForbidden("You do not have permission to modify this document")
    signature.completed = None if signature.completed else datetime.datetime.now()
    signature.save()

  # send back the new user criterion ids to replace old data
  user = User.objects.get(pk=user.pk)
  attrs = ['signature_jsons','enrollment_jsons','locked_criterion_ids','criterion_ids']
  return HttpResponse(json.dumps({attr: getattr(user,attr) for attr in attrs}))

@staff_member_required
def tool_permission_table(request):
  permissions = Permission.objects.all().order_by("name")
  permissions_tools = [(p,p.tool_set.all().order_by('name')) for p in permissions]
  permissions_tools.append((None,Tool.objects.filter(permission=None).order_by('name')))
  values = {
    'permission_tools': permissions_tools,
  }
  return TemplateResponse(request,'tool/tool_permission_table.html',values)
  
