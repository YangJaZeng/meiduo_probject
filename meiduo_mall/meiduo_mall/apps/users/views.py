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
from goods.models import SKU
from meiduo_mall.utils.response_code import RETCODE
from .models import User, Address
from meiduo_mall.utils.views import LoginRequiredMixin, LoginRequiredJSONMixin
import logging

logger = logging.getLogger('django')


class UserBrowseHistory(LoginRequiredJSONMixin, View):
    """用户浏览记录"""

    def get(self, request):
        """获取用户浏览记录"""
        # 获取Redis存储的sku_id列表信息
        redis_conn = get_redis_connection('history')
        sku_ids = redis_conn.lrange('history_%s' % request.user.id, 0, -1)

        # 根据sku_ids列表数据，查询出商品sku信息
        skus = []
        for sku_id in sku_ids:
            sku = SKU.objects.get(id=sku_id)
            skus.append({
                'id': sku.id,
                'name': sku.name,
                'default_image_url': sku.default_image_url,
                'price': sku.price
            })

        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'skus': skus})

    def post(self, request):
        """保存用户浏览记录"""
        # 接收参数
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')

        # 校验参数:
        try:
            SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return http.HttpResponseForbidden('sku不存在')

        # 保存用户浏览数据
        redis_conn = get_redis_connection('history')
        pl = redis_conn.pipeline()
        user_id = request.user.id

        # 先去重: 这里给 0 代表去除所有的 sku_id
        pl.lrem('history_%s' % user_id, 0, sku_id)
        # 再存储
        pl.lpush('history_%s' % user_id, sku_id)
        # 最后截取: 界面有限, 只保留 5 个
        pl.ltrim('history_%s' % user_id, 0, 4)
        # 执行管道
        pl.execute()

        # 响应结果
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})


class ChangePasswordView(LoginRequiredMixin, View):
    """修改密码"""

    def get(self, request):
        """展示修改密码界面"""
        return render(request, 'user_center_pass.html')

    def post(self, request):
        """实现修改密码逻辑"""

        # 接收参数
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        new_password2 = request.POST.get('new_password2')

        # 校验参数
        if not all([old_password, new_password, new_password2]):
            return http.HttpResponseForbidden('缺少必传参数')

        try:
            request.user.check_password(old_password)
        except Exception as e:
            logger.error(e)
            return render(request, 'user_center_pass.html', {'origin_pwd_errmsg': '原始密码错误'})

        if not re.match(r'^[0-9A-Za-z]{8,20}$', new_password):
            return http.HttpResponseForbidden('密码最少8位，最多20位')

        if new_password != new_password2:
            return http.HttpResponseForbidden('两次输入的密码不一致')

        # 修改密码
        try:
            request.user.set_password(new_password)
            request.user.save()
        except Exception as e:
            logger(e)
            return render(request, 'user_center_pass.html', {'change_pwd_errmsg': '修改密码失败'})

        # 清理状态保持信息
        logout(request)
        response = redirect(reverse('users:login'))
        response.delete_cookie('username')

        # 响应密码修改结果：重定向到登录界面
        return response


class UpdateTitleAddressView(LoginRequiredJSONMixin, View):
    """设置地址标题"""

    def put(self, request, address_id):
        """设置地址标题"""

        # 接收参数：地址标题
        json_dict = json.loads(request.body.decode())
        title = json_dict.get('title')

        try:
            # 查询地址
            address = Address.objects.get(id=address_id)

            # 设置新的地址标题
            address.title = title
            address.save()
        except Exception as e:
            logger.error(e);
            return http.JsonResponse({'code': RETCODE.DBERR,
                                      'errmsg': '设置地址标题失败'})

        # 响应删除地址结果
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': '设置地址表题成功'})


class DefaultAddressView(LoginRequiredJSONMixin, View):
    """设置默认地址"""

    def put(self, request, address_id):
        """设置默认地址"""
        try:
            # 接收参数，查询地址
            address = Address.objects.get(id=address_id)

            # 设置地址为默认地址
            request.user.default_address = address
            request.user.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code': RETCODE.DBERR,
                                      'errmsg': '设置默认地址失败'})

        # 响应设置默认地址结果
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': '设置默认地址成功'})


class UpdateDestroyAddressView(LoginRequiredJSONMixin, View):
    """修改和删除地址"""

    def put(self, request, address_id):
        """修改地址"""

        # 1.接收参数
        json_dict = json.loads(request.body.decode())
        receiver = json_dict.get('receiver')
        province_id = json_dict.get('province_id')
        city_id = json_dict.get('city_id')
        district_id = json_dict.get('district_id')
        place = json_dict.get('place')
        mobile = json_dict.get('mobile')
        tel = json_dict.get('tel')
        email = json_dict.get('email')

        # 2.校验参数
        if not all([receiver, province_id, city_id, district_id, place, mobile]):
            return http.HttpResponseForbidden('缺少必传参数')
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('手机号码错误')
        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return http.HttpResponseForbidden('参数tel错误')
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return http.HttpResponseForbidden('参数email错误')

        # 3.更新地址（保存）
        try:
            Address.objects.filter(id=address_id).update(
                user=request.user,
                title=receiver,
                receiver=receiver,
                province_id=province_id,
                city_id=city_id,
                district_id=district_id,
                place=place,
                mobile=mobile,
                tel=tel,
                email=email
            )
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code': RETCODE.DBERR,
                                      'errmsg': '更新地址失败'})

        # 4.拼接
        address = Address.objects.get(id=address_id)
        address_dict = {
            'id': address.id,
            'title': address.title,
            'receiver': address.receiver,
            'province': address.province.name,
            'city': address.city.name,
            'district': address.district.name,
            'place': address.place,
            'mobile': address.mobile,
            'tel': address.tel,
            'email': address.email
        }

        # 5.返回
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': '更新地址成功',
                                  'address': address_dict})

    def delete(self, request, address_id):
        """删除地址"""
        try:
            # 查询要删除的地址
            address = Address.objects.get(id=address_id)

            # 将地址逻辑删除设置为True
            address.is_deleted = True
            address.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code': RETCODE.DBERR,
                                      'errmsg': '删除地址失败'})

        # 响应删除地址结果
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': '删除地址成功'})


class CreateAddressView(LoginRequiredJSONMixin, View):
    """新增地址"""

    def post(self, request):
        """实现新增地址逻辑"""

        # 获取地址个数
        count = request.user.addresses.count()

        # 判断是否超过地址上限：最多20个
        if count >= 20:
            # RETCODE.THROTTLINGERR:  4002
            return http.JsonResponse({'code': RETCODE.THROTTLINGERR,
                                      'errmsg': '超过地址数量上限'})

        # 接收参数
        json_dict = json.loads(request.body.decode())
        receiver = json_dict.get('receiver')
        province_id = json_dict.get('province_id')
        city_id = json_dict.get('city_id')
        district_id = json_dict.get('district_id')
        place = json_dict.get('place')
        mobile = json_dict.get('mobile')
        tel = json_dict.get('tel')
        email = json_dict.get('email')

        # 校验参数
        if not all([receiver, province_id, city_id, district_id, place, mobile]):
            return http.HttpResponseForbidden('缺少必传参数')
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('参数mobile有误')
        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return http.HttpResponseForbidden('参数tel有误')
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return http.HttpResponseForbidden('参数email有误')

        # 保存地址信息
        try:
            address = Address.objects.create(
                user=request.user,
                title=receiver,
                receiver=receiver,
                province_id=province_id,
                city_id=city_id,
                district_id=district_id,
                place=place,
                mobile=mobile,
                tel=tel,
                email=email
            )

            # 设置默认地址
            if not request.user.default_address:
                request.user.default_address = address
                request.user.save()


        except Exception as e:

            logger.error(e)

            return http.JsonResponse({'code': RETCODE.DBERR,
                                      'errmsg': '新增地址失败'})

            # 新增地址成功，将新增的地址响应给前端实现局部刷新
        address_dict = {
            'id': address.id,
            'title': address.title,
            'receiver': address.receiver,
            'province': address.province.name,
            'city': address.city.name,
            'district': address.district.name,
            'place': address.place,
            'mobile': address.mobile,
            'tel': address.tel,
            'email': address.email
        }

        # 响应保存结果
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': '新增地址成功',
                                  'address': address_dict})


class AddressView(LoginRequiredMixin, View):
    """用户收货地址"""

    def get(self, request):
        """提供地址管理界面"""
        # 获取所有的地址
        addresses = Address.objects.filter(user=request.user, is_deleted=False)

        # 创建空列表
        address_dict_list = []

        # 遍历
        for address in addresses:
            address_dict = {
                'id': address.id,
                'title': address.title,
                'receiver': address.receiver,
                'province': address.province.name,
                'city': address.city.name,
                'district': address.district.name,
                'place': address.place,
                'mobile': address.mobile,
                'tel': address.tel,
                'email': address.email
            }

            # 将默认地址移动到列表最前面
            default_address = request.user.default_address
            if default_address.id == address.id:
                address_dict_list.insert(0, address_dict)
            else:
                address_dict_list.append(address_dict)

        context = {
            'default_address_id': request.user.default_address_id,
            'addresses': address_dict_list
        }

        return render(request, 'user_center_site.html', context)


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


class EmailView(LoginRequiredJSONMixin, View):
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
