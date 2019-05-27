from django.core.files.storage import Storage
# 先导入我们安装的 fdfs_client.client 客户端
from fdfs_client.client import Fdfs_client
# 导入 settings 文件
from django.conf import settings


class FastDFSStorage(Storage):

    def save(self, name, content, max_length=None):
        ...

    # 我们再添加一个新的方法
    # 该方法会在我们上传之前,判断文件名称是否冲突
    def exists(self, name):
        # 根据上面的图片我们可知,
        # fdfs 中的文件名是由 fdfs 生成的, 所以不可能冲突
        # 我们返回 False: 永不冲突
        return False

    # 返回可访问到文件的完整的url地址
    # 我们知道, 保存成功后, 返回的图片是不完整的, 所以在这里拼接完整.
    def url(self, name):
        return settings.FDFS_URL + name
