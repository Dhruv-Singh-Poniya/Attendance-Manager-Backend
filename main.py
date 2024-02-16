# Imports
from io import BytesIO, StringIO
from typing import List
import json
import requests
from PIL import Image as PILImage
import bs4
import pandas as pd
import flask
import pytesseract

# Global Variables
SRM_STUDENT_PORTAL_URI = 'https://sp.srmist.edu.in/srmiststudentportal/students/loginManager/youLogin.jsp'
SRM_STUDENT_PORTAL_GET_CAPTCHA_URI = 'https://sp.srmist.edu.in/srmiststudentportal/captchas'
ATTENDENCE_PAGE_URI = 'https://sp.srmist.edu.in/srmiststudentportal/students/report/studentAttendanceDetails.jsp'

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

    def get_attendence_table(self) -> pd.DataFrame:
        """Get main Attendence Table. """
        attendence_page = self.attendence_page()
        
        # Get Attendence Table
        attendence_table = attendence_page.find('table', class_='table')
        
        # Convert to DataFrame
        attendence_df = pd.read_html(StringIO(str(attendence_table)))[0]
        
        # Remove Unwanted Subject Codes
        blacklist_codes = ['CL', 'Total']
        attendence_df = attendence_df[~attendence_df['Code'].isin(blacklist_codes)]
        return attendence_df
    
    def get_absent_details(self) -> List[pd.DataFrame]:
        """Get Absent Details for every month."""
        pass


app = flask.Flask(__name__)

@app.route('/get_attendence', methods=['POST'])
def get_attendence():
    """Get Attendence."""
    # Get Username and Password
    username = flask.request.form.get('username')
    if not username:
        return flask.Response(json.dumps({'error': 'username is required form parameter', 'data': ''}), status=400, mimetype='application/json')

    password = flask.request.form.get('password')
    if not password:
        return flask.Response(json.dumps({'error': 'password is required form parameter', 'data': ''}), status=400, mimetype='application/json')

    # Create Attendence Manager Instance
    attendence_manager = AttendenceManager(username, password)

    # Login
    try:
        attendence_manager.login()
    except ValueError as e:
        return flask.Response(json.dumps({'error': str(e), 'data': ''}), status=401, mimetype='application/json')

    # Get Attendence Table
    attendence_df = attendence_manager.get_attendence_table()

    return flask.Response(json.dumps({'data': attendence_df.to_json()}), status=200, mimetype='application/json')

@app.route('/get_attendence', methods=['GET'])
def error():
    """GET request not allowed."""
    return flask.Response(json.dumps({'error': 'GET request not allowed', 'data': ''}), status=405, mimetype='application/json')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
