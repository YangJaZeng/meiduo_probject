import random
import re

# from django.contrib.auth.models import User
from venv import logger

from django.contrib.auth import login
from django.db import DatabaseError
from django import http
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django_redis import get_redis_connection

from meiduo_mall.utils.response_code import RETCODE
from users import constants
from .models import User


class SMSCodeView(View):
    """短信验证码"""

    def get(self, request, mobile):
        """

        :param request:
        :param mobile: 手机号码
        :return: JSON
        """
        # 1.接收参数
        image_code_client = request.GET.get('image_code')
        uuid = request.GET.get('image_code_id')

        # 2.校验参数
        if not all([image_code_client, uuid]):
            return http.JsonResponse({'code': RETCODE.NECESSARYPARAMERR,
                                      'errmsg': '缺少必传参数'})

        # 3.创建连接到redis的对象
        redis_conn = get_redis_connection('verify_code')

        # 4.提取图形验证码
        image_code_server = redis_conn.get('img_%s' % uuid)
        if image_code_server is None:
            # 图形验证码过期或者不存在
            return http.JsonResponse({'code': RETCODE.IMAGECODEERR,
                                      'errmsg': '图形验证码失效'})

        # 5.删除图形验证码，避免恶意侧视图形验证码
        try:
            redis_conn.delete('img_%s' % uuid)
        except Exception as e:
            logger.error(e)

        # 6.对比图形验证码
        image_code_server = image_code_server.decode()  # bytes转字符串
        if image_code_client.lower() != image_code_server.lower():  # 转小写后比较
            return http.JsonResponse({'code': RETCODE.IMAGECODEERR,
                                      'errmsg': '输入图形验证码错误'})

        # 7. 生成短信验证码：生成6位数验证码
        sms_code = '%06d' % random.randint(0, 999999)
        logger.info(sms_code)

        # 8.保存短信验证码
        # 短信验证码有效期， 单位：秒
        # SMS_CODE_REDIS_EXPIRES = 300
        redis_conn.setex('sms_%' % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)

        # 9.发送短信验证码
        # 短信模板
        # SMS_CODE_REDIS_EXPIRES // 60 = 5min
        # SEND_SMS_TEMPLATE_ID = 1



        # 10.响应结果
        return http.JsonResponse({'code':RETCODE.OK,
                                  'errmsg':'发送短信成功'})


class MobileCountView(View):
    """判断手机号是否重复"""

    def get(self, request, mobile):
        count = User.objects.filter(mobile=mobile).count()
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'ok',
                                  'count': count})


class UsernameCountView(View):
    """判断用户名是否重复"""

    def get(self, request, username):
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
        """
        实现用户注册
        :param request: 请求对象
        :return: 注册结果
        """
        # 接收参数
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get("password2")
        mobile = request.POST.grt('mobile')
        # TODO sms_code 还没有做
        allow = request.POST.get('allow')

        # 校验参数
        # 判断参数是否齐全
        if not all([username, password, password2, mobile, allow]):
            return http.HttpResponseForbidden('缺少必传参数')
        # 判断用户名是否是5-20个字符
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return http.HttpResponseForbidden('请输入5-20个字符的用户名')
        # 判断密码是否是8-20个数字和字母
        if not re.match(r'^[a-zA-Z0-9]{8,20}', password):
            return http.HttpResponseForbidden('请输入8-20位的密码')
        # 判断两次密码是否一致
        if password != password2:
            return http.HttpResponseForbidden('两次密码不一致')
        # 判断手机号是否合法
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('请输入正确的手机号码')
        # 判断是否勾选用户协议
        if allow != 'on':
            return http.HttpResponseForbidden('请勾选用户协议')

        # 保存注册数据
        try:
            # create_user函数可以加密密码
            user = User.objects.create_user(username=username, password=password, mobile=mobile)
        except DatabaseError:
            return render(request, 'register.html', {'register_errmsg': '注册失败'})

        login(request, user)
        # 响应注册结果
        return redirect(reverse('contents:index'))

# Create your views here.
