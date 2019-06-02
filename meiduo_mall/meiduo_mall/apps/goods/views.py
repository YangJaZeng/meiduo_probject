import datetime
from unicodedata import category

from django.utils import timezone

from django import http
from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import render
from django.views import View

from goods.models import GoodsCategory, SKU, GoodsVisitCount, Goods
from goods.utils import get_categories, get_breadcrumb, get_goods_and_spec
from meiduo_mall.utils.response_code import RETCODE
import logging

logger = logging.getLogger('django')


class DetailVisitView(View):
    """详情页分类商品访问量"""

    def post(self, request, category_id):

        # 根据传入的 category_id 值， 获取对应类别的商品
        try:
            category = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return http.HttpResponseNotFound('缺少必传参数')

        # 获取今天的日期
        # 先获取时间对象
        t = timezone.localtime()
        # 根据时间对象拼接日期的字符串
        today_str = '%d-%02d-%02d' % (t.year, t.month, t.day)
        # 将字符串转为日期格式
        today_data = datetime.datetime.strptime(today_str, '%Y-%m-%d')
        try:
            # 将今天的日期传入进去, 获取该商品今天的访问量:
            # 查询今天该类别的商品的访问量
            counts_data = category.goodsvisitcount_set.get(date=today_data)
        except GoodsVisitCount.DoesNotExist:
            counts_data = GoodsVisitCount()

        try:
            # 更新模型类对象里的属性 category 和 count
            counts_data.category = category
            counts_data.count += 1
            counts_data.save()
        except Exception as e:
            logger.error(e)
            return http.HttpResponseNotFound('服务器异常')

        # 返回
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'ok'})


class DetailView(View):
    """商品详情页"""

    def get(self, request, sku_id):
        # 查询商品频道分类

        categories = get_categories()
        # 获取当前sku的信息
        sku = SKU.objects.get(id=sku_id)

        category = sku.category

        # 3.调用工具类方法 查询面包屑导航
        breadcrumb = get_breadcrumb(category)

        # 调用封装的函数, 根据 sku_id 获取对应的
        # 1. 类别( sku )
        # 2. 商品( goods )
        # 3. 商品规格( spec )
        data = get_goods_and_spec(sku_id, request)

        # 拼接数据
        context = {
            'categories': categories,
            'goods': data.get('goods'),
            'breadcrumb': breadcrumb,  # 面包屑导航
            'specs': data.get('goods_specs'),
            'sku': data.get('sku')

        }

        # 返回
        return render(request, 'detail.html', context)


class ListView(View):
    """商品列表页"""

    def get(self, request, category_id, page_num):
        """
        提供商品列表页
        :param request:
        :param category_id: 商品分类级别
        :param page_num: 页码
        :return:
        """

        # 1.判断category_id 是否正确
        try:
            category = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return http.HttpResponseForbidden('GoodsCategory 不存在')

        # 2.调用工具类方法 查询商品频道分类
        categories = get_categories()

        # 3.调用工具类方法 查询面包屑导航
        breadcrumb = get_breadcrumb(category)

        # 4.接收sort 排序方式参数， 如果用户不传，就设置默认值
        sort = request.GET.get('sort', 'default')

        # 5. 按照排序规则查询该分类商品SKU信息
        if sort == 'price':
            # 按照价格从低到高
            sortkind = 'price'
        elif sort == 'hot':
            # 按照热度从高到低
            sortkind = '-sales'
        else:
            # 'price'和'sales'以外的所有排序方式都归为'default'
            sortkind = 'create_time'

        # 获取当前分类并且上架的商品.( 并且对商品按照排序字段进行排序 )
        skus = SKU.objects.filter(category=category,
                                  is_launched=True).order_by(sortkind)
        # 7.创建分页器
        # skus是所有商品， 5 是每页显示的个数
        paginator = Paginator(skus, 5)
        # 使用分页器
        try:
            # page()方法，从第几页开始显示
            page_skus = paginator.page(page_num)
        except EmptyPage:
            # 如果page_num 不正确，默认返回404
            return http.HttpResponseNotFound('empty page')
        # 获取列表页总页数
        total_page = paginator.num_pages
        # 4.拼接
        context = {
            'categories': categories,  # 频道分类
            'breadcrumb': breadcrumb,  # 面包屑导航
            'sort': sort,  # 排序字段
            'category': category,  # 第三级分类
            'page_skus': page_skus,  # 分页后数据
            'total_page': total_page,  # 总页数
            'page_num': page_num,  # 当前页码
        }

        # 5.返回
        return render(request, 'list.html', context)


class HotGoodsView(View):
    """热销排行"""

    def get(self, request, category_id):
        # 根据销售量排序，截取最多的两个商品
        skus = SKU.objects.filter(category_id=category_id,
                                  is_launched=True).order_by('-sales')[:2]
        # 序列化(拼接数据)
        hot_skus = []

        # 选的拼接
        for sku in skus:
            hot_skus.append({
                'id': sku.id,
                'default_image_url': sku.default_image_url,
                'name': sku.name,
                'price': sku.price
            })
        # 返回
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'ok',
                                  'hot_skus': hot_skus})
