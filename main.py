import os
import urllib

import pysolr
import re

import requests
from tika import parser
import pytesseract as pytesseract
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, flash, json
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from solr import SolrConnection
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# configure database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="finalyearproject"
)

# define route for the home page
@app.route('/')
def home():
    return render_template('home.html')


# define route for the login page

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
    except KeyError:
        error = 'Invalid request'
        return render_template('login.html', error=error)

    # Connect to the finalyearproject database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="finalyearproject"
    )

    cur = conn.cursor()

    # Query the appropriate table based on the user type
    if user_type == 'student':
        cur.execute("SELECT * FROM students WHERE email = %s AND password = %s", (email, password))
    elif user_type == 'faculty':
        cur.execute("SELECT * FROM faculty WHERE email = %s AND password = %s", (email, password))
    elif user_type == 'admin':
        cur.execute("SELECT * FROM admin WHERE email = %s AND password = %s", (email, password))

    user = cur.fetchone()
    conn.close()

    # Check if user exists
    if user:
        # Redirect to appropriate dashboard based on user type
        if user_type == 'student':
            return redirect(url_for('home'))
        elif user_type == 'faculty':
            return redirect(url_for('faculty_dashboard'))
        elif user_type == 'admin':
            return redirect(url_for('dashboard'))

    # If user does not exist or password is incorrect, show an error message
    error = 'Invalid email or password.'
    return render_template('login.html', error=error)




@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        user_type = request.form['user_type']
        cursor = db.cursor()
        cursor.execute("SELECT * FROM students WHERE username=%s", (username,))
        user = cursor.fetchone()
        if user is not None:
            return 'Username already taken'
        if password != confirm_password:
            return 'Passwords do not match'
        if user_type == 'faculty':
            cursor.execute("INSERT INTO faculty (id, username, email, password, user_type) VALUES (NULL, %s, %s, %s, %s)",
                           (username, email, password, user_type))
        elif user_type == 'student':
            cursor.execute("INSERT INTO students (id, username, email, password, user_type) VALUES (NULL, %s, %s, %s, %s)",
                           (username, email, password, user_type))
        else:
            return 'Invalid user type'
        db.commit()
        return redirect(url_for('login'))
    return render_template('register.html')



# define route for the dashboard page




#crud operation for student






@app.route('/dashboard')
def dashboard():
    cursor = db.cursor()

    # Query data from the faculty database
    cursor.execute("SELECT * FROM faculty")
    faculty = cursor.fetchall()

    # Query data from the students database
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()

    return render_template('dashboard.html', faculty=faculty, students=students)

@app.route('/dashboard/new', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        cursor = db.cursor()

        # Check if the user already exists in the database
        cursor.execute("SELECT * FROM {} WHERE username=%s".format(user_type), (name,))
        existing_user = cursor.fetchone()
        if existing_user:
            flash("User already exists.")
            return redirect(url_for('add_user'))

        # If the user does not already exist, insert them into the database
        if user_type == 'faculty':
            cursor.execute("INSERT INTO faculty (username, email, password, user_type) VALUES (%s, %s, %s, %s)", (name, email, password, user_type))
        elif user_type == 'students':
            cursor.execute("INSERT INTO students (username, email, password, user_type) VALUES (%s, %s, %s, %s)", (name, email, password, user_type))

        db.commit()
        return redirect(url_for('dashboard'))
    return render_template('add_user.html')


@app.route('/dashboard/<string:table>/<int:id>/edit', methods=['GET', 'POST'])
def edit_user(table, id):
    cursor = db.cursor()

    if table == 'faculty':
        cursor.execute("SELECT * FROM faculty WHERE id=%s", (id,))
        user = cursor.fetchone()
    elif table == 'students':
        cursor.execute("SELECT * FROM students WHERE id=%s", (id,))
        user = cursor.fetchone()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        cursor = db.cursor()

        if table == 'faculty':
            cursor.execute("UPDATE faculty SET username=%s, email=%s, password=%s WHERE id=%s", (name, email, password, id))
        elif table == 'students':
            cursor.execute("UPDATE students SET username=%s, email=%s, password=%s WHERE id=%s", (name, email, password, id))

        db.commit()
        return redirect(url_for('dashboard'))

    return render_template('edit_user.html', table=table, user=user)


@app.route('/dashboard/<string:table>/<int:id>/delete', methods=['POST'])
def delete_user(table, id):
    cursor = db.cursor()

    if table == 'faculty':
        cursor.execute("DELETE FROM faculty WHERE id=%s", (id,))
    elif table == 'students':
        cursor.execute("DELETE FROM students WHERE id=%s", (id,))

    db.commit()
    return redirect(url_for('dashboard'))

# upload notification
app.config['UPLOAD_FOLDER'] = 'static/uploads'
noti = pysolr.Solr('http://localhost:8983/solr/notification', always_commit=True)

@app.route('/upload-notification', methods=['GET', 'POST'])
def upload_notification():
    if request.method == 'POST':
        # Get the form data
        id = request.form['id']
        subject = request.form['subject']
        date = request.form['date']
        image = request.files['image']

        try:
            # Save the image to the static/images folder
            image_filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

            # Process the image using Pytesseract
            text = pytesseract.image_to_string(Image.open(image))
            image_url = 'http://localhost:5000/' + url_for('static', filename='uploads/' + image_filename)

            # Index the notification data in Apache Solr
            noti.add([{
                'id': id,
                'subject': subject,
                'notidate': date,
                'text': text,
                'image_url': image_url
            }])

            return "Notification uploaded successfully!"

        except Exception as e:
            # Log any errors that occur during the image processing or indexing
            app.logger.error(str(e))
            return "An error occurred while uploading the notification."

    else:
        return render_template('upload_notification.html')

noti = pysolr.Solr('http://localhost:8983/solr/notification', always_commit=True)


@app.route('/notification', methods=['GET', 'POST'])
def notification():
    if request.method == 'POST':
        # If the user submitted the search form, update the results based on the selected radio button and query
        query = request.form['query']
        search_by = request.form['search_by']

        if search_by == 'subject':
            query_params = {
                'q': 'subject:"{}"'.format(query),
                'rows': 10,
                'start': 0,
                'wt': 'json',
                'indent': 'true',
                'df': 'subject'
            }
        elif search_by == 'date':
            # Assuming that the user inputs the date in the format 'YYYY-MM-DD'
            query_params = {
                'q': 'notidate:"{}"'.format(query),
                'rows': 10,
                'start': 0,
                'wt': 'json',
                'indent': 'true',
                'df': 'notidate'
            }
        elif search_by == 'id':
            query_params = {
                'q': 'id:"{}"'.format(query),
                'rows': 10,
                'start': 0,
                'wt': 'json',
                'indent': 'true',
                'df': 'id'
            }
        else:  # search_by == 'text'
            query_params = {
                'q': 'text:"{}"'.format(query),
                'rows': 10,
                'start': 0,
                'wt': 'json',
                'indent': 'true',
                'df': 'text'
            }

        # Make the Solr request and get the search results
        response = noti.search(**query_params)
        results = response.docs

        # Render the search results page with the updated results
        return render_template('notification.html', results=results)


    else:
        # If the user didn't submit the search form, display the first 5 notifications by default
        query_params = {
            'q': '*:*',
            'rows': 10,
            'start': 0,
            'wt': 'json',
            'sort': 'notidate asc'
        }

        # Make the Solr request and get the default results
        response = noti.search(**query_params)
        results = response.docs

        # Render the default page with the default results
        return render_template('notification.html', results=results)


app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']





@app.route('/uploads', methods=['GET', 'POST'])
def upload_pdf():
    if request.method == 'POST':
        pdf_file = request.files['pdf_file']
        file_path = os.path.join('static', 'uploads', pdf_file.filename)
        pdf_file.save(file_path)
        parsed_pdf = parser.from_file(file_path)
        data = parsed_pdf['content']
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        # elif not isinstance(data, str):
        #     data = str(data)
            return "Error: Unable to parse the PDF file"
        solr = pysolr.Solr('http://localhost:8983/solr/newdata', always_commit=True)
        values = re.findall(r'\d\s....\d\d\d\d\s..........\s.......\s\(..\-\d\)\s\d\(\d\+\d\)'
                            r'\s\n\n\d\s\n\s\n\n....\d\d\d\d\s\n............\s..\s...........\s'
                            r'..........\s\n\n\s\n\n\(..\-\d\)\s\n\n\s\n\n\d\(\d\+\d\)'
                            r'\s\n\n\d\s....\d\d\d\d\/\s\n\n....\d\d\d\d\s\n\n\*\s\n\n\s\n\n.....'
                            r'..\s.......\/......\s\(..-\d\)\s\n\s\n\n\d\(\d\+\d\)'
                            r'\s\n\n\d\s....\d\d\d\d\s........\-\d\s\(....\-\d\)\s\d\(\d\+\d\)'
                            r'\s\n\n\d\s....\d\d\d\d\s.......\s.....\s...\s......\s\d\(\d\+\d\)'
                            r'\s\n\n\d\s.......\s\(..........\s........\s\d\)\s\d\(\d\+\d\)', str(data))
        newvalue = [re.sub(r'[\n]', '', string)for string in values]
        my_string = ', '.join(newvalue)
        coursecode = re.findall(r'[A-Z]+\d+|[A-Z]+XXXX',my_string)
        credit_hour = re.findall(r'\d\(\d\+\d\)',my_string)
        pattern = r'Functional\sEnglish|Introduction\sto\sInformation\sTechnology|Islamic\sStudies\/Ethics|Calculus-1|Digital\sLogic\sand\sDesign|University\sElective\s1'
        subject_names = re.findall(pattern, my_string)

        # solr = pysolr.Solr('http://localhost:8983/solr/fypdata', always_commit=True)
        data = []
        max_len1 = max(len(coursecode), len(credit_hour), len(subject_names))
        for i in range(max_len1):
            doc = {
                "id": "sem1" +str(i+1),
                "coursecode": coursecode[i] if i < len(coursecode) else "",
                "credit_hour": credit_hour[i] if i < len(credit_hour) else "",
                "subject_names": subject_names[i] if i < len(subject_names) else "",
                "semester": '1st'
            }
            data.append(doc)

        solr.add(data)
        solr.commit()
        values2 = re.findall(r'\d\s....\d\d\d\d\s........\s.......\s\(..\-\d\)\s\d\(\d\+\d\)'
                             r'\s\n\n\d\s....\d\d\d\d\s\n...........\s............\s\n\n\(..'
                             r'..\.\s....\-\(\d\)\)\s\n\d\(\d\+\d\)\s\n\n\d\s....\d\d\d\d\s..'
                             r'......\s...........\s\n\n\(....\.\s....\-\(\d\)\)\s\n\d\(\d\+'
                             r'\d\)\s\n\n\d\s....\d\d\d\d\s\n...........\s..........\s.......'
                             r'.......\s\n\(..\.\s....\s\(\d\)\)\s\n\n\d\(\d\+\d\)\s\n\n\d\s'
                             r'.......\s\(...................\s\d\)\s\d\(\d\+\d\)\s\n\n', str(data))
        newvalue2 = [re.sub(r'[\n]', '', string) for string in values2]
        my_string = ', '.join(newvalue2)
        coursecode = re.findall(r'[A-Z]+\d+|[A-Z]+XXXX', my_string)
        # print(coursecode)
        credit_hour = re.findall(r'\d\(\d\+\d\)', my_string)
        # print(credit_hour)
        # pattern = r'(?<=\d\s)[A-Za-z\s]+(?=\s\(\w)'
        pattern = r'Pakistan\sStudies|Programming\sFundamentals|Discrete\sMathematics|Information\sTechnology\sInfrastructure|University\sElective'
        subject_names = re.findall(pattern, my_string)
        # print(subject_names)
        # solr = pysolr.Solr('http://localhost:8983/solr/fypdata', always_commit=True)
        data2 = []
        max_len2 = max(len(coursecode), len(credit_hour), len(subject_names))
        for i in range(max_len2):
            doc = {
                "id": "sem2" + str(i + 1),
                "coursecode": coursecode[i] if i < len(coursecode) else "",
                "credit_hour": credit_hour[i] if i < len(credit_hour) else "",
                "subject_names": subject_names[i] if i < len(subject_names) else "",
                "semester": '2nd'
            }
            data2.append(doc)

        solr.add(data2)
        solr.commit()
        values3 = re.findall(
            r'\d\s....\d\d\d\d\s.........\s.......\s...\s............\s......\s\n\n\(..\-\d\)\s\n\n\d\(\d'
            r'\+\d\)\s\n\n\d\s....\d\d\d\d\s......\s........\s...........\s\n\n\(....\.\s....\(\d\)\)\s\n'
            r'\d\(\d\+\d\)\s\n\n\d\s....\d\d\d\d\s..........\s......\s.......\s\(....\-\d\)\s\d\(\d\+\d\)'
            r'\s\n\n\d\s....\d\d\d\d\s\n........\s.......\s\n\n\(....\.\s....\(\d\)\)\s\d\(\d\+\d\)\s\n\n'
            r'\d\s.......\s\n\s\n\n\(..........\s........\s\d\)\s\d\(\d\+\d\)\s\n', str(data))
        newvalues3 = [re.sub(r'[\n]', '', string) for string in values3]
        print(newvalues3)
        my_string = ', '.join(newvalues3)
        coursecode = re.findall(r'[A-Z]+\d+|[A-Z]+XXXX', my_string)
        # print(coursecode)
        credit_hour = re.findall(r'\d\(\d\+\d\)', my_string)
        # print(credit_hour)
        subject_names = re.findall(r'(?<=\d\s)[A-Za-z\s]+(?=\s\(\w)', my_string)
        # print(subject_names)
        # solr = pysolr.Solr('http://localhost:8983/solr/fypdata')
        data3 = []
        max_len3 = max(len(coursecode), len(credit_hour), len(subject_names))
        for i in range(max_len3):
            doc = {
                "id": "sem3" + str(i + 1),
                "coursecode": coursecode[i] if i < len(coursecode) else "",
                "credit_hour": credit_hour[i] if i < len(credit_hour) else "",
                "subject_names": subject_names[i] if i < len(subject_names) else "",
                "semester": '3rd'
            }
            data3.append(doc)

        solr.add(data3)
        solr.commit()
        values4 = re.findall(
            r'\d\s....\d\d\d\d\s............\s..\s..........\s...\s...........\s\n\n\(....\-\d\)\s\n\n\s\n\n\d\('
            r'\d\+\d\)\s\n\n\d\s....\d\d\d\d\s\n........\s...........\s\n\n\(....\.\s....\(\d\)\)\s\n\d\(\d\+'
            r'\d\)\s\n\n\d\s....\d\d\d\d\s\n.........\s.......\s\n\n\(....\.\s....\s\(\d\)\)\s\n\d\(\d\+\d\)'
            r'\s\n\n\d\s....\d\d\d\d\s\n....\s..........\s...\s..........\s\n\n\(....\.\s....\s\(\d\)\)\s\n'
            r'\d\(\d\+\d\)\s\n\n\d\s.......\s\(..........\s........\s\d\)\s\d\(\d\+\d\)\s\n\n', str(data))
        newvalues4 = [re.sub(r'[\n]', '', string) for string in values4]
        my_string = ', '.join(newvalues4)
        coursecode = re.findall(r'[A-Z]+\d+|[A-Z]+XXXX', my_string)
        # print(coursecode)
        credit_hour = re.findall(r'\d\(\d\+\d\)', my_string)
        # print(credit_hour)
        subject_names = re.findall(r'(?<=\d\s)[A-Za-z\s]+(?=\s\(\w)', my_string)
        # print(subject_names)
        # solr = pysolr.Solr('http://localhost:8983/solr/fypdata')
        data4 = []
        max_len4 = max(len(coursecode), len(credit_hour), len(subject_names))
        for i in range(max_len4):
            doc = {
                "id": "sem4" + str(i + 1),
                "coursecode": coursecode[i] if i < len(coursecode) else "",
                "credit_hour": credit_hour[i] if i < len(credit_hour) else "",
                "subject_names": subject_names[i] if i < len(subject_names) else "",
                "semester": '4th'
            }
            data4.append(doc)

        solr.add(data4)
        solr.commit()

        # code for semester 5 breakup

        values5 = re.findall(
            r'\d\s\n\s\n\n....\d\d\d\d\s\n........\s..............\s...\s\n\n..........\s\(..\.\s....\s'
            r'\(\d\)\)\s\n\n\s\n\n\d\(\d\+\d\)\s\n\n\d\s....\d\d\d\d\s\n\s\n\n......\s...\s.......\s..'
            r'............\s\n\n\(..\.\s....\s\(\d\)\)\s\n\n\d\(\d\+\d\)\s\n\n\d\s....\d\d\d\d\s...\s.'
            r'..........\s\(..\.\s....\s\(\d\)\)\s\d\(\d\+\d\)\s\n\n\d\s........\s..\s........\s'
            r'\d\s\d\(\d\+\d\)\s\n\n\d\s........\s..\s........\s\d\s\d\(\d\+\d\)\s\n\n', str(data))
        newvalues5 = [re.sub(r'[\n]', '', string) for string in values5]
        my_string = ', '.join(newvalues5)
        coursecode = re.findall(r'[A-Z]+\d+|[A-Z]+XXXX', my_string)
        # print(coursecode)
        credit_hour = re.findall(r'\d\(\d\+\d\)', my_string)
        # print(credit_hour)
        # pattern = r'(?<=\d\s)[A-Za-z\s]+(?=\s\(\w)'
        pattern = r'Database\sAdministration\sand\sManagement|System\sand\sNetwork\sAdministration|Web\sEngineering|IT\sElective\s1|IT\sElective\s2'
        subject_names = re.findall(pattern, my_string)
        # print(subject_names)
        # solr = pysolr.Solr('http://localhost:8983/solr/fypdata', always_commit=True)
        data5 = []
        max_len5 = max(len(coursecode), len(credit_hour), len(subject_names))
        for i in range(max_len5):
            doc = {
                "id": "sem5" + str(i + 1),
                "coursecode": coursecode[i] if i < len(coursecode) else "",
                "credit_hour": credit_hour[i] if i < len(credit_hour) else "",
                "subject_names": subject_names[i] if i < len(subject_names) else "",
                "semester": '5th'
            }
            data5.append(doc)

        solr.add(data5)
        solr.commit()

        # code for semester 6 breakupu
        values6 = re.findall(r'\d\s....\d\d\d\d\s..\s.......\s..........\s\(..\.\s....\s\(\d\)\)\s\d\(\d\+\d\)\s\n'
                             r'\n\d\s....\d\d\d\d\s\n........\s..............\s...\s........\s\n\n\(....\.\s....\s'
                             r'\(\d\)\)\s\n\d\(\d\+\d\)\s\n\n\d\s........\s..\s........\s\d\s\d\(\d\+\d\)\s\n\n\d\s'
                             r'........\s..\s........\s\d\s\d\(\d\+\d\)\s\n\n\d\s........\s..\s..........\s\d\s\d\(\d\+\d\)\s\n',
                             str(data))
        newvalues6 = [re.sub(r'[\n]', '', string) for string in values6]
        my_string = ', '.join(newvalues6)
        coursecode = re.findall(r'[A-Z]+\d+|[A-Z]+XXXX', my_string)
        # print(coursecode)
        credit_hour = re.findall(r'\d\(\d\+\d\)', my_string)
        # print(credit_hour)
        # pattern = r'(?<=\d\s)[A-Za-z\s]+(?=\s\(\w)'
        pattern = r'IT\sProject\sManagement|Computer\sCommunications\sand\sNetworks|IT\sElective\s3|IT\sElective\s4|IT\sSupportive\s1'
        subject_names = re.findall(pattern, my_string)
        # print(subject_names)
        # solr = pysolr.Solr('http://localhost:8983/solr/fypdata', always_commit=True)
        data6 = []
        max_len6 = max(len(coursecode), len(credit_hour), len(subject_names))
        for i in range(max_len6):
            doc = {
                "id": "sem6" + str(i + 1),
                "coursecode": coursecode[i] if i < len(coursecode) else "",
                "credit_hour": credit_hour[i] if i < len(credit_hour) else "",
                "subject_names": subject_names[i] if i < len(subject_names) else "",
                "semester": '6th'
            }
            data6.append(doc)

        solr.add(data6)
        solr.commit()

        # code for semester 7 breakup

        values7 = re.findall(
            r'\d\s....\d\d\d\d\s.....\s........\s\(..\.\s....\s\(\d\)\)\s\d\(\d\+\d\)\s\n\n\d\s\n\s\n\n'
            r'....\d\d\d\d\s\n\s\n\n............\s.........\s\(..\-\d\)\s\n\s\n\n\d\(\d\+\d\)\s\n\n\d\s'
            r'........\s..\s........\s\d\s\d\(\d\+\d\)\s\n\n\d\s........\s..\s..........\s\d\s\d\(\d\+\d'
            r'\)\s\n\n\d\s....\d\d\d\d\s..\s........\s.......\*\s\d\(\d\+\d\)\s\n', str(data))
        newvalues7 = [re.sub(r'[\n]', '', string) for string in values7]
        my_string = ', '.join(newvalues7)
        coursecode = re.findall(r'[A-Z]+\d+|[A-Z]+XXXX', my_string)
        # print(coursecode)
        credit_hour = re.findall(r'\d\(\d\+\d\)', my_string)
        # print(credit_hour)
        subject_names = re.findall(
            r'Cyber\sSecurity|Professional\sPractices|IT\sElective|IT\sSupportive|IT\sCapstone\sProject', my_string)
        subject_name = [re.sub(r'[\n]', '', string) for string in subject_names]

        # print(subject_name)
        # solr = pysolr.Solr('http://localhost:8983/solr/fypdata', always_commit=True)
        data7 = []
        max_len7 = max(len(coursecode), len(credit_hour), len(subject_names))
        for i in range(max_len7):
            doc = {
                "id": "sem7" + str(i + 1),
                "coursecode": coursecode[i] if i < len(coursecode) else "",
                "credit_hour": credit_hour[i] if i < len(credit_hour) else "",
                "subject_names": subject_names[i] if i < len(subject_names) else "",
                "semester": '7th'
            }
            data7.append(doc)
        solr.add(data7)
        solr.commit()

        # code for semester 8 breakup

        values8 = re.findall(r'\d\s....\d\d\d\d\s.......\s.......\s...\s........\s\n\n\(..\.\s'
                             r'....\s\(\d\)\)\s\n\n\s\n\n\d\(\d\+\d\)\s\n\n\d\s........\s\n\s\n'
                             r'\n..\s..........\s\d\s\d\(\d\+\d\)\s\n\n\d\s....\d\d\d\d\s.......\s'
                             r'........\s\n\n\(....\.\s....\s\(\d\)\)\s\n\d\(\d\+\d\)\s\n\n\d\s.'
                             r'...\d\d\d\d\s..\s........\s.......\s\d\(\d\+\d\)\s', str(data))
        newvalues8 = [re.sub(r'[\n]', '', string) for string in values8]
        my_string = ', '.join(newvalues8)
        coursecode = re.findall(r'[A-Z]+\d+|[A-Z]+XXXX', my_string)
        # print(coursecode)
        credit_hour = re.findall(r'\d\(\d\+\d\)', my_string)
        # print(credit_hour)
        # pattern = r'\b[A-Z]+\d+\b\s+([A-Za-z\s]+)|xxxxxxx'
        pattern = r'Virtual\sSystems\sand\sServices|IT\sSupportive\s3|Network\sSecurity|IT\sCapstone\sProject'
        subject_names = re.findall(pattern, my_string)
        # print(subject_names)
        # solr = pysolr.Solr('http://localhost:8983/solr/fypdata', always_commit=True)
        data8 = []
        max_len8 = max(len(coursecode), len(credit_hour), len(subject_names))
        for i in range(max_len8):
            doc = {
                "id": "sem8" + str(i + 1),
                "coursecode": coursecode[i] if i < len(coursecode) else "",
                "credit_hour": credit_hour[i] if i < len(credit_hour) else "",
                "subject_names": subject_names[i] if i < len(subject_names) else "",
                "semester": '8th'
            }
            data8.append(doc)

        solr.add(data8)
        solr.commit()

         # code for elective subjects

        elective_cour = re.findall(
            r'\d\s....\d\d\d\d\s........\s............\s...\s........\s\n\d\(\d\+\d\)\s\n\n\d\s...'
            r'.\d\d\d\d\s....\s......\s\n\d\(\d\+\d\)\s\n\n\d\s....\d\d\d\d\s..........\s..........'
            r'..\s\n\d\(\d\+\d\)\s\n\n\d\s....\d\d\d\d\s........\s.......\s.........\s\n\d\(\d\+\d\)\s\n\n\d\s...'
            r'.\d\d\d\d\s.....\s........\s...........\s\d\(\d\+\d\)\s\n\n\d\s....\d\d\d\d\s......\s........\s.....'
            r'...\s...\s......\s\d\(\d\+\d\)\s\n\n\d\s....\d\d\d\d\s..........\s..........\s\n\d\(\d\+\d\)\s\n\n\d\s..'
            r'..\d\d\d\d\s.......\s......\s...\s..........\s\n\d\(\d\+\d\)\s\n\n\d\s....\d\d\d\d\s...........\s....'
            r'....\s.......\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s..........\s........\s\n\d\(\d\+\d\)\s\n\n\d\d\s.'
            r'...\d\d\d\d\s....\s...........\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s............\s...........\s....'
            r'..\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s......\s........\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s....'
            r'....\s.......\s..........\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s........\s....\s.....\s...\s...........'
            r'.\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s........\s........\s\n\d\(\d\+\d\)\s\n\n\s\n\n\s\n\s\n\nAnnexure-'
            r'A,\sPage\s#\s7\sof\s146\s\n\nPage\s7\sof\s146\s\n\n\s\n\n\s\n\n\s\n\n\s\n\n\s\n\n\s\n\n\s\n\s\n\n\d\d\s....\d\d\d\d\s.'
            r'.......\s......\s...\s............\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s...........\s........'
            r'.\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s........\s............\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s...\s...'
            r'.........\s...........\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s..........\s.......\s...\s......\s\n\d\(\d\+\d\)\s\n\n\d\d\s..'
            r'..\d\d\d\d\s.......\s...\s...........\s...........\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s.....\s........'
            r'.\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s......\s...........\s...........\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s....'
            r'..\s...\s.........\s.........\s\n\d\(\d\+\d\)\s\n\n\d\d\s....\d\d\d\d\s.........\s.....\s.......\s\n\d\(\d\+\d\)\s\n\n\d\d\s..'
            r'..\d\d\d\d\s........\s...........\s..........\s\n\d\(\d\+\d\)\s\n', str(data))
        elective_course = [re.sub(r'[\n]', '', string) for string in elective_cour]
        my_string = ', '.join(elective_course)
        coursecode = re.findall(r'[A-Z]+\d+|[A-Z]+XXXX', my_string)
        # print(coursecode)
        credit_hour = re.findall(r'\d\(\d\+\d\)', my_string)
        # print(credit_hour)
        subject_names = re.findall(r'\b[A-Z]+\d+\b\s+([A-Za-z\s]+)|xxxxxxx', my_string)
        # print(subject_names)

        # solr = pysolr.Solr('http://localhost:8983/solr/fypdata', always_commit=True)
        datae = []
        max_lenE = max(len(coursecode), len(credit_hour), len(subject_names))
        for i in range(max_lenE):
            doc = {
                "id": "elec" + str(i + 1),
                "coursecode": coursecode[i] if i < len(coursecode) else "",
                "credit_hour": credit_hour[i] if i < len(credit_hour) else "",
                "subject_names": subject_names[i] if i < len(subject_names) else "",
                "semester": 'elective'
            }
            datae.append(doc)

        solr.add(datae)
        solr.commit()
        return 'File uploaded and indexed successfully!'

    return render_template('upload.html')


solr = pysolr.Solr('http://localhost:8983/solr/newdata', always_commit=True)


@app.route('/scheme-of-study', methods=['GET', 'POST'])
def schemeofstudy():
    if request.method == 'POST':
        # If the user submitted the search form, update the results based on the selected search option
        query = request.form['query']
        search_option = request.form['search_option']

        if search_option == 'subject':
            query_params = {
                'q': 'subject_names:{0}'.format(query),
                'rows': 10,
                'start': 0,
                'wt': 'json'
            }
        elif search_option == 'coursecode':
            query_params = {
                'q': 'coursecode:{0}'.format(query),
                'rows': 10,
                'start': 0,
                'wt': 'json'
            }
        elif search_option == 'semester':
            query_params = {
                'q': 'semester:{0}'.format(query),
                'rows': 10,
                'start': 0,
                'wt': 'json'
            }

        # Make the Solr request and get the search results
        response = solr.search(**query_params)
        results = response.docs

        # Render the search results page with the updated results
        return render_template('schemeofstudy.html', results=results)

    else:
        # If the user didn't submit the search form, display the data for each semester in separate tables
        first_semester_query_params = {
            'q': 'semester:1st',
            'rows': 10,
            'start': 0,
            'wt': 'json'
        }
        first_semester_response = solr.search(**first_semester_query_params)
        first_semester_results = first_semester_response.docs

        second_semester_query_params = {
            'q': 'semester:2nd',
            'rows': 10,
            'start': 0,
            'wt': 'json'
        }
        second_semester_response = solr.search(**second_semester_query_params)
        second_semester_results = second_semester_response.docs

        third_semester_query_params = {
            'q': 'semester:3rd',
            'rows': 10,
            'start': 0,
            'wt': 'json'
        }
        third_semester_response = solr.search(**third_semester_query_params)
        third_semester_results = third_semester_response.docs

        fourth_semester_query_params = {
            'q': 'semester:4th',
            'rows': 10,
            'start': 0,
            'wt': 'json'
        }
        fourth_semester_response = solr.search(**fourth_semester_query_params)
        fourth_semester_results = fourth_semester_response.docs

        # Render the page with the separate tables for each semester
        return render_template('schemeofstudy.html',
                               first_semester_results=first_semester_results,
                               second_semester_results=second_semester_results,
                               third_semester_results=third_semester_results,
                               fourth_semester_results=fourth_semester_results)




# def delete_all_docs_from_core(core_url):
#     # Create a Solr connection instance
#     solr = SolrConnection(core_url)
#     # Create a query to delete all documents from the core
#     query = '*:*'
#     # Delete all documents matching the query
#     solr.delete_query(query)
#     # Commit the changes to the index
#     solr.commit()
# # Example usage
# if __name__ == '__main__':
#     core_url = 'http://localhost:8983/solr/testsos'
#     delete_all_docs_from_core(core_url)


@app.route('/faculty')
def faculty_dashboard():
    cursor = db.cursor()

    # Query data from the students database
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()

    return render_template('faculty_dashboard.html', students=students)

@app.route('/faculty/new', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        cursor = db.cursor()

        # Check if the student already exists in the database
        cursor.execute("SELECT * FROM students WHERE username=%s", (name,))
        existing_student = cursor.fetchone()
        if existing_student:
            flash("Student already exists.")
            return redirect(url_for('add_student'))

        # If the student does not already exist, insert them into the database
        cursor.execute("INSERT INTO students (username, email, password, user_type) VALUES (%s, %s, %s, %s)", (name, email, password, user_type))

        db.commit()
        return redirect(url_for('faculty_dashboard'))
    return render_template('add_student.html')


@app.route('/faculty/<int:id>/edit', methods=['GET', 'POST'])
def edit_student(id):
    cursor = db.cursor()

    cursor.execute("SELECT * FROM students WHERE id=%s", (id,))
    student = cursor.fetchone()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        cursor = db.cursor()

        cursor.execute("UPDATE students SET username=%s, email=%s, password=%s WHERE id=%s", (name, email, password, id))

        db.commit()
        return redirect(url_for('faculty_dashboard'))

    return render_template('edit_student.html', student=student)


@app.route('/faculty/<int:id>/delete', methods=['POST'])
def delete_student(id):
    cursor = db.cursor()

    cursor.execute("DELETE FROM students WHERE id=%s", (id,))

    db.commit()
    return redirect(url_for('faculty_dashboard'))


@app.route('/about')
def about():
    return render_template('about.html')
@app.route('/contact')
def contact():
    return render_template('contact.html')

if __name__ == '__main__':
    app.run(debug=True, threaded=True, port=5000)

