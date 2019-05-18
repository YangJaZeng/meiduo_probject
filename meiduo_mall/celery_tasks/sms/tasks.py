# bind：保证task对象会作为第一个参数自动传入
# name：异步任务别名
# retry_backoff：异常自动重试的时间间隔 第n次(retry_backoff×2^(n-1))s
# max_retries：异常自动重试次数的上限
from venv import logger

from celery_tasks.yuntongxun.ccp_sms import CCP
from verifications import const
from celery_tasks.main import celery_app


@celery_app.task(bind = True, name='send_sms_code', retry_backoff=3)
def send_sms_code(self, mobile, sms_code):
    """
    异步发送短信
    :param self:
    :param mobile:
    :param sms_code:
    :return:
    """

    try:
        # 调用CCP() 发送短信，并传递相关参数
        result = CCP().send_template_sms(mobile,
                                         [sms_code, const.IMAGE_COOE_REDIS_EXPIRES // 60],
                                         const.SEND_SMS_TEPLATE_ID)
    except Exception as e:
        # 如果发送过程出错，打印错误日志
        logger.error(e)

        # 有异常自动重试三次
        raise self.retry(exc=e, max_retries=3)

        # 如果发送成功，rend_ret 为0
    if result != 0:
        raise self.retry(exc=Exception('发送短信失败', max_retries=3))

    return result
