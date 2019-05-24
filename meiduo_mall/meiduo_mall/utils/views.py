# 定义一个Mixin扩展类：来帮助判断用户是否登录
from django import http
from django.contrib.auth.decorators import login_required
from django.utils.decorators import wraps

from meiduo_mall.utils.response_code import RETCODE


class LoginRequiredMixin(object):

    # 重写 as_view方法
    @classmethod
    def as_view(cls, **initkwargs):
        # 调用父类的as_view()方法
        view = super().as_view()
        # 添加装饰器行为：
        return login_required(view)


def login_required_json(view_func):
    """
    判断用户是否登录的装饰器，并返回 json
    :param view_func: 被装饰的视图函数
    :return: json、view_func
    """

    # 恢复 view_func 的名字和文档
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # 如果用户未登录，返回json数据
        if not request.user.is_authenticated():
            return http.JsonResponse(({'code': RETCODE.SESSIONERR,
                                       'errmsg': '用户未登录'}))
        else:
            # 如果用户登录，进入到 view_func 中
            return view_func(request, *args, **kwargs)

    return wrapper


class LoginRequiredJSONMixin(object):

    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return login_required_json(view)
