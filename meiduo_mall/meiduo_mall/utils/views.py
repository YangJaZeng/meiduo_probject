# 定义一个Mixin扩展类：来帮助判断用户是否登录
from django.contrib.auth.decorators import login_required


class LoginRequiredMixin(object):

    # 重写 as_view方法
    @classmethod
    def as_view(cls, **initkwargs):
        # 调用父类的as_view()方法
        view = super().as_view()
        # 添加装饰器行为：
        return login_required(view)


class LoginRequiredJsonMixin(object):

    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return login_required_json(view)
