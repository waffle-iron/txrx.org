from django.template import Library

from course.models import Course, Session
from event.utils import get_room_conflicts as _get_room_conflicts

import datetime

register = Library()

@register.filter
def is_event_coordinator(user):
  return user.is_superuser or user.groups.filter(name="Event Coordinator")

@register.filter
def is_course_manager(user):
  return user.is_superuser or user.groups.filter(name="Course Manager")

@register.simple_tag(takes_context=True)
def get_room_conflicts(context):
  context['room_conflicts'] = _get_room_conflicts()
  return ''

@register.simple_tag(takes_context=True)
def get_courses_needed(context):
  context['courses_needed'] = Course.objects.courses_needed()
  context['inactive_sessions'] = Session.objects.filter(active=False)
  return ''
