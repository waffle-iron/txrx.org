from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.template.defaultfilters import slugify, date, urlencode

from geo.models import Room
from media.models import PhotosMixin
from lablackey.db.models import UserModel
from lablackey.utils import cached_property, cached_method
from wmd import models as wmd_models

import datetime, sys, math

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

ICON_CHOICES = (
  ("public","Open to the public"),
  ("private","Private - Invitation only"),
  ("rsvp","RSVP Required"),
)

class Event(PhotosMixin,models.Model):
  _use_default_photo = True
  name = models.CharField(max_length=128,null=True,blank=True)
  url = models.CharField(max_length=256,null=True,blank=True)
  _ht = "Optional. Alternative name for the calendar."
  short_name = models.CharField(max_length=64,null=True,blank=True,help_text=_ht)
  room = models.ForeignKey(Room,null=True,blank=True) #! remove ntbt when you remove location.
  get_room = lambda self: self.room
  description = wmd_models.MarkDownField(blank=True,null=True)
  _ht = "If your changing this, you will need to manually delete all future incorrect events."
  _ht += "Repeating events are auto-generated every night."
  repeat = models.CharField(max_length=32,choices=REPEAT_CHOICES,null=True,blank=True,help_text=_ht)
  _ht = "If true, this class will not raise conflict warnings for events in the same room."
  no_conflict = models.BooleanField(default=False,help_text=_ht)
  _ht = "Hidden stuff won't appear on the calendar."
  hidden = models.BooleanField(default=False)
  allow_rsvp = models.BooleanField(default=True)
  _ht = "Number of days before event when RSVP is cut off (eg 0.5 means \"You must rsvp 12 hours before this event\")"
  rsvp_cutoff = models.FloatField(default=0,help_text=_ht)
  max_rsvp = models.IntegerField(default=128)
  icon = models.CharField(max_length=16,choices=ICON_CHOICES)
  @property
  def verbose_rsvp_cutoff(self):
    if self.rsvp_cutoff > 2:
      s = "{} days".format(int(self.rsvp_cutoff))
    else:
      s = "{} hours".format(int(math.ceil(12*self.rsvp_cutoff)))
    return "You must RSVP for this event at least {} before the event begins.".format(s)

  get_short_name = lambda self: self.short_name or self.name
  def get_absolute_url(self):
    return reverse("event:event_detail",args=[self.pk,slugify(self.name)])
  @property
  def all_occurrences(self):
    return self.eventoccurrence_set.all()
  @property
  def upcoming_occurrences(self):
    return self.eventoccurrence_set.filter(start__gte=datetime.datetime.now()-datetime.timedelta(0.5))

  @property
  def next_occurrence(self):
    if not self.upcoming_occurrences.count():
      return None
    return self.upcoming_occurrences[0]
  def get_user_rsvps(self,user):
    occurrence_ids = self.all_occurrences.values_list('id',flat=True)
    rsvps = RSVP.objects.filter(
      user=user,
      object_id__in=occurrence_ids,
      content_type_id=ContentType.objects.get(model="eventoccurrence").id
    )
    return {r.object_id:r.quantity for r in rsvps}
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
      'site_name': settings.SITE_NAME,
      'location': "205 Roberts Street, Houston TX, 77003",
      'url': 'http://txrxlabs.org/', #+urlencode(self.get_absolute_url()),
      }
    return "http://www.google.com/calendar/event?action=TEMPLATE&text=%(name)s&dates=%(start)s/%(end)s&details=%(description)s&location=%(location)s&trp=false&sprop=%(site_name)s&sprop=name:%(url)s"%d
  @property
  def is_external(self):
    url = self.get_absolute_url()
    return not (url.startswith('/') or url.startswith(settings.SITE_URL))
  @property
  def class_name(self):
    extra = " fa fa-external-link" if self.is_external else ""
    return self.icon + extra
  class Meta:
    abstract = True

class RSVP(UserModel):
  content_type = models.ForeignKey("contenttypes.ContentType")
  object_id = models.IntegerField()
  content_object = GenericForeignKey('content_type', 'object_id')
  datetime = models.DateTimeField(auto_now_add=True)
  emailed = models.DateTimeField(null=True,blank=True)
  quantity = models.IntegerField(default=0)
  completed = models.BooleanField(default=False)
  get_occurrences = lambda self: [self.content_object]
  __unicode__ = lambda self: "%s for %s"%(self.user,self.content_object)

class EventOccurrence(PhotosMixin,OccurrenceModel):
  event = models.ForeignKey(Event)
  publish_dt = models.DateTimeField(default=datetime.datetime.now) # for rss feed
  get_admin_url = lambda self: "/admin/event/event/%s/"%self.event.id
  name_override = models.CharField(null=True,blank=True,max_length=128)
  name = property(lambda self: self.name_override or self.event.name)
  short_name = property(lambda self: self.name_override or self.event.get_short_name())
  url = property(lambda self: self.url_override or self.event.url)
  description_override = wmd_models.MarkDownField(blank=True,null=True)
  description = property(lambda self: self.description_override or self.event.description)
  get_room = lambda self: self.event.room #! depracate me
  room = cached_property(lambda self: self.event.room,name="room")
  no_conflict = property(lambda self: self.event.no_conflict)

  url_override = models.CharField(max_length=256,null=True,blank=True)
  _get_absolute_url = lambda self: reverse('event:occurrence_detail',args=(self.id,slugify(self.name)))
  get_absolute_url = lambda self: self.url_override or self.event.url or self._get_absolute_url()
  get_absolute_url = cached_method(get_absolute_url,name="get_absolute_url")

  rsvp_cutoff = property(lambda self: self.start - datetime.timedelta(self.event.rsvp_cutoff))
  total_rsvp = property(lambda self: sum([r.quantity for r in self.get_rsvps()]))
  full = property(lambda self: self.total_rsvp >= self.event.max_rsvp)
  icon = property(lambda self: self.event.icon)
  _cid = ContentType.objects.get(model="eventoccurrence").id
  @cached_method
  def get_rsvps(self):
    return RSVP.objects.filter(object_id=self.id,content_type_id=self._cid)
  def save(self,*args,**kwargs):
    # set the publish_dt to a week before the event
    self.publish_dt = self.start - datetime.timedelta(7)
    super(EventOccurrence,self).save(*args,**kwargs)
  @property
  def past(self):
    now = datetime.datetime.now()
    return (self.end < now) or (self.rsvp_cutoff < now and not self.get_rsvps().count())
  @property
  def as_json(self):
    return {
      'room_id': self.event.room_id,
      'name': self.name,
      'start': str(self.start),
      'end': str(self.end),
    }
  class Meta:
    ordering = ('start',)

class CheckInPoint(models.Model):
  room = models.ForeignKey(Room)
  __unicode__ = lambda self: "%s"%self.room
  class Meta:
    ordering = ('room__name',)

class CheckIn(UserModel):
  datetime = models.DateTimeField(auto_now_add=True)
  object_id = models.IntegerField(null=True,blank=True)
  content_type = models.ForeignKey("contenttypes.ContentType",null=True,blank=True)
  content_object = GenericForeignKey('content_type', 'object_id')
  checkinpoint = models.ForeignKey(CheckInPoint)
  __unicode__ = lambda self: "%s @ %s - %s"%(self.user,self.checkinpoint,self.datetime)
  class Meta:
    ordering = ('-datetime',)
