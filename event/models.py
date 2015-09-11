from django.db import models
from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.defaultfilters import slugify, date, urlencode

from media.models import PhotosMixin
from wmd import models as wmd_models
from geo.models import Room
from lablackey.utils import cached_property

import datetime, sys, json

def print_time(t):
  if t: return t.strftime('%I:%M %P')
  return ''

def reverse_ics(obj):
  """ see event.views.ics for information on what objects can be used with this function """
  clss = obj.__class__
  module = clss.__module__.split(".")[0]
  model_str = clss.__name__
  f_name = '%s-%s.ics'%(slugify(obj.name),slugify(settings.SITE_NAME))
  return "%s/event/ics/%s/%s/%s/%s"%(settings.SITE_DOMAIN,module,model_str,obj.id,f_name)


REPEAT_CHOICES = (
  ('','No Repeat'),
  ('weekly','Weekly'),
  ('biweekly','Bi Weekly'),
  ('triweekly','Tri Weekly'),
  ('month-dow','Monthly (Nth weekday of every month)'),
  ('month-number','Monthly (by day number)'),
  )

class Event(PhotosMixin,models.Model):
  name = models.CharField(max_length=128,null=True,blank=True)
  _ht = "Optional. Alternative name for the calendar."
  short_name = models.CharField(max_length=64,null=True,blank=True,help_text=_ht)
  room = models.ForeignKey(Room,null=True,blank=True) #! remove ntbt when you remove location.
  get_room = lambda self: self.room
  description = wmd_models.MarkDownField(blank=True,null=True)
  _ht = "If your changing this, you will need to manually delete all future incorrect events. Repeating events are auto-generated every night."
  repeat = models.CharField(max_length=32,choices=REPEAT_CHOICES,null=True,blank=True,help_text=_ht)
  _ht = "If true, this class will not raise conflict warnings for events in the same room."
  no_conflict = models.BooleanField(default=False,help_text=_ht)

  get_short_name = lambda self: self.short_name or self.name
  @property
  def all_occurrences(self):
    return self.eventoccurrence_set.all()
  @property
  def upcoming_occurrences(self):
    return self.eventoccurrence_set.filter(start__gte=datetime.datetime.now())

  @property
  def next_occurrence(self):
    if not self.upcoming_occurrences.count():
      return None
    return self.upcoming_occurrences[0]

  def get_name(self):
    return self.name or self.room

  get_ics_url = lambda self: reverse_ics(self)

  __unicode__ = lambda self: "%s@%s"%(self.name,self.room)
  class Meta:
    pass

class OccurrenceModel(models.Model):
  """
  The goal is to eventually make this very general so that it can reach accross many models to be put into a feed.
  Occurrences need a start (DateTime), end (DateTime, optional), name (str), description (str), and get_absolute_url (str).
  """
  start = models.DateTimeField()
  end_time = models.TimeField()
  __unicode__ = lambda self: "%s - %s"%(self.name,date(self.start,'l F d, Y'))
  created = models.DateTimeField(auto_now_add=True)

  get_ics_url = lambda self: reverse_ics(self)

  @property
  def end(self):
    return self.start.replace(hour=self.end_time.hour,minute=self.end_time.minute)
  @property
  def google_link(self):
    d = {
      'name': urlencode(self.name),
      'start': date(self.start,"Ymd\THi00"),
      'end': date(self.end,"Ymd\THi00"),
      'description': urlencode(self.description),
      'site_name': urlencode('TX/RX Labs'),
      'location': "205 Roberts Street, Houston TX, 77003",
      'url': 'http://txrxlabs.org/', #+urlencode(self.get_absolute_url()),
      }
    return "http://www.google.com/calendar/event?action=TEMPLATE&text=%(name)s&dates=%(start)s/%(end)s&details=%(description)s&location=%(location)s&trp=false&sprop=%(site_name)s&sprop=name:%(url)s"%d
  class Meta:
    abstract = True

class EventOccurrence(PhotosMixin,OccurrenceModel):
  event = models.ForeignKey(Event)
  publish_dt = models.DateTimeField(default=datetime.datetime.now) # for rss feed
  get_absolute_url = lambda self: reverse('event:occurrence_detail',args=(self.id,slugify(self.name)))
  get_admin_url = lambda self: "/admin/event/event/%s/"%self.event.id
  name_override = models.CharField(null=True,blank=True,max_length=128)
  name = property(lambda self: self.name_override or self.event.name)
  short_name = property(lambda self: self.name_override or self.event.get_short_name())
  description_override = wmd_models.MarkDownField(blank=True,null=True)
  description = property(lambda self: self.description_override or self.event.description)
  get_room = lambda self: self.event.room #! depracate me
  room = cached_property(lambda self: self.event.room,name="room")
  no_conflict = property(lambda self: self.event.no_conflict)
  def save(self,*args,**kwargs):
    # set the publish_dt to a week before the event
    self.publish_dt = self.start - datetime.timedelta(7)
    super(EventOccurrence,self).save(*args,**kwargs)
  class Meta:
    ordering = ('start',)

#these signals fire and mess up loaddata
if not 'loaddata' in sys.argv:
  from .signals import *
