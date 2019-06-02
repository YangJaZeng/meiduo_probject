import json
from decimal import Decimal

from django import http
from django.core.paginator import Paginator, EmptyPage
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from django_redis import get_redis_connection

from goods.models import SKU
from orders.models import OrderInfo, OrderGoods
from users.models import Address
from meiduo_mall.utils.views import LoginRequiredMixin, LoginRequiredJSONMixin
from meiduo_mall.utils.response_code import RETCODE
import logging

logger = logging.getLogger('django')


class UserOrderInfoView(LoginRequiredMixin, View):
    """我的订单界面"""

    def get(self, request, page_num):
        # 获取用户
        user = request.user

        # 查询订单
        orders = user.orderinfo_set.all().order_by('-create_time')

        # 遍历所有订单
        for order in orders:
            # 绑定订单状态
            order.status_name = OrderInfo.ORDER_STATUS_CHOICES[order.status_name]
            # 绑定支付方式
            order.pay_method_name = OrderInfo.PAY_METHOD_CHOICES[order.pay_method_name]
            order.sku_list = []
            # 查询订单商品
            order_goods = order.skus.all()
            # 遍历订单商品
            for order_good in order_goods:
                sku = order_good.sku
                sku.count = order_good.count
                sku.amount = sku.price * sku.count
                order.sku_list.append(sku)

        # 分页
        page_num = int(page_num)
        try:
            paginator = Paginator(orders, 2)
            page_orders = paginator.page(page_num)
            total_page = paginator.num_pages
        except EmptyPage:
            return http.HttpResponseForbidden('订单不存在')

        # 拼接格式
        context = {
            'page_orders': page_orders,
            'total_page': total_page,
            'page_num': page_num
        }

        # 返回
        return render(request, 'user_center_order.html', context)


class OrderSuccessView(View):
    """提交订单成功页面"""

    def get(self, request):
        # 结算参数
        order_id = request.GET.get('order_id')
        payment_amount = request.GET.get('payment_amount')
        pay_method = request.GET.get('pay_method')

        # 拼接格式
        context = {
            'order_id': order_id,
            'payment_amount': payment_amount,
            'pay_method': pay_method
        }

        # 返回
        return render(request, 'order_success.html', context)


class OrderCommitView(View):
    """订单提交"""

    def post(self, request):
        # 获取参数
        json_dict = json.loads(request.body.decode())
        address_id = json_dict.get('address_id')
        pay_method = json_dict.get('pay_method')

        # 校验参数
        if not all([address_id, pay_method]):
            return http.HttpResponseForbidden('缺少必传参数')

        try:
            adderss = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return http.HttpResponseForbidden('参数address_id 错误')
        if pay_method not in [OrderInfo.PAY_METHODS_ENUM['CASH'],
                              OrderInfo.PAY_METHODS_ENUM['ALIPAY']]:
            return http.HttpResponseForbidden('pay_method 参数错误')

        # 获取登录用户
        user = request.user

        # 生成订单
        order_id = timezone.localtime().strftime('%Y%m%d%H%M%S') + ('%09d' % user.id)

        with transaction.atomic():
            # 创建事务保存点
            save_id = transaction.savepoint()

            # 回滚
            try:
                # 保存订单基本信息
                order = OrderInfo.objects.create(
                    order_id=order_id,
                    user=user,
                    address=adderss,
                    total_count=0,
                    total_amount=Decimal('0.00'),
                    freight=Decimal('10.00'),
                    pay_method=pay_method,
                    status=OrderInfo.ORDER_STATUS_ENUM['UNPAID']
                    if pay_method == OrderInfo.PAY_METHODS_ENUM['ALIPAY']
                    else OrderInfo.ORDER_STATUS_ENUM['UNSEND']
                )

                # 从redis中读取购物车中被勾选的商品信息
                redis_conn = get_redis_connection('carts')
                item_dict = redis_conn.hgetall('carts_%s' % user.id)
                cart_selected = redis_conn.smembers('selected_%s' % user.id)
                carts = {}

                # 将在set中的商品信息 保存在carts 中
                for sku_id in cart_selected:
                    carts[int(sku_id)] = int(item_dict[sku_id])

                # 获取选中的商品id
                sku_ids = carts.keys()

                # 遍历购物购物车中被勾选的商品
                for sku_id in sku_ids:
                    # 使用乐观锁
                    while True:
                        # 查询SKU信息
                        sku = SKU.objects.get(id=sku_id)

                        # 读取原始库存
                        origin_stock = sku.stock
                        origin_sales = sku.sales

                        # 判断库存
                        sku_count = carts[sku.id]
                        if sku_count > origin_stock:
                            # 出错就回滚到保存点
                            transaction.savepoint_rollback(save_id)
                            return http.JsonResponse({'code': RETCODE.STOCKERR,
                                                      'errmsg': '库存不足'})

                        # 减少库存，增加销量
                        # sku.stock -= sku_count
                        # sku.sales += sku_count
                        # sku.save()

                        # 修改库存和销量
                        new_stock = origin_stock - sku_count
                        new_sales = origin_sales + sku_count

                        # 再次读取库存，来对比
                        result = SKU.objects.filter(
                                id=sku_id,
                                stock=origin_stock
                        ).update(stock=new_stock, sales=new_sales)

                        if result == 0:
                            continue

                        sku.goods.sales += sku_count
                        sku.goods.save()
                        # 保存订单信息
                        OrderGoods.objects.create(
                            order=order,
                            sku=sku,
                            count=sku_count,
                            price=sku.price
                        )

                        # 保存商品订单中总价和总数数量
                        order.total_count += sku_count
                        order.total_amount += (sku.price * sku_count)

                        # 下单成功或者失败，就跳出循环
                        break

                # 添加邮费和保存订单信息
                order.total_amount += order.freight
                order.save()
            except Exception as e:
                logger.error(e)
                transaction.savepoint_rollback(save_id)
                return http.JsonResponse({'code': RETCODE.DBERR,
                                          'errmsg': '下单失败'})

            # 提交事务
            transaction.savepoint_commit(save_id)

        # 清除购物车中已结算的商品
        redis_conn.hdel('carts_%s' % user.id, *cart_selected)
        redis_conn.srem('selected_%s' % user.id, *cart_selected)

        # 返回JSON
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': '下单成功',
                                  'order_id': order.order_id})


class OrderSettlementView(LoginRequiredMixin, View):
    """结算订单"""

    def get(self, request):
        # 获取用户
        user = request.user

        # 查询地址信息
        try:
            addresser = Address.objects.filter(user=request.user,
                                               is_deleted=False)
        except Address.DoesNotExist:
            # 如果地址为空， 渲染模版时会判断，并跳转到地址编辑页面
            addresser = None

        # 从redis购物车中查询出被勾选的商品信息
        redis_conn = get_redis_connection('carts')
        item_dict = redis_conn.hgetall('carts_%s' % user.id)
        cart_selected = redis_conn.smembers('selected_%s' % user.id)
        cart = {}
        for sku_id in cart_selected:
            cart[int(sku_id)] = int(item_dict[sku_id])

        # 准备初始值
        total_count = 0
        total_amount = Decimal(0.00)

        # 查询商品信息
        skus = SKU.objects.filter(id__in=cart.keys())
        for sku in skus:
            sku.count = cart[sku.id]
            sku.amount = sku.price * sku.count
            total_count += sku.count
            total_amount += sku.count * sku.price

        # 补充运费
        freight = Decimal('10.00')

        # 拼接数据，渲染界面
        context = {
            'addresses': addresser,
            'skus': skus,
            'total_count': total_count,
            'total_amount': total_amount,
            'freight': freight,
            'payment_amount': total_amount + freight
        }

        # 返回
        return render(request, 'place_order.html', context)
