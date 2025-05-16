import config

import os
import pymongo
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.collection import Collection
from bson.objectid import ObjectId


def __get_connection_str(cluster_name: str) -> str:
    conf = config.general_config['mongo']
    for cluster in conf['clusters']:
        if cluster['name'] == cluster_name:
            connection_str = cluster['connection_string']
            user_env_var = cluster['user_var_name']
            pass_env_var = cluster['pass_var_name']
            cluster_connecting_str = connection_str.format(db_username=os.getenv(user_env_var),
                                                           db_password=os.getenv(pass_env_var))
    return cluster_connecting_str


def get_client(cluster_name: str) -> pymongo.MongoClient:
    connection_str = __get_connection_str(cluster_name)
    return pymongo.MongoClient(connection_str)


def get_client_async(cluster_name: str) -> pymongo.AsyncMongoClient:
    connection_str = __get_connection_str(cluster_name)
    return pymongo.AsyncMongoClient(connection_str)


def string_to_id(id_string: str) -> ObjectId:
    return ObjectId(id_string)


def find_by_id(doc_id: ObjectId, where: Collection) -> dict[str, any]:
    document = where.find_one({"_id": doc_id})
    return document


async def find_by_id_async(doc_id: ObjectId, where: AsyncCollection) -> dict[str, any]:
    document = await where.find_one({"_id": doc_id})
    return document


async def update_by_id_async(doc_id: ObjectId, where: AsyncCollection, set_dict: dict[str, any], **kwargs) -> bool:
    """
    :param doc_id: bson Object
    :param where:
    :param set_dict: {"field_name": field_val, ...}
    :return: true if update was successfully
    """

    res = await where.update_one(
        filter={"_id": doc_id},
        update={"$set": set_dict},
        **kwargs
    )
    return res.matched_count > 0