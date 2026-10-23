"""
MongoDB storage module for the multi-agent storyboard system.
"""

from .mongodb import MongoDBStorage, get_mongodb_service

__all__ = ["MongoDBStorage", "get_mongodb_service"]

