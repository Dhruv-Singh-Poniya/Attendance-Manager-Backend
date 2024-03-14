"""Generates notifications for given user."""

import os
from typing import Literal
from pymongo import MongoClient
import dotenv
dotenv.load_dotenv('.env')

class Notifications:
    def __init__(self):
        self.client = MongoClient(
            f"mongodb://{os.getenv('MONGO_DB_USER')}:{os.getenv('MONGO_DB_PASSWORD')}@{os.getenv('MONGO_DB_HOST')}:{os.getenv('MONGO_DB_PORT')}"
        )
        self.db = self.client[os.getenv('MONGO_DB_NAME')]
        self.unread_notifications = self.db['unread_notifications']
        self.read_notifications = self.db['read_notifications']
    
    def __del__(self):
        self.client.close()
    
    def push_notification(
            self,
            username: str,
            subject: str, 
            type: Literal['absent', 'present'],
            num_lectures: int,
            previous_attendance_percentage: float,
            current_attendance_percentage: float,
            previous_date: str,
            previous_time: str,
            current_date: str,
            current_time: str
        ):
        self.unread_notifications.insert_one({
            'username': username,
            'subject': subject,
            'type': type,
            'num_lectures': num_lectures,
            'previous_attendance_percentage': previous_attendance_percentage,
            'current_attendance_percentage': current_attendance_percentage,
            'previous_date': previous_date,
            'previous_time': previous_time,
            'current_date': current_date,
            'current_time': current_time
        })
        
    def retrieve_notifications(self, username: str) -> list:
        """Retrieve unread notifications for given user and mark them as read."""
        notifications = list(self.unread_notifications.find({'username': username}))
        if not notifications:
            return []
        self.unread_notifications.delete_many({'_id': {'$in': [notification['_id'] for notification in notifications]}})
        self.read_notifications.insert_many(notifications)
        return [{key: notification[key] for key in notification if key != '_id'} for notification in notifications]
