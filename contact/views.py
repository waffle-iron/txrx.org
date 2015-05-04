from django.contrib import messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse

from .models import Subject
from .forms import MessageForm

def contact(request):
  initial = {}
  if request.user.is_authenticated():
    initial['from_email'] = request.user.email
    initial['from_name'] = request.user.get_full_name() or request.user.username
  try:
    initial['contactsubject'] = Subject.objects.get(slug=request.GET.get('slug',''))
  except Subject.DoesNotExist:
    pass
  form = MessageForm(request.POST or None,initial=initial)
  if form.is_valid():
    message = form.save()
    if request.user.is_authenticated():
      message.user = request.user
      message.save()
    messages.success(request,"Your message has been sent. We will respond to you as soon as possible.")
    return HttpResponseRedirect('.')
  values = {
    'form': form,
    'ubjects': Subject.objects.all(),
  }
  return TemplateResponse(request,"contact.html",values)
  
