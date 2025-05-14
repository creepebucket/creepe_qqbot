import pymongo
import nonebot
from copy import deepcopy
from nonebot.plugin import *
# 获取配置文件
config = nonebot.get_driver().config

# 读取配置文件
host = config.db_connection
# 连接数据库
client = pymongo.MongoClient(host)


class Database:
    def __init__(self, database_name='qq_bot'):
        # 初始化数据库
        self.database = client[database_name]
        self.collection = None

    def set_collection(self, collection_name):
        # 设置使用的集合
        self.collection = self.database[collection_name]

    def get(self, query_dict):
        # 查询数据
        query_result = self.collection.find_one(query_dict)
        if query_result:
            del query_result['_id']
            return query_result
        return None

    def get_db(self):
        # 获取集合实例
        return self.collection

    def clear(self):
        # 清空集合
        self.collection.delete_many({})

    def __getattr__(self, name):
        """
        实现getattr方法，使得可以通过database示例.方法名 调用数据库集合的方法
        :param name: 方法名
        :return: 数据库集合的方法
        """
        if self.collection is None:
            raise ValueError('错误：请先初始化数据库集合')

        return getattr(self.collection, name)

# 导出数据库
def get_database(collection_name):
    # 获取数据库实例
    db = Database()
    db.set_collection(collection_name)
    return db