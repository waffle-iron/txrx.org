from django.conf import settings
from django.conf.urls import url, patterns, include
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import password_reset
from django.contrib.flatpages.models import FlatPage
from django.contrib.sitemaps.views import sitemap

from main.sitemaps import sitemaps
from main.feeds import AllFeed
from main import views as main_views

import os

_urls = lambda *ns: [url(r'^%s/'%n, include('%s.urls'%n, namespace=n, app_name=n)) for n in ns]

_pages = [
  'checkin',
  'checkout',
  'todays-checkins',
  'my-permissions',
  'needed-sessions',
  'rooms',
  'rfid',
  'toolmaster',
  'week-hours',
]

urlpatterns = patterns(
  '',
  url(r'^(%s)/$'%('|'.join(_pages)),main_views.beta),
  url(r'^$',main_views.index,name="home"),
  url(r'^sitemap\.xml$', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
  url(r'^admin/', include(admin.site.urls)),
  url(r'^blog/',include('blog.urls')),
  url(r'arst/(?P<pk>\d+)',main_views.intentional_500,name="order_detail"),
  url(r'^(\d{4})/(\d{1,2})/(\d{1,2})/([^/]+)/','blog.views.post_redirect'),
  url(r'^500/$',main_views.intentional_500),
  url(r'^event/',include('event.urls',namespace="event",app_name="event")),
  url(r'^media_files/',include('media.urls')),
  url(r'^shop/',include('store.urls')),
  url(r'^product_is_a_fail/(.*)/$',main_views.index,name="product_detail"),
  url(r'^me/$',login_required(main_views.beta)),

  # comments and javascript translation
  url(r'^comments/',include('mptt_comments.urls')),
  url(r'^jsi18n/(?P<packages>\S+?)/$', 'django.views.i18n.javascript_catalog'),
  url(r'^rss/$', AllFeed()),
  url(r'^favicon.ico$',main_views.predirect,
      kwargs={'url':getattr(settings,'FAVICON','/static/favicon.ico')}),
  url(r'^sculpturemonth$',main_views.predirect,
      kwargs={'url':"/classes/221/3d-modeling-with-rhino/?rhino10"}),
  url(r'^thing/$','thing.views.thing_index',name='thing_index'),
  url(r'^thing/add/$','thing.views.add_thing',name='add_thing'),
  url(r'^thing/(\d+)/([\w\d\-\_]+)/$','thing.views.thing_detail',name='thing_detail'),
  url(r'^gfycat/$',main_views.gfycat,name='gfycat'),
  url(r'^tools/',include('tool.urls')),
  url('', include('social.apps.django_app.urls', namespace='social')),
  url(r'perfect-programming',main_views.intentional_500),
  url(r'^classes/', include('course.urls',namespace='course',app_name='course')),
  url(r'^tx/rx/ipn/handler/', include('paypal.standard.ipn.urls')),
  url(r'^tx/rx/return/$','course.views.paypal_return',name='paypal_redirect'),
  url(r'^contact/$','contact.views.contact',name='contact'),
  url(r'^contact/(\w+).(\w+)_(\d+)-(.*).png$','contact.views.tracking_pixel',name="tracking_pixel"),
  url(r'^dxfviewer/$','geo.views.dxfviewer',name='dxfviewer'),
  url(r'^geo/events.json','geo.views.events_json'),
  url(r'^geo/locations.json$','geo.views.locations_json'),
  url(r'^checkin_ajax/$', 'user.views.checkin_ajax', name='checkin_ajax'),
  url(r'^add_rfid/$', 'user.views.add_rfid', name='add_rfid'),
  url(r'^user.json','user.views.user_json'),
  url(r'^todays_checkins.json','user.views.todays_checkins_json'),
  url(r'^redtape/',include("redtape.urls")),
)

def activate_user(target):
  def wrapper(request,*args,**kwargs):
    from django.contrib.auth import get_user_model
    model = get_user_model()
    if request.REQUEST.get('email',None):
      try:
        user = model.objects.get(email=request.REQUEST.get('email'))
        user.is_active = True
        user.save()
      except model.DoesNotExist:
        pass
    return target(request,*args,**kwargs)
  return wrapper

#auth related
urlpatterns += patterns(
  '',
  url(r'^accounts/settings/$','membership.views.user_settings',name='account_settings'),
  url(r'^accounts/register/$','membership.views.register'),
  url(r'^accounts/', include('registration.urls')),
  url(r'^auth/password_reset/$',activate_user(password_reset)),
  url(r'^auth/',include('django.contrib.auth.urls')),
  url(r'^force_login/(\d+)/$', main_views.force_login),
  url(r'^api/remove_rfid/$','user.views.remove_rfid'),
  url(r'^api/change_rfid/$','user.views.set_rfid'),
  url(r'^api/',include("api.urls")),
  url(r'^api/change_(headshot|id_photo)/$','user.views.change_headshot'),
  url(r'^api-token-auth/', 'rest_framework_jwt.views.obtain_jwt_token'),
)

if hasattr(settings,"STAFF_URL"):
  urlpatterns += patterns("", url(settings.STAFF_URL[1:],'user.views.hidden_image'))

#membership urls
urlpatterns += patterns(
  'membership.views',
  url(r'^join-us/$','join_us'),
  url(r'^minutes/$', 'minutes_index', name='meeting_minutes_index',),
  url(r'^minutes/(\d+-\d+-\d+)/$', 'minutes', name='meeting_minutes',),
  url(r'^roland_email/$','roland_email',name='roland_email'),
  url(r'^roland_email/(\d+)/(\d+)/(\d+)/$','roland_email',name='roland_email'),
  url(r'^api/users/$','user_emails'),
  url(r'^api/courses/$','course_names'),
  url(r'^instructors/$','member_index',name='instructor_index'),
  url(r'^instructors/([^/]+)/$','member_detail',name='instructor_detail'),
  url(r'^u/$','member_index',name='member_index'),
  url(r'^u/([^/]+)/$','member_detail',name='member_detail'),
  url(r'^officers/$', 'officers', name='officers'),
  url(r'^analysis/$', 'analysis', name='analysis'),
  url(r'^force_cancel/(\d+)/$','force_cancel',name="force_cancel"),
  url(r'^flag_subscription/(\d+)/$','flag_subscription',name="flag_subscription"),
  url(r'^containers/$','containers'),
  url(r'^update_flag_status/(\d+)/$','update_flag_status',name='update_flag_status'),
  url(r'^update_flag_status/(\d+)/([\w\d\-\_]+)/$','update_flag_status',name='update_flag_status'),
  url(r'^rfid_access.json$','door_access',name='door_access_json'),
  url(r'^rfid_permission_table/$','rfid_permission_table',name='rfid_permission_table'),
  url(r'^membership/container/(\d+)/','container',name='container'),
)

#notify urls
urlpatterns += patterns(
  'notify.views',
  url(r'^notify_course/(\d+)/$','notify_course',name='notify_course'),
  url(r'^clear_notification/(notify_course)/(\d+)/(\d+)/$','clear_notification',name='clear_notification'),
  url(r'^unsubscribe/(notify_course|global|comments|classes|sessions)/(\d+)/$',
      'unsubscribe', name='unsubscribe'),
)

# todo
urlpatterns += patterns(
  '',
  (r'^survey/$',main_views.survey),
)

flatpages = [page.url[1:] for page in FlatPage.objects.all()]
fps = '|'.join(flatpages)

# flat pages
urlpatterns += patterns(
  '',
  url(r'^(about-us)/$',main_views.to_template),
  url(r'(%s)'%fps,'django.contrib.flatpages.views.flatpage',name='map'),
)

from django.views.static import serve
from django.contrib.auth.decorators import user_passes_test

is_superuser = lambda user:user.is_superuser
urlpatterns += patterns(
    '',
    url(r'^media/(?P<path>signatures/.*)$',user_passes_test(is_superuser)(serve),
        {'document_root': settings.MEDIA_ROOT,'show_indexes': False}),
)
if settings.DEBUG:
  urlpatterns += patterns(
    '',
    url(r'^media/(?P<path>.*)$','django.views.static.serve',
        {'document_root': settings.MEDIA_ROOT,'show_indexes': True}),
  )

# Turn me on to enable "maintenance mode"
if False:
  urlpatterns = [
    url(r'^(maintenance)/$',main_views.beta),
    url(r'^admin/', include(admin.site.urls)),
    url(r'',main_views.predirect,kwargs={'url': "/maintenance/"},name="logout"),
  ]
