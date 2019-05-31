import base64
import json
import pickle

from django import http
from django.shortcuts import render
from django.views import View
from django_redis import get_redis_connection

from goods.models import SKU
from utils.response_code import RETCODE


class CartsSimpleView(View):
    """商品页面右上角购物车"""

    def get(self, request):
        # 判断用户是否登录
        user = request.user
        if user.is_authenticated:
            # 已登录
            redis_conn = get_redis_connection('carts')
            item_dict = redis_conn.hgetall('carts_%s' % user.id)
            cart_selected = redis_conn.smembers('selected_%s' % user.id)

            # 将redis 中的两个数据统一格式，跟 cookie 中的格式一致，方便统一查询
            cart_dict = {}
            for sku_id, count in item_dict.items():
                cart_dict[int(sku_id)] = {
                    'count': int(count),
                    'selected': sku_id in cart_selected
                }

        else:
            # 未登录
            cookie_cart = request.COOKIES.get('carts')
            if cookie_cart:
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))
            else:
                cart_dict = {}

        # 构造简单购物车 JSON数据
        cart_skus = []
        sku_ids = cart_dict.keys()
        skus = SKU.objects.filter(id__in=sku_ids)
        for sku in skus:
            cart_skus.append({
                'id': sku.id,
                'name': sku.name,
                'count': cart_dict.get(sku.id).get('count'),
                'default_image_url': sku.default_image_url
            })

        # 返回
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'ok',
                                  'cart_skus': cart_skus})


class CartsSelectAllView(View):
    """全选购物车"""

    def put(self, request):

        # 接收参数
        json_dict = json.loads(request.body.decode())
        selected = json_dict.get('selected', True)

        # 校验参数
        if selected:
            if not isinstance(selected, bool):
                return http.HttpResponseForbidden('参数selected有误')

        # 判断用户是否登录
        user = request.user
        if user is not None and user.is_authenticated:
            # 用户已登录
            # 连接redis数据
            redis_conn = get_redis_connection('carts')
            item_dict = redis_conn.hgetall('carts_%s' % user.id)
            sku_ids = item_dict.keys()

            # 判断selected是True还是False
            if selected:
                # 全选
                redis_conn.sadd('selected_%s' % user.id, *sku_ids)
            else:
                # 取消全选
                redis_conn.srem('selected_%s' % user.id, *sku_ids)

            return http.JsonResponse({'code': RETCODE.OK,
                                      'errmsg': '全选购物车成功'})

        else:
            # 用户未登录
            cookie_cart = request.COOKIES.get('carts')
            response = http.JsonResponse({'code': RETCODE.OK,
                                          'errmsg': '全选购物车成功'})

            if cookie_cart:
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))

                for sku_id in cart_dict:
                    cart_dict[sku_id]['selected'] = selected
                cart_data = base64.b64encode(pickle.dumps(cart_dict)).decode()

                response.set_cookie('carts', cart_data)

        return response


class CartsView(View):
    """购物车管理"""

    def delete(self, request):
        """删除购物车数据"""

        # 接收参数
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')

        # 校验参数 判断sku_id 是否存在
        try:
            SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return http.HttpResponseForbidden('商品不存在')

        # 判断用户是否登录
        user = request.user
        if user is not None and user.is_authenticated:
            # 用户登录，删除redis购物车
            redis_conn = get_redis_connection('carts')

            # 创建管道
            pl = redis_conn.pipeline()

            # 删除键， 就等价于删除了整条记录
            pl.hdel('carts_%s' % user.id, sku_id)
            pl.srem('selected_%s' % user.id, sku_id)

            # 执行管道
            pl.execute()

            # 删除结束后， 没有响应的数据，只需要响应状态码即可
            return http.JsonResponse({'code': RETCODE.OK,
                                      'errmsg': '删除购物车成功'})
        else:
            # 用户未登录，删除cookie购物车
            cookie_cart = request.COOKIES.get('carts')

            # 判断数据是否存在
            if cookie_cart:
                # 存在就解码
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))
            else:
                # 不存在就新建
                cart_dict = {}

            # 创建响应对象
            response = http.JsonResponse({'code': RETCODE.OK,
                                          'errmsg': '删除购物车成功'})
            if sku_id in cart_dict:
                del cart_dict[sku_id]
                # 加密
                cart_data = base64.b64encode(pickle.dumps(cart_dict)).decode()
                # 将数据写入cookie中
                response.set_cookie('carts', cart_data)

            # 返回
            return response

    def put(self, request):
        """修改购物车"""

        # 接收参数
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        count = json_dict.get('count')
        selected = json_dict.get('selected')
        # 校验参数
        # 判断参数是否齐全
        if not all([sku_id, count, selected]):
            return http.HttpResponseForbidden('缺少必传参数')

        # 判断sku_id是否存在
        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return http.HttpResponseForbidden('商品sku_id不存在')

        # 判断count是否为数字
        try:
            count = int(count)
        except Exception:
            return http.HttpResponseForbidden('count数据类型错误')

        # 判断selected是否为bool值
        if selected:
            if not isinstance(selected, bool):
                return http.HttpResponseForbidden('selected数据类型错误')

        user = request.user
        # 判断用户是否登录
        if user.is_authenticated:
            # 用户已登录，修改redis购物车
            redis_conn = get_redis_connection('carts')

            # 创建管道
            pl = redis_conn.pipeline()
            # 直接覆盖
            pl.hset('carts_%s' % user.id, sku_id, count)
            # 是否选中
            if selected:
                pl.sadd('selected_%s' % user.id, sku_id)
            else:
                pl.srem('selected_%s' % user.id, sku_id)
            # 执行管道
            pl.execute()

            # 拼接数据
            cart_sku = {
                'id': sku_id,
                'count': count,
                'selected': selected,
                'name': sku.name,
                'default_image_url': sku.default_image_url,
                'price': sku.price,
                'amount': sku.price * count
            }

            # 返回
            return http.JsonResponse({'code': RETCODE.OK,
                                      'errmsg': '修改购物车成功',
                                      'cart_sku': cart_sku})

        else:
            # 用户未登录，修改cookie购物车
            cookie_cart = request.COOKIES.get('carts')
            if cookie_cart:
                # 有就解码
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))
            else:
                # 没有就创建
                cart_dict = {}

            # 直接覆盖
            cart_dict[sku_id] = {
                'count': count,
                'selected': selected
            }

            # 加密
            cart_data = base64.b64encode(pickle.dumps(cart_dict)).decode()

            # 拼接数据
            cart_sku = {
                'id': sku.id,
                'count': count,
                'selected': selected,
                'name': sku.name,
                'default_image_url': sku.default_image_url,
                'price': sku.price,
                'amount': sku.price * count

            }

            # 返回
            response = http.JsonResponse({'code': RETCODE.OK,
                                          'errmsg': '修改购物车成功',
                                          'cart_sku': cart_sku})
            # 写入cookie中
            response.set_cookie('carts', cart_data)

            return response

    def get(self, request):
        """展示购物车界面"""

        # 拿取用户
        user = request.user

        # 判断用户是否登录
        if user.is_authenticated:
            # 用户以登录，查询redis购物车

            # 连接redis数据库
            redis_conn = get_redis_connection('carts')

            # 获取redis 购物车中的所有数据
            item_dict = redis_conn.hgetall('carts_%s' % user.id)

            # 获取 redis 中的状态
            cart_selected = redis_conn.smembers('selected_%s' % user.id)

            # 将 redis 中的数据构造成跟 cookie中的格式一样
            # 方便统一查询出商品的图片，名字，数量，状态等信息
            cart_dict = {}
            # 遍历拼接数据
            for sku_id, count in item_dict.items():
                cart_dict[int(sku_id)] = {
                    'count': int(count),
                    'selected': sku_id in cart_selected
                }
        else:
            # 用户未登录，查询cookies购物车
            cookie_cart = request.COOKIES.get('carts')
            if cookie_cart:
                # 将cart_str转成bytes,再将bytes转成base64的bytes,
                # 最后将bytes转字典
                cart_dict = pickle.loads(base64.b64decode(cookie_cart.encode()))
            else:
                cart_dict = {}

        # 构造购物车渲染数据
        sku_ids = cart_dict.keys()
        skus = SKU.objects.filter(id__in=sku_ids)
        cart_skus = []
        for sku in skus:
            cart_skus.append({
                'id': sku.id,
                'name': sku.name,
                'count': cart_dict.get(sku.id).get('count'),
                'selected': str(cart_dict.get(sku.id).get('selected')),  # 将True，转'True'，方便json解析
                'default_image_url': sku.default_image_url,
                'price': str(sku.price),  # 从Decimal('10.2')中取出'10.2'，方便json解析
                'amount': str(sku.price * cart_dict.get(sku.id).get('count')),
            })

        context = {

            'cart_skus': cart_skus,
        }

        # 渲染购物车页面
        return render(request, 'cart.html', context)

    def post(self, request):
        """添加商品到购物车"""

        # 接收参数
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        count = json_dict.get('count')
        selected = json_dict.get('selected', True)

        # 校验参数
        if not all([sku_id, count]):
            return http.HttpResponseForbidden('缺少必传参数')

        # 判断sku_id是否存在 (需要使用数据库，需要try)
        try:
            SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return http.HttpResponseForbidden('sku错误')

        # 判断count是否为数字,(也有可能出错，需要使用try)
        try:
            count = int(count)
        except Exception:
            return http.HttpResponseForbidden('参数count错误')

        # 判断selected是否为bool值
        if selected:
            if not isinstance(selected, bool):
                return http.HttpResponseForbidden('参数selected类型错误')

        # 判断用户是否登录
        if request.user.is_authenticated:
            # 用户已登录，操作redis购物车

            # 连接redis数据库
            redis_conn = get_redis_connection('carts')

            # 创建管道
            pl = redis_conn.pipeline()

            # 新增购物车数据( hincrby() 保存哈希类型，并可是实现累加)
            pl.hincrby('carts_%s' % request.user.id,
                       sku_id,
                       count)

            # 新增选中的状态
            if selected:
                # selected 保存在see类型中
                pl.sadd('selected_%s' % request.user.id,
                        sku_id)

            # 执行管道
            pl.execute()

            # 返回
            return http.JsonResponse({'code': RETCODE.OK,
                                      'errmsg': '添加购物车成功'})
        else:
            # 用户未登录，操作cookie购物车

            # 通过cookie拿到商品字典
            cookie_cart = request.COOKIES.get('carts')

            # 判断字典是否存在
            if cookie_cart:
                # 如果存在就解码 将 cookie_cart 转成 base64 的 bytes,最后将 bytes 转字典
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))
            else:
                # 如果不存在就创建一个空字典
                cart_dict = {}

            # 我们判断用户之前是否将该商品加入过购物车, 如果加入过
            # 则只需要让数量增加即可.
            # 如果没有存在过, 则需要创建, 然后增加:
            # 形式如下所示:
            # {
            #     '<sku_id>': {
            #         'count': '<count>',
            #         'selected': '<selected>',
            #     },
            #     ...
            # }
            # 判断要加入购物车的商品是否已经在购物车中
            # 如有相同商品，累加求和，反之，直接赋值
            if sku_id in cart_dict:
                # 累加求和
                count += cart_dict[sku_id]['count']

            # 直接添加
            cart_dict[sku_id] = {
                'count': count,
                'selected': selected
            }

            # 编码加密 将字典转成 bytes,再将 bytes 转成 base64 的 bytes，最后转为字符串
            cart_data = base64.b64encode(pickle.dumps(cart_dict)).decode()

            # 创建响应对象
            response = http.JsonResponse({'code': RETCODE.OK,
                                          'errmsg': '添加购物车成功'})

            # 将购物车数据写入到 cookie
            response.set_cookie('carts', cart_data)

            # 返回
            return response
