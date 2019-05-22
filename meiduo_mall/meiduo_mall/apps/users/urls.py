from django.conf.urls import url

from . import views

urlpatterns = [
    # 注册
    url(r'^register/$', views.RegisterView.as_view(), name='register'),
    # 验证用户名
    url(r'^usernames/(?P<username>\w{5,20})/count/$', views.UsernameCountView.as_view()),
    # 验证号码
    url(r'^mobiles/(?P<mobile>1[3-9]\d{9})/count/$', views.MobileCountView.as_view()),
    # 登录
    url(r'^login/$', views.LoginView.as_view(), name='login'),
    # 退出登录
    url(r'^logout/$', views.LogoutView.as_view(), name='logout'),
    # 用户中心
    url(r'^info/$', views.UserInfoView.as_view(), name='info'),
    # 添加邮箱
    url(r'^emails/$', views.EmailView.as_view()),
    # 验证邮箱
    url(r'^emails/verification/$', views.VerifyEmailView.as_view()),
]
