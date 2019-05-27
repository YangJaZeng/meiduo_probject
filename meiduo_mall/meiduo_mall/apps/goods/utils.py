from collections import OrderedDict

from goods.models import GoodsChannel


def get_categories():
    """
    获取商城商品分类菜单
    :return: 菜单字典
    """

    # 第一部分: 从数据库中取数据:
    # 定义一个有序字典对象
    categories = OrderedDict()
    # 对GoodsChannel 进行 group_id 和 sequence 排序，获取排序后的结果
    channels = GoodsChannel.objects.order_by('group_id', 'sequence')
    # 遍历排序后的结果： 得到所有的一级菜单（即，频道）
    for channel in channels:
        # 从频道中得到当前的组id
        group_id = channel.group_id

        # 判断： 如果当前组id不在我们的有序字典中
        if group_id not in categories:
            # 我们就把 组id添加到有序字典中
            # 并且作为key 值， value值 值{'channels': [], 'sub_cats': []}
            categories[group_id] = {'channels': [], 'sub_cats': []}

        # 获取当前频道的分类名称
        cat1 = channel.category

        # 给刚刚创建的字典中，追加具体信息
        categories[group_id]['channels'].append({
            'id': cat1.id,
            'name': cat1.name,
            'url': channel.url
        })

        # 根据cta1 的外键反向， 获取下一级（二级菜单）所有的分类数据，并遍历
        for cat2 in cat1.goodscategory_set.all():
            # 创建一个新列表
            cat2.sub_cats = []
            # 根据 cat2 的外键反向，获取下一级的所有分类数据，并遍历
            for cat3 in cat2.goodscategory_set.all():
                # 拼接新的列表
                cat2.sub_cats.append(cat3)
            # 所有内容都增加到 以及菜单生成的有序字典中去
            categories[group_id]['sub_cats'].append(cat2)

    return categories


def get_breadcrumb(category):
    """
    获取面包屑
    :param category: 商品类别
    :return:
    """

    # 定义一个字典
    breadcrumb = dict(
        cat1='',
        cat2='',
        cat3=''
    )
    # 判断 category 是哪一个级别的
    #  category 是 GoodsCategory 对象
    if category.parent is None:
        # 当类别为1 时, 只需展示一级
        breadcrumb['cat1'] = category
    elif category.goodscategory_set.count() == 0:
        # 当对象的下一级数量为0时，证明是最后一级,需要将所有的级别展示出来
        breadcrumb['cat3'] = category
        cat2 = category.parent
        breadcrumb['cat2'] = cat2
        breadcrumb['cat1'] = cat2.parent
    else:
        # 当前类别为二级，需要展示两级
        breadcrumb['cat2'] = category
        breadcrumb['cat1'] = category.parent

    # 返回面包屑结果
    return breadcrumb
