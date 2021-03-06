from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.template.defaultfilters import date
from django import forms

from models import (Group, Level, Feature, MembershipFeature, UserMembership, Product, Flag,
                    Subscription, Status, MeetingMinutes, Proposal, Officer, Container, LevelDoorGroupSchedule)

from lablackey.db.admin import RawMixin
from lablackey.db.forms import StaffMemberForm

import datetime

admin.site.register(Feature)
admin.site.register(Group)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
  list_display = ('name','__unicode__')

class ContainerInline(admin.TabularInline):
  raw_id_fields = ('subscription',)
  readonly_fields = ("status","notes")
  model = Container
  extra = 0

@admin.register(Flag)
class FlagAdmin(admin.ModelAdmin):
  raw_id_fields = ('subscription',)
  readonly_fields = ('action','datetime')
  list_display = ('__unicode__','status')
  def action(self,obj):
    if not obj or not obj.pk or not obj.status in obj.PAYMENT_ACTIONS:
      return "No action to be taken"
    next_status, verbose, target_days = obj.PAYMENT_ACTIONS[obj.status]
    days_since_flag = (datetime.datetime.now()-obj.last_datetime).days
    _diff = abs(days_since_flag - target_days)
    if days_since_flag > target_days:
      msg = "This person should have been notified of the cancellation %s days ago"%_diff
      cls = 'warning'
    elif days_since_flag < target_days:
      msg = "This person should not be notified for %s more days"%_diff
      cls = 'danger'
    else:
      msg = "This person should be notified now. Send this out now"
      cls = 'success'

    url = reverse('update_flag_status',args=[obj.pk,next_status])
    html = "<div class='alert alert-%s'>%s<br/><a href='%s' class='btn btn-%s'>%s</a></div>"
    return html%(cls,msg,url,cls,verbose)
  action.allow_tags = True

class FlagInline(admin.TabularInline):
  model = Flag
  extra = 0

class StaffContainerFilter(admin.SimpleListFilter):
  title = "Needs Staff Attention?"
  parameter_name = "needs Staff"
  def lookups(self,request,model_admin):
    return [('yes','Yes')]
  def queryset(self,request,queryset):
    if self.value() == 'yes':
      return queryset.filter(Q(status='maintenance')|Q(status='canceled'))
    return queryset

@admin.register(Container)
class ContainerAdmin(admin.ModelAdmin):
  list_display = ("__unicode__","status","subscription","notes")
  raw_id_fields = ("subscription",)
  list_filter = [StaffContainerFilter]
  readonly_fields = ['action','links']
  fields = [
    ('number','room','kind'),
    'subscription','status',
    'notes',
    'action',
    'links'
  ]
  def links(self,obj=None):
    if not obj.subscription:
      return
    link = '<b>%s: </b> <a href="/admin/%s/%s/">%s</a>'
    sub = obj.subscription
    out = link%("User",'user/user',sub.user.pk,sub.user)+"<br/>"
    return out + link%("Subscription",'membership/subscription',sub.pk,sub)
  links.allow_tags = True
  def action(self,obj=None):
    link = '<a href="%s?action=%s">%s</a>'
    if obj.status == "used":
      return "User is paid up and no action should be taken until subscription is canceled."
    if obj.status == "canceled":
      email_link = link%("/membership/container/%s/"%obj.pk,"send_mail","email member about cancelation")
      no_email_link = link%("/membership/container/%s/"%obj.pk,"emailed","mark emailed without notifying user.")
      return "Member dues are past due. Please %s or %s."%(email_link,no_email_link)
    if obj.status == "emailed":
      canceled_datetime = obj.get_cleanout_date()
      return "Member has been emailed that they are past due. "\
        "This %s will be marked canceled on %s."%(obj.kind,date(canceled_datetime,("l F jS, Y")))
    if obj.status == "staff":
      return "This drawer is marked as 'staff'. See notes to see what it is used for."
  action.allow_tags = True

class MembershipFeatureInline(RawMixin,admin.TabularInline):
  extra = 0
  raw_id_fields = ('level','feature')
  model = MembershipFeature

class ProductInline(admin.TabularInline):
  extra = 0
  model = Product
  exclude = ('slug',)

class LevelDoorGroupScheduleInline(admin.TabularInline):
  model = LevelDoorGroupSchedule
  extra = 0

@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
  list_display = ("name","order")
  list_editable = ("order",)
  fieldsets = (
    (None,{'fields': (('name','group'),('discount_percentage','order'),'permission_description',
                      'tool_schedule','door_schedule','holiday_access')}),
    # ('For Profit Features',{
    #   'classes': ('collapse',),
    #   'fields': (('machine_credits','cost_per_credit'),'simultaneous_users',
    #              ('custom_training_cost','custom_training_max'))
    #}),
  )
  inlines = (MembershipFeatureInline, ProductInline, LevelDoorGroupScheduleInline)

class StatusInline(admin.TabularInline):
  model = Status
  exclude = ('paypalipn',)
  readonly_fields = ('datetime',"transaction_id")
  raw_id_fields = ('paypalipn',)
  extra = 0

class CanceledBooleanFilter(admin.SimpleListFilter):
  title = "Canceled?"
  parameter_name = "is_canceled"
  def lookups(self,request,model_admin):
    return [('yes','Yes'),('no','No')]
  def queryset(self,request,queryset):
    if self.value() == 'yes':
      return queryset.filter(canceled__isnull=False)
    elif self.value() == 'no':
      return queryset.filter(canceled__isnull=True)
    return queryset

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
  inlines = [FlagInline,StatusInline]
  search_fields = ['user__username','user__email','user__paypal_email','user__first_name','user__last_name']
  list_display = ("__unicode__","canceled")
  list_filter = [CanceledBooleanFilter]
  fields = (
    ('user','edit_user'),
    ('product','subscr_id'),
    'created',
    ('amount','owed','paid_until'),
    ('canceled','_action'),
    '_container',
  )
  raw_id_fields = ('user',)
  readonly_fields = ('_container','_action','paid_until','canceled','owed','edit_user')
  def _container(self,obj):
    try:
      return '<a href="/admin/membership/container/%s/">%s</a> %s'%(obj.container.pk,obj.container,obj.container.status)
    except:
      pass
  _container.allow_tags = True
  def _action(self,obj):
    if not (obj and obj.pk):
      return "Save before creating actions."
    url = reverse("force_cancel",args=[obj.pk])+"?next=/admin/membership/subscription/%s/"%obj.pk
    if obj and obj.pk and not obj.canceled:
      return "<a href='%s'>%s</a>"%(url,"Force Cancel")
    return "<a href='%s&undo'>%s</a>"%(url,"Undo Cancel")
  _action.allow_tags = True
  _action.short_description = ""
  def edit_user(self,obj):
    if obj and obj.user:
      return '<a class="change-related" href="/admin/user/user/%s/"></a>'%obj.user.pk
  edit_user.allow_tags = True
  edit_user.short_description = ""
  def save_model(self,request,obj,form,change):
    super(SubscriptionAdmin,self).save_model(request,obj,form,change)
    obj.recalculate()

class SubscriptionInline(admin.TabularInline):
  model = Subscription
  readonly_fields = ('subscr_id','created','canceled','paid_until','product','amount','owed')
  ordering = ('-canceled',)
  extra = 0
  #has_add_permission = lambda self,obj: False

class UserMembershipInline(admin.StackedInline):
  list_display = ("__unicode__",'photo')
  list_editable = ('photo',)
  list_filter = ('user__is_staff',)
  search_fields = ('user__email','user__username')
  raw_id_fields = ('photo',)
  fields = (
    'bio', 'photo',
    ('voting_rights','suspended'),
  )
  model = UserMembership

class ProposalInline(admin.StackedInline):
  model = Proposal
  raw_id_fields = ('user',)
  fields = ('order','title','user','original','ammended')
  extra = 0

class MeetingMinutesForm(forms.ModelForm):
  User = get_user_model()
  _q = User.objects.filter(usermembership__voting_rights=True,usermembership__suspended=False)
  kwargs = dict(widget=forms.CheckboxSelectMultiple(),required=False)
  voters_present = forms.ModelMultipleChoiceField(queryset=_q,**kwargs)
  _q = User.objects.filter(usermembership__voting_rights=True,usermembership__suspended=True)
  kwargs = dict(widget=forms.CheckboxSelectMultiple(),required=False)
  inactive_present = forms.ModelMultipleChoiceField(queryset=_q,**kwargs)
  class Meta:
    model = MeetingMinutes
    exclude = ()

@admin.register(MeetingMinutes)
class MeetingMinutesAdmin(admin.ModelAdmin):
  form = MeetingMinutesForm
  inlines = [ProposalInline]
  fields = ('date','content',('voters_present','inactive_present'),'nonvoters_present')
  filter_horizontal = ('nonvoters_present',)

@admin.register(Officer)
class OfficerAdmin(admin.ModelAdmin):
  form = StaffMemberForm
