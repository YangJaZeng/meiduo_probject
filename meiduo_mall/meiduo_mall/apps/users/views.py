from django.contrib.auth import login
from django.db import DatabaseError
# from django.http import HttpResponse
from django.shortcuts import render, redirect
from django import http
# Create your views here.
from django.urls import reverse
from django.views import View
import re
from django_redis import get_redis_connection
# from users.models import User
from meiduo_mall.utils.response_code import RETCODE
from .models import User


class MobileCountView(View):

    def get(self, request, mobile):
        '''
        接收用户的手机号, 查询, 判断个数,返回
        :param request:
        :param mobile:
        :return:
        '''
        count = User.objects.filter(mobile=mobile).count()

        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'ok',
                                  'count': count})


class UsernameCountView(View):

    def get(self, request, username):
        '''
        获取用户, 查询用户名的数量, 返回前端
        :param request:
        :param username:
        :return:
        '''
        count = User.objects.filter(username=username).count()
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'ok',
                                  'count': count})


class RegisterView(View):

    def get(self, request):
        '''
        定义一个接口,返回注册页面
        :param request:
        :return:
        '''
        return render(request, 'register.html')

    def post(self, request):
        '''
        接收用户发来的注册信息,保存到数据库, 返回状态
        :param request:
        :return:
        '''
        # 1.  接收参数
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        mobile = request.POST.get('mobile')
        sms_code_client = request.POST.get('sms_code')
        allow = request.POST.get('allow')
        print('拿到l')
        print(mobile)
        # 2.  校验参数
        # 2.1 全局校验:
        if not all([username, password, password2, mobile, allow]):
            return http.HttpResponseForbidden('缺少必传参数')
        # 2.2 单个查看:
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return http.HttpResponseForbidden('用户名请输入5-20位')

        if not re.match(r'^[a-zA-Z0-9]{8,20}$', password):
            return http.HttpResponseForbidden('密码请输入8-20位')

        if password != password2:
            return http.HttpResponseForbidden('两次输入的密码不一致')

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('手机号格式不正确')

        if allow != 'on':
            return http.HttpResponseForbidden('请勾选用户协议')
        print('判断了')
        # 对短信验证码进行校验:
        redis_conn = get_redis_connection('verify_code')
        # redis取出的:
        sms_code_server = redis_conn.get('sms_code_%s' % mobile)
        print(sms_code_server)
        if sms_code_server is None:
            print('进去了')
            return render(request, 'register.html', {'sms_code_errmsg': '验证码实效'})
        print('失效了')
        # 对比前后端的验证码:
        if sms_code_client != sms_code_server.decode():
            return render(request, 'register.html', {'sms_code_errmsg': '输入的验证码有误'})

        # 3.  保存到数据库
        try:
            user = User.objects.create_user(username=username,
                                            password=password,
                                            mobile=mobile)
        except DatabaseError:
            print('失败')
            return render(request, 'register.html', {'reigster_errmsg': '写入数据库出错'})

        # 5. 状态保持:  session
        login(request, user)

        # 4.  跳转到首页
        # return http.HttpResponse('保存成功, 跳转还没有做(需要跳转到首页)')

        return redirect(reverse('contents:index'))
