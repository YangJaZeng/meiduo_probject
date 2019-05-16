from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^register/$', views.RegisterView.as_view(), name='register'),
    url(r'^usernames/(?P<username>\w{5,20})/count/$', views.UsernameCountView.as_view(), name='register'),
    url(r'^usernames/mobiles/(?P<mobile>1[3-9]\d{9})/count/$', views.MobileCountView.as_view(), name='register'),

]