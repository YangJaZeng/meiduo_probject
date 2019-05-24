from django import http
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render

# Create your views here.
from django.views import View

from areas.models import Area
from meiduo_mall.utils.response_code import RETCODE


class SubAreasView(View):

    def get(self, request, pk):
        """
        接收id， 返回市或者区的数据
        :param request:
        :param pk:
        :return:
        """
        sub_data = cache.get('sub_area_' + pk)
        if not sub_data:
            try:
                # 1.获取市区的数据
                sub_model_list = Area.objects.filter(parent=pk)

                # 2.获取省份的数据
                parent_model = Area.objects.get(id=pk)

                sub_list = []

                # 3.遍历(拼接)
                for sub_model in sub_model_list:
                    sub_list.append({'id': sub_model.id,
                                     'name': sub_model.name})

                # 4.再次拼接
                sub_data = {'id': parent_model.id,
                            'name': parent_model.name,
                            'subs': sub_list}
                cache.set('sub_area_' + pk, sub_data, 3600)
            except Exception as e:
                return http.JsonResponse({'code': RETCODE.DBERR,
                                          'errmsg': '获取市区数据出错'})
        # 5.返回
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'OK',
                                  'sub_data': sub_data})


class ProvinceAreasView(View):
    """省级地区"""

    def get(self, request):
        '''
        从数据库中获取省份数据, 返回前端
        :param request:
        :return:
        '''

        province_list = cache.get('province_list')

        if not province_list:

            try:
                # 1. 从数据库中获取省份数据(条件: parent为空)
                province_model_list = Area.objects.filter(parent__isnull=True)

                province = []

                # 2. 遍历(拿取每一个)
                for province_model in province_model_list:
                    # 3. 拼接格式 [{'id':'', 'name':''}]
                    province.append({'id': province_model.id,
                                     'name': province_model.name})
                # 增加缓存
                cache.set('province_list', province, 3600)
            except Exception as e:
                return http.JsonResponse({'code': RETCODE.DBERR,
                                          'errmsg': '数据库出错'})

        # 4. 返回
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'ok',#
                                  'province_list': province_list})
