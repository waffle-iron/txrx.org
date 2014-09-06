from django.conf import settings
from django.contrib.auth.models import get_user_model

from db.utils import get_or_none

class EmailOrUsernameModelBackend(object):
  def authenticate(self, username=None, password=None):
    User = get_user_model()
    user = get_or_none(User,email=username) or get_or_none(User,username=username)
    if user and user.check_password(password):
      return user
    return None

  def get_user(self, user_id):
    User = get_user_model()
    try:
      return User.objects.get(pk=user_id)
    except User.DoesNotExist:
      return None
