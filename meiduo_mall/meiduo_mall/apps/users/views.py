import json

from django.contrib.auth import login, authenticate, logout
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
from meiduo_mall.utils.views import LoginRequiredMixin
import logging

logger = logging.getLogger('django')


class VerifyEmailView(View):
    """验证邮箱"""

    def get(self, request):

        # 接收参数
        token = request.GET.get('token')

        # 校验参数
        if not token:
            return http.HttpResponseForbidden('缺少token')

        # 使用封装好的函数 将token解码
        user = User.check_verify_email_token(token)
        if not user:
            return http.HttpResponseForbidden('无效的token')

        # 修改 email_active 的值为 True
        try:
            user.email_active = True
            user.save()
        except Exception as e:
            logger.error(e)
            return http.HttpResponseServerError('邮件激活失败')

        # 返回结果
        return redirect(reverse('users:info'))


class EmailView(View):
    """添加邮箱"""

    def put(self, request):
        """实现添加邮箱逻辑"""
        # 接收参数
        json_dict = json.loads(request.body.decode())
        email = json_dict['email']

        # 校验参数
        if not email:
            return http.HttpResponseForbidden('缺少必传参数')
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return http.HttpResponseForbidden('参数email有误')

        # 赋值 email 字段
        try:
            request.user.email = email
            request.user.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '添加邮箱失败'})

        # 导入:
        from celery_tasks.email.tasks import send_verify_email
        # 异步发送验证邮件
        verify_url = request.user.generate_verify_email_url()

        # 发送验证链接:
        send_verify_email.delay(email, verify_url)

        # 响应添加邮箱结果
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '添加邮箱成功'})


class UserInfoView(LoginRequiredMixin, View):
    """用户中心"""

    def get(self, request):
        """提供个人信息界面"""
        # 如果使用该方法, 它的用法如下所示:
        # 进行判断: 是否登录验证
        # if request.user.is_authenticated():
        #     # 如果登录, 则正常加载用户中心页面
        #     return render(request, 'user_center_info.html')
        # else:
        #     # 否则, 进入登录页面,进行登录
        #     return redirect(reverse('users:login'))

        # 将验证用户的信息进行拼接
        context = {
            'username': request.user.username,
            'mobile': request.user.mobile,
            'email': request.user.email,
            'email_active': request.user.email_active
        }

        return render(request, 'user_center_info.html', context=context)


class LogoutView(View):
    """退出登录"""

    def get(self, request):
        """实现退出登录逻辑"""

        # 清理 session
        logout(request)

        # 退出登录，重定向到登录页面
        response = redirect(reverse('contents:index'))

        # 退出登录是清除 cookie 中的username
        response.delete_cookie('username')

        # 返回响应
        return response


class LoginView(View):

    def get(self, request):
        """
        用户登录
        :param request:
        :return: 返回登陆页面
        """
        return render(request, 'login.html')

    def post(self, request):
        """
        实现登录逻辑
        :param request:请求对象
        :return: 登录结果
        """
        # 1.接收参数
        username = request.POST.get('username')
        password = request.POST.get('password')
        remembered = request.POST.get('remembered')

        # 2.校验参数
        # 判断参数是否齐全
        # 这里注意：remembered 这个参数可以是 None 或者是 ‘no’
        # 所以我们不对它是否存在进行判断
        if not all([username, password]):
            return http.HttpResponseForbidden('缺少必传参数')

        # 判断用户名是否是5-20个字符
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return http.HttpResponseForbidden('请输入正确的用户名或手机号')

        # 判断密码是否是8-20个数字
        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return http.HttpResponseForbidden('密码最少8位，最长20位')

        # 认证登录用户 authenticate 是django自带的认证用户方法,返回用户名
        user = authenticate(username=username, password=password)
        if user is None:
            return render(request, 'login.html', {'account_errmsg': '用户名或密码错误'})

        # 实现状态保持
        login(request, user)
        # 设置状态保持的周期
        if remembered != 'on':
            request.session.set_expiry(0)
        else:
            request.session.set_expiry(None)

        # 获取跳转过来的地址
        next = request.GET.get('next')

        # 判断参数是否存在
        if next:
            # 如果是从别的页面跳转过来的, 则重新跳转到原来的页面
            response = redirect(next)
        else:
            # 生成响应对象
            # 如果不是从别的页面跳转过来的，就重定向到首页
            response = redirect(reverse('contents:index'))
        # 在响应对象中设置用户名信息
        # 将用户名写入到 cookie，有效期15天
        response.set_cookie('username', user.username, max_age=3600 * 24 * 15)

        # 返回响应结果
        return response

        # 响应登录结果(重定向到首页)
        # return redirect(reverse('contents:index'))


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

        # 对短信验证码进行校验:
        redis_conn = get_redis_connection('verify_code')
        # redis取出的:
        sms_code_server = redis_conn.get('sms_code_%s' % mobile)

        if sms_code_server is None:
            return render(request, 'register.html', {'sms_code_errmsg': '验证码实效'})

        # 对比前后端的验证码:
        if sms_code_client != sms_code_server.decode():
            return render(request, 'register.html', {'sms_code_errmsg': '输入的验证码有误'})

        # 3.  保存到数据库
        try:
            user = User.objects.create_user(username=username,
                                            password=password,
                                            mobile=mobile)
        except DatabaseError:

            return render(request, 'register.html', {'reigster_errmsg': '写入数据库出错'})

        # 5. 状态保持:  session
        login(request, user)

        # 生成响应对象
        response = redirect(reverse('contents:index'))

        # 在响应对象中设置用户名信息
        # 将用户名写入到 cookie， 有效期15天
        response.set_cookie('username', user.username, max_age=3600 * 24 * 15)
        # 返回响应结果
        return response

        # 4.  跳转到首页
        # return http.HttpResponse('保存成功, 跳转还没有做(需要跳转到首页)')

        # return redirect(reverse('contents:index'))
