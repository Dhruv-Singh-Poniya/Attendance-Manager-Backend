from fastapi import FastAPI, Form, HTTPException
from pydantic import BaseModel
from utils.database import Database
import asyncio
from contextlib import asynccontextmanager
import datetime
from utils.update_attendence_database import update_attendence_database
from utils.attendance_manager import AttendanceManager

async def update_attendence():
    """Update Attendence Database."""
    while True:
        db = Database()
        users = db.get_all_users()
        tasks = []
        for username, password in users:
            tasks.append(update_attendence_database(username, password, AttendanceManager, db.cursor, db.conn))

        result = await asyncio.gather(*tasks)
        print('Today:', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        for r in result: print(r)
        await asyncio.sleep(1000)

# Schedule the update_attendence_database function to run every 10min for each user
@asynccontextmanager
async def update_attendence_lifespan(app: FastAPI):
    print('Starting Update Attendence Lifespan')
    asyncio.create_task(update_attendence())
    yield
    print('Stopping Update Attendence Lifespan')

app = FastAPI(
    title='SRM Student Portal Attendance Manager API',
    description='API to get SRM Student Portal Attendance Details',
    version='0.0.1',
    docs_url=None,
    redoc_url=None,
    lifespan=update_attendence_lifespan,
)

class User(BaseModel):
    """User model for authentication."""
    username: str = ''
    password: str = ''

    def check_username_password(self) -> str | None:
        """Check Username and Password."""
        # required checks
        if not self.username:
            return 'username is required form parameter'
        if not self.password:
            return 'password is required form parameter'
        
        # length checks
        if len(self.username) != 6:
            return 'username should be of 6 characters'
        if len(self.password) > 64:
            return 'Sorry, password is too long for our database (max 64 characters allowed)'
        
        return None

@app.post('/get_attendance_details')
async def get_attendance(username: str = Form(default=''), password: str = Form(default='')):
    """Get Attendance Details."""
    # Check Username and Password
    user = User(username=username, password=password)
    err_msg = user.check_username_password()
    if err_msg:
        raise HTTPException(status_code=400, detail=err_msg)
    
    # Create Attendance Manager Instance
    attendance_manager = AttendanceManager(user.username, user.password)

    # Login
    try:
        await attendance_manager.login()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Get Attendance Details
    course_wise_attendance, monthly_absent_hours = await attendance_manager.get_attendance_details()
    
    await attendance_manager.close()

    return {
        'CourseWiseAttendance': course_wise_attendance,
        'MonthlyAttendance': monthly_absent_hours,
    }
    
@app.post('/get_timetable')
async def get_timetable(username: str = Form(default=''), password: str = Form(default='')):
    """Get Timetable."""
    # Check Username and Password
    user = User(username=username, password=password)
    err_msg = user.check_username_password()
    if err_msg:
        raise HTTPException(status_code=400, detail=err_msg)
    
    # Create Attendance Manager Instance
    attendance_manager = AttendanceManager(user.username, user.password)

    # Login
    try:
        await attendance_manager.login()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Get Timetable
    timetable = await attendance_manager.get_timetable()
    
    await attendance_manager.close()

    return {'Timetable': timetable}

@app.post('/notifications/register')
async def register_user(username: str = Form(default=''), password: str = Form(default='')):
    """Register User."""
    # Check Username and Password
    user = User(username=username, password=password)
    err_msg = user.check_username_password()
    if err_msg:
        raise HTTPException(status_code=400, detail=err_msg)
    
    # Create Attendance Manager Instance
    attendance_manager = AttendanceManager(user.username, user.password)
    
    # Try to Login to check if the credentials are valid
    try:
        await attendance_manager.login()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    
    # Add User to Database
    db = Database()
    status=db.add_user(user.username, user.password)
    return status

@app.post('/notifications/unregister')
async def unregister_user(username: str = Form(default='')):
    """Unregister User."""
    # Check Username
    if not username:
        raise HTTPException(status_code=400, detail='username is required form parameter')
    
    # Remove User from Database
    db = Database()
    status=db.remove_user(username)
    return status

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
