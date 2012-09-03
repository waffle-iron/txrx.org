from django import forms
from django.contrib import admin
from models import Tool, ToolPhoto, ToolLink, ToolVideo, Lab
from lablackey.content.mixins import CKEditorMixin
from lablackey.photo.admin import PhotoAdmin
from lablackey.db.admin import SlugModelAdmin

class LabAdmin(SlugModelAdmin):
  list_display = ("__unicode__","order")
  list_editable = ("order",)

class ToolPhotoInline(admin.TabularInline):
  extra = 0
  fields = ("caption_override","photo","thumbnail_")
  readonly_fields = ("thumbnail_",)
  model = ToolPhoto
  def save_model(self, request, obj, form, change):
    if obj.uploader_id is 1:
      obj.uploader = request.user
    obj.save()
  def thumbnail_(self, photo):
    from sorl.thumbnail.helpers import ThumbnailError
    try:
      return photo.thumbnail_link_128x128
    except ThumbnailError:
      return ''
  thumbnail_.allow_tags = True

class ToolLinkInline(admin.TabularInline):
  extra = 0
  model = ToolLink
  fields = ("title","url","order")

class ToolVideoInline(admin.StackedInline):
  extra = 0
  model = ToolVideo
  fieldsets = ((None, {'fields': ("title","thumbnail","project","order")}),
         (None, {'fields': ("embed_code",)})
         )

class ToolAdmin(CKEditorMixin, SlugModelAdmin):
  list_display = ("__unicode__","order")
  list_editable = ("order",)
  inlines = (ToolLinkInline,ToolPhotoInline,ToolVideoInline)

admin.site.register(Lab,LabAdmin)
admin.site.register(Tool,ToolAdmin)