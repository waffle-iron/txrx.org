from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.forms.models import BaseInlineFormSet
from django.utils.translation import ugettext_lazy as _

from .models import Event, EventOccurrence
from event.utils import get_room_conflicts
from media.admin import TaggedPhotoAdmin

import datetime,functools

class OccurrenceModelFormSet(BaseInlineFormSet):
  def check_conflicts(self,obj):
    conflicts = get_room_conflicts(obj)
    if conflicts:
      m = "%s was saved, but some of the times conflict with other events in the room: %s"
      messages.error(self.request,m%(obj,obj.room))
    for room,conflict_tuples in conflicts:
      for (start,end),events in conflict_tuples:
        for event in events:
          if event != obj:
            m = "%s is in the same room with overlapping time %s-%s"%(event,start,end)
            messages.error(self.request,m)
  def save_existing(self, form, obj, commit=True):
    obj = super(OccurrenceModelFormSet,self).save_existing(form,obj,commit=commit)
    self.check_conflicts(obj)
    return obj
  def save_new(self, form, commit=True):
    obj = super(OccurrenceModelFormSet,self).save_new(form,commit=commit)
    self.check_conflicts(obj)
    return obj

class OccurrenceModelInline(admin.TabularInline):
  formset = OccurrenceModelFormSet
  def get_formset(self, request, obj=None, **kwargs):
    form_class = super(OccurrenceModelInline, self).get_formset(request, obj, **kwargs)
    form_class.request = request
    return form_class

class FuturePastListFilter(admin.SimpleListFilter):
  title = _('Filter by Date')
  parameter_name = 'futurepast'

  def lookups(self, request, model_admin):
    return (
      ('future', _('Hide Past Events')),
      ('past', _('Past Events Only')),
    )
    
  def queryset(self, request, queryset):
    if self.value() == 'future':
      return queryset.filter(start__gte=datetime.date.today())
    if self.value() == 'past':
      return queryset.filter(start__lt=datetime.date.today())

class EventOccurrenceInline(OccurrenceModelInline):
  model = EventOccurrence
  fields = ('name_override','start','end_time')
  def get_queryset(self,request):
    qs = super(EventOccurrenceInline,self).get_queryset(request)
    return qs.filter(start__gte=datetime.datetime.now())

class EventAdmin(TaggedPhotoAdmin):
  list_display = ("__unicode__","repeat")
  inlines = [EventOccurrenceInline]
  search_fields = ['name']

class EventOccurrenceAdmin(TaggedPhotoAdmin):
  search_fields = ['event__name']
  list_filter = (FuturePastListFilter,)

admin.site.register(Event,EventAdmin)
admin.site.register(EventOccurrence,EventOccurrenceAdmin)
