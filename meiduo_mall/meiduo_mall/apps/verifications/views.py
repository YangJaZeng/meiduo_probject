from django import http
from django.views import View
from django_redis import get_redis_connection

from meiduo_mall.libs.captcha.captcha import captcha
from verifications import const


class ImageCode(View):
    def get(self, request, uuid):
        """

        :param request:
        :param uuid: 当前用户的唯一id
        :return: image/jpg
        """
        #生成图片验证
        text, image = captcha.generate_captcha()

        #保存图片验证码
        redis_conn = get_redis_connection('verify_code')

        #图形验证码有效期，单位：秒
        redis_conn.setex('img_%s' % uuid, const.IMAGE_COOE_REDIS_EXPIRES, text)

        #响应图片验证码
        return http.HttpResponse(image, content_type='image/jpg')
# Create your views here.
