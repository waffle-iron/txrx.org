from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models

from db.models import UserModel

from sorl.thumbnail import get_thumbnail

ITEM_TYPE_CHOICES = (
  ('blog','Blog Post'),
  ('session','Class'),
  ('event','Event'),
  ('thing','Thing'),
  ('video','Video'),
  ('link','Link'),
  ('other','Other'),
)

class FeedItem(UserModel):
  """Items for the front page feed, also will be what all comments are tied to.
  The content_object for a feed item should have an obj.update_feed().
  """
  # obj.update_feed() should set these 4
  title = models.CharField(max_length=256)
  thumbnail = models.ImageField(upload_to='feed_thumbnails')
  item_type = models.CharField(max_length=16,choices=ITEM_TYPE_CHOICES)
  publish_dt = models.DateTimeField()

  datetime = models.DateTimeField(auto_now_add=True)
  votes = models.IntegerField(default=0)
  featured = models.BooleanField(default=False)

  content_type = models.ForeignKey(ContentType)
  object_id = models.PositiveIntegerField()
  content_object = generic.GenericForeignKey('content_type', 'object_id')

  __unicode__ = lambda self: self.title
  def save(self,*args,**kwargs):
    self.publish_dt = self.publish_dt or self.datetime
    super(FeedItem,self).save(*args,**kwargs)

  class Meta:
    unique_together = ('content_type','object_id')
  
  @classmethod
  def get_for_object(clss,obj):
    """Returns a FeedItem for a given object. Object may or may not exist in the database
    (so save() the returned result after adding necessary fields)."""
    content_type = ContentType.objects.get_for_model(obj)
    try:
      return clss.objects.get(object_id=obj.id,content_type=content_type)
    except clss.DoesNotExist:
      return clss(content_type=content_type,object_id=obj.id)

def prep_thumbnail(src):
  return get_thumbnail(src,'100x100',crop='center',quality=99).name

class Like(UserModel):
  feed_item = models.ForeignKey(FeedItem)
  class Meta:
    unique_together = ('user','feed_item')
