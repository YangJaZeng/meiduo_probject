from django import http
from django.views import View
import random
from meiduo_mall.libs.captcha.captcha import captcha
from meiduo_mall.libs.yuntongxun.ccp_sms import CCP
from meiduo_mall.utils.response_code import RETCODE
from verifications import const
from venv import logger
from django_redis import get_redis_connection
# 导入日志
import logging
# 日志器
logging = logging.getLogger('django')


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

        # 8.保存短信验证码,保存到redis中
        # 短信验证码有效期， 单位：秒
        # SMS_CODE_REDIS_EXPIRES = 300
        redis_conn.setex('sms_code_%' % mobile, const.IMAGE_COOE_REDIS_EXPIRES, sms_code)

        # 9.发送短信验证码
        # 短信模板
        # SMS_CODE_REDIS_EXPIRES // 60 = 5min
        # SEND_SMS_TEMPLATE_ID = 1
        CCP().send_template_sms(mobile, [sms_code, 5], 1)

        # 10.响应结果
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': '发送短信成功'})

# 图形验证码

class ImageCode(View):

    def get(self, request, uuid):
        """

        :param request:
        :param uuid: 当前用户的唯一id
        :return: image/jpg
        """
        # 生成图片验证
        text, image = captcha.generate_captcha()

        # 保存图片验证码
        redis_conn = get_redis_connection('verify_code')

        # 图形验证码有效期，单位：秒
        redis_conn.setex('img_%s' % uuid, const.IMAGE_COOE_REDIS_EXPIRES, text)

        # 响应图片验证码
        return http.HttpResponse(image, content_type='image/jpg')
# Create your views here.
