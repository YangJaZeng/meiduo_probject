from django import http
from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import render
from django.views import View

from goods.models import GoodsCategory, SKU
from goods.utils import get_categories, get_breadcrumb
from utils.response_code import RETCODE


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
