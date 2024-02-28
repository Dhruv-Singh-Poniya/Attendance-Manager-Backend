"""This script updates the `attendence` database for a user to latest data."""

from typing import Type
import os
import sys
import psycopg2
from psycopg2.errorcodes import UNIQUE_VIOLATION
import dotenv
dotenv.load_dotenv('.env')

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils import check_if_user_exists
from utils.attendance_manager import AttendanceManager

async def update_attendence_database(
    username: str,
    password: str,
    attendence_manager_cls: Type[AttendanceManager],
    cursor: psycopg2.extensions.connection,
    conn: psycopg2.extensions.connection
) -> dict:
    """Update Attendence Database."""
    # Check if User Exists
    if check_if_user_exists(username, cursor):
        # Get Attendance Details
        attendence_manager = attendence_manager_cls(username, password)
        await attendence_manager.login()
        attendence, _ = await attendence_manager.get_attendance_details()
        # Insert Attendance Data
        for data in attendence:
            try:
                cursor.execute("""
                    INSERT INTO attendence_table (
                        username, subject, max_hours, attended_hours, absent_hours, total_percentage, date, time
                    ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE, CURRENT_TIME)
                """, (username, data['Description'], data['Max. hours'], data['Att. hours'], data['Absent hours'], data['Total Percentage']))
                conn.commit()
            except psycopg2.Error as e:
                if str(e.pgcode) != str(UNIQUE_VIOLATION):
                    print('das')
                    return {'status': 'error', 'message': f'{username}: Internal Server Error'}
                conn.rollback()
        return {'status': 'success', 'message': f'{username}: Attendance Updated Successfully'}
    return {'status': 'error', 'message': f'{username}: User Not Found'}
