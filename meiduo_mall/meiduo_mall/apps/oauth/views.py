from venv import logger

from django import http
from django.conf import settings
from django.views import View
from QQLoginTool.QQtool import OAuthQQ
from meiduo_mall.utils.models import BaseModel
from django.db import models

from utils.response_code import RETCODE


class QQUserView(View):
    """用户扫码登录的回调处理"""

    def get(self, request):
        """oauth2.0认证"""
        # 接收Authorization Code
        code = request.GET.get('code')
        if not code:
            return http.HttpResponseForbidden('缺少code')

        # 创建工具对象
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URL)

        try:
            # 携带 code 向 QQ服务器 请求 access_token(code)
            access_token = oauth.get_access_token(code)

            # 携带 access_token 向 QQ服务器 请求 openid
            openid = oauth.get_open_id(access_token)

        except Exception as e:
            # 如果上面获取 openid 出错，则验证失败
            logger.error(e)
            # 返回结果
            return http.HttpResponseServerError('OAuth2.0认证失败')
        pass


class QQURLView(View):
    """
    提供QQ登录页面网址
    https://graph.qq.com/oauth2.0/authorize?
    response_type=code&
    client_id=xxx&
    redirect_uri=xxx&
    state=xxx
    """

    def get(self, request):
        # next 表示从哪个页面进入到登录界面，将来登录成功后，就自动回到那个页面
        next = request.GET.get('next')

        # 获取 QQ 登录页面网址
        # 创建 QAuthQQ 类对象
        oauth = OAuthQQ(client_id=settings.QQ_CLTENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URL,
                        state=next)

        # 调用对象的获取 qq 地址方法
        login_url = oauth.get_qq_url()

        # 返回登录地址
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'OK',
                                  'login_url': login_url})


class OAuthQQUser(BaseModel):
    """qq登录用户数据"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, verbose_name='用户')
    openid = models.CharField(max_length=64, verbose_name='openid', db_index=True)

    class Meta:
        db_table = 'tb_oauth_qq'
        verbose_name = 'QQ登录用户数据'
        verbose_name_plural = verbose_name
# Create your views here.
