from celery import Celery
import os

# 全局django环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meiduo_mall.settings.dev")

# 用Celery创建对象
celery_app = Celery('meiduo')

celery_app.config_from_object('celery_tasks.config')

# 自动注册 celery 任务
celery_app.autodiscover_tasks(['celery_tasks.sms', 'celery_tasks.email'])
