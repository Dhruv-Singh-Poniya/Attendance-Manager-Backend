# Imports
from io import BytesIO, StringIO
import ast
from typing import List
import json
import requests
import asyncio
from PIL import Image as PILImage
import bs4
import pandas as pd
import flask
import pytesseract
from pydantic import BaseModel

# Global Variables
SRM_STUDENT_PORTAL_URI = 'https://sp.srmist.edu.in/srmiststudentportal/students/loginManager/youLogin.jsp'
SRM_STUDENT_PORTAL_GET_CAPTCHA_URI = 'https://sp.srmist.edu.in/srmiststudentportal/captchas'
ATTENDENCE_PAGE_URI = 'https://sp.srmist.edu.in/srmiststudentportal/students/report/studentAttendanceDetails.jsp'
MONTHLY_ATTENDENCE_PAGE_URI = 'https://sp.srmist.edu.in/srmiststudentportal/students/report/studentAttendanceDetailsInner.jsp'

class AttendenceManager:
    """SRM Student Portal Attendence Manager API Interface."""
    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        }
    
    def login(self) -> None:
        """Login to SRM Student Portal."""

        # Make GET request to SRM Student Portal
        self.session.get(SRM_STUDENT_PORTAL_URI, headers=self.headers)

        # Get Captcha
        capcha_bin = self.session.get(SRM_STUDENT_PORTAL_GET_CAPTCHA_URI, headers=self.headers).content
        capcha_text = pytesseract.image_to_string(PILImage.open(BytesIO(capcha_bin))).strip()

        # Login
        data = {
            'txtPageAction': '1',
            'txtAN': self.username,
            'txtSK': self.password,
            'hdnCaptcha': capcha_text,
        }
        response = self.session.post(SRM_STUDENT_PORTAL_URI, data=data)

        # Check for Login Error
        if response.text.find('Login Error : Invalid net id or password') != -1:
            raise ValueError('Invalid Username or Password')

        # Check for Captcha Error, If so then try again
        if response.text.find('Invalid Captcha....') != -1:
            self.login()

    def attendence_page(self) -> bs4.BeautifulSoup:
        """Get Attendence Page."""
        # Make GET request to Attendence Page
        response = self.session.post(ATTENDENCE_PAGE_URI, headers=self.headers)
        
        # Parse HTML
        attendence_page = bs4.BeautifulSoup(response.text, 'html.parser')
        
        return attendence_page

    def get_CourseWiseAttendence(self) -> List[dict[str, str | int]]:
        """Get main Attendence Table. """
        attendence_page = self.attendence_page()
        
        # Get Attendence Table
        attendence_table = attendence_page.findAll('table', class_='table')[0]
        
        # Convert to DataFrame
        attendence_df = pd.read_html(StringIO(str(attendence_table)))[0]
        
        # Remove Unwanted Subject Codes
        blacklist_codes = ['CL', 'Total']
        attendence_df = attendence_df[~attendence_df['Code'].isin(blacklist_codes)]
        return ast.literal_eval(attendence_df.to_json(index=False, orient='records'))
    
    def get_MonthlyAttendence(self) -> List[dict[str, str | int]]:
        """Get Absent Details for every month."""
        attendence_page = self.attendence_page()
        
        # Get Cumulative Attendence Table
        cumulative_attendence_table = attendence_page.findAll('table', class_='table')[1]
        cumulative_attendence_df = pd.read_html(StringIO(str(cumulative_attendence_table)))[0]
        month_map = {'JAN': 1, 'FEB': 2,'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
        
        daywise_absent_details = []
        for idx, row in cumulative_attendence_df.iterrows():
            mon, year = row['Month / Year'].split(' / ')
            response = self.session.post(
                MONTHLY_ATTENDENCE_PAGE_URI,
                data={
                    'ids': 1, 
                    'attendanceMonth': month_map[mon],
                    'attendanceYear': year,
                },
            )
            absent_details = pd.read_html(StringIO(str(response.text)))[0]
            daywise_absent_details.extend(ast.literal_eval(absent_details.to_json(index=False, orient='records')))

        return daywise_absent_details
class User(BaseModel):
    """User."""
    username: str = ''
    password: str = ''

    def check_username_password(self) -> str | None:
        """Check Username and Password."""
        if not self.username:
            return 'username is required form parameter'

        if not self.password:
            return 'password is required form parameter'

app = flask.Flask(__name__)

@app.route('/get_attendence_details', methods=['POST'])
def get_attendence():
    """Get Attendence."""
    # Check Username and Password
    user = User(**flask.request.form)
    err_msg = user.check_username_password()
    if err_msg:
        return flask.Response(json.dumps({'error': err_msg, 'data': ''}), status=400, mimetype='application/json')
    
    # Create Attendence Manager Instance
    attendence_manager = AttendenceManager(user.username, user.password)

    # Login
    try:
        attendence_manager.login()
    except ValueError as e:
        return flask.Response(json.dumps({'error': str(e), 'data': ''}), status=401, mimetype='application/json')

    # Get Attendence Table
    CourseWiseAttendence = attendence_manager.get_CourseWiseAttendence()

    # Get Monthly Absent Hours
    MonthlyAbsentHours = attendence_manager.get_MonthlyAttendence()
    return flask.Response(
        json.dumps(
            {
                'CourseWiseAttendence': CourseWiseAttendence,
                'MonthlyAttendence': MonthlyAbsentHours,
                }
            ), status=200, mimetype='application/json')

@app.route('/get_attendence_details', methods=['GET'])
def error():
    """GET request not allowed."""
    return flask.Response(json.dumps({'error': 'GET request not allowed', 'data': ''}), status=405, mimetype='application/json')
