from django.shortcuts import render
from django.views import View

from contents.models import ContentCategory
from goods.utils import get_categories


class IndexView(View):
    """首页广告"""

    def get(self, request):
        """提供首页广告界面"""

        # 查询首页广告界面
        categories = get_categories()

        # 定义一个空的字典
        dict = {}
        # 查询出所有的广告类别
        content_categories = ContentCategory.objects.all()
        # 遍历所有的广告类别，然后放入到定义的空字典中
        for cat in content_categories:
            # 获取类别对应的展示数据， 并对数据进行排序
            dict[cat.key] = cat.content_set.filter(status=True).order_by('sequence')
        # 拼接参数
        context = {
            # 这是首页需要的一二级分类信息
            'categories': categories,
            # 这是首页需要的能展示的三级信息
            'contents': dict
        }

        return render(request, 'index.html', context=context)

# Create your views here.
