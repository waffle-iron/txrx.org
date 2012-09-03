from django.contrib import admin
from django import forms
from course.models import Subject, Course, Section, Session, Enrollment, Term, ClassTime
from lablackey.content.mixins import CKEditorMixin

class SubjectAdmin(admin.ModelAdmin):
  pass

class SectionInline(admin.TabularInline):
  extra = 0
  model = Section

class CourseAdmin(CKEditorMixin, admin.ModelAdmin):
  list_display = ("name",)
  filter_horizontal = ("subjects",)
  #inlines = (SectionInline,)

class ClassTimeInline(admin.TabularInline):
  model = ClassTime

class SectionAdmin(admin.ModelAdmin):
  save_as = True
  list_display = ("__unicode__","prerequisites","requirements")
  list_editable = ("prerequisites","requirements")

class SessionAdmin(admin.ModelAdmin):
  list_display = ("__unicode__","user")
  list_editable = ("user",)
  exclude = ('time_string',)
  extra = 0
  inlines = (ClassTimeInline,)

class EnrollmentAdmin(admin.ModelAdmin):
  list_display = ('user', 'session', )

admin.site.register(Subject,SubjectAdmin)
admin.site.register(Course,CourseAdmin)
admin.site.register(Section,SectionAdmin)
admin.site.register(Enrollment,EnrollmentAdmin)
admin.site.register(Session,SessionAdmin)
admin.site.register(Term)