from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_celery import make_celery
from flask_sqlalchemy import SQLAlchemy
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps
import bluetooth
import time

app = Flask(__name__)

# Config Celery
app.config['CELERY_BROKER_URL'] = 'amqp://localhost//'
app.config['CELERY_BACKEND'] = 'db+mysql://root:admin@localhost/blueatten'

# Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'admin'
app.config['MYSQL_DB'] = 'blueatten'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
# init MYSQL
mysql = MySQL(app)

# Init Celery
celery = make_celery(app)

# Index
@app.route('/')
def index():
    return render_template('home.html')


# About
@app.route('/about')
def about():
    return render_template('about.html')


# Student Register Form Class
class RegisterForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=50), validators.DataRequired()])
    rollno = StringField('Rollno', [validators.Length(min=1, max=3), validators.DataRequired()])
    email = StringField('Email', [validators.Email(), validators.DataRequired()])
    macad = StringField('Macad', [validators.Length(max=17), validators.DataRequired()])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')


# Student Register
@app.route('/registerStu', methods=['GET', 'POST'])
def registerStu():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        rollno = form.rollno.data
        macad = form.macad.data
        password = sha256_crypt.encrypt(str(form.password.data))

        # Create cursor
        cur = mysql.connection.cursor()

        # Execute query
        cur.execute("INSERT INTO students(name, email, rollno, macad, password) VALUES(%s, %s, %s, %s, %s)", (name, email, rollno, macad, password))

        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash('You are now registered and can log in', 'success')

        return redirect(url_for('loginStu'))
    return render_template('registerStu.html', form=form)


# Student login
@app.route('/loginStu', methods=['GET', 'POST'])
def loginStu():
    if request.method == 'POST':
        # Get Form Fields
        email = request.form['email']
        password_candidate = request.form['password']

        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by username
        result = cur.execute("SELECT * FROM students WHERE email = %s", [email])

        if result > 0:
            # Get stored hash
            data = cur.fetchone()
            password = data['password']
            username = data['name']
            macadd = data['macad']

            # Compare Passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session['logged_in'] = True
                session['username'] = username
                session['student'] = True
                session['macaddress'] = macadd
                
                flash('You are now logged in', 'success')
                return redirect(url_for('dashboardStu'))
            else:
                error = 'Invalid login'
                return render_template('loginStu.html', error=error)
            # Close connection
            cur.close()
        else:
            error = 'Username not found'
            return render_template('loginStu.html', error=error)

    return render_template('loginStu.html')




# Professor Register Form Class
class ProfessorForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=50), validators.DataRequired()])
    email = StringField('Email', [validators.Email(), validators.DataRequired()])
    subject = StringField('Subject', [validators.Length(min=1, max=17), validators.DataRequired()])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')


# Professor Register
@app.route('/registerPro', methods=['GET', 'POST'])
def registerPro():
    form = ProfessorForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        subject = form.subject.data
        password = sha256_crypt.encrypt(str(form.password.data))

        # Create cursor
        cur = mysql.connection.cursor()

        # Execute query
        cur.execute("INSERT INTO professors(name, email, subject, password) VALUES(%s, %s, %s, %s)", (name, email, subject, password))

        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash('You are now registered and can log in', 'success')

        return redirect(url_for('loginPro'))
    return render_template('registerPro.html', form=form)


# Professor login
@app.route('/loginPro', methods=['GET', 'POST'])
def loginPro():
    if request.method == 'POST':
        # Get Form Fields
        email = request.form['email']
        password_candidate = request.form['password']

        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by username
        result = cur.execute("SELECT * FROM professors WHERE email = %s", [email])

        if result > 0:
            # Get stored hash
            data = cur.fetchone()
            password = data['password']
            username = data['name']
            sub = data['subject']
            
            # Compare Passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session['logged_in'] = True
                session['username'] = username
                session['student'] = False
                session['subject'] = sub

                flash('You are now logged in', 'success')
                return redirect(url_for('dashboardPro'))
            else:
                error = 'Invalid login'
                return render_template('loginPro.html', error=error)
            # Close connection
            cur.close()
        else:
            error = 'Username not found'
            return render_template('loginPro.html', error=error)

    return render_template('loginPro.html')



# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('index'))
    return wrap

# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('index'))

# Dashboard Student
@app.route('/dashboardStu')
@is_logged_in
def dashboardStu():
    
    macadress = session['macaddress']
    # Create cursor
    cur = mysql.connection.cursor()

    # Get articles
    result = cur.execute("SELECT * FROM attendance WHERE macad = %s", [macadress])

    attends = cur.fetchall()

    print attends

    if result > 0:
        return render_template('dashboardStu.html', attends=attends)
    else:
        msg = 'No Attendance Found'
        return render_template('dashboardStu.html', msg=msg)
    # Close connection
    cur.close()

# Dashboard Professors
@app.route('/dashboardPro')
@is_logged_in
def dashboardPro():
    subject = session['subject']
    # Create cursor
    cur = mysql.connection.cursor()

    # Get attendance
    result = cur.execute("SELECT name, attendance.id, subject, presabs, class_date FROM students, attendance WHERE attendance.macad = students.macad and subject = %s", [subject])

    attends = cur.fetchall()

    if result > 0:
        return render_template('dashboardPro.html', attends=attends)
    else:
        msg = 'No Attendance Found'
        return render_template('dashboardPro.html', msg=msg)
    # Close connection
    cur.close()
    
    
# Check Attendance
@app.route('/check_attendance')
@is_logged_in
def check_attendance():
    sub = session['subject']
    
    # Create cursor
    cur = mysql.connection.cursor()
    
    # Get mac adresses
    result = cur.execute("SELECT macad FROM students")
    
    macads = cur.fetchall()

    print macads
    
    if result > 0:
        bluescan.delay(macads, sub)
        return render_template('scan_prog.html')
    else:
        msg = 'No Records Found'
        return render_template('dashboardPro.html', msg=msg)
    # close connection
    cur.close()

# Celery Task
@celery.task(name='app.bluescan')
def bluescan(macs, subj):
    
    for mac in macs:
        macadd = mac['macad']
        # Create cursor
        cur = mysql.connection.cursor()
        
        result = bluetooth.lookup_name(macadd, timeout=5)
        if (result != None):
            attend = 'present'
            # Execute query
            cur.execute("INSERT INTO attendance(macad, subject, presabs) VALUES(%s, %s, %s)", (macadd, subj, attend))           
        else:
            attend = 'absent'
            # Execute query
            cur.execute("INSERT INTO attendance(macad, subject, presabs) VALUES(%s, %s, %s)", (macadd, subj, attend))
        
        # Commit to DB
        mysql.connection.commit()
        
        # Close Connection
        cur.close()
        
    return 'Done With The Attendance Check'



# Delete Attendance
@app.route('/delete_attendance/<string:id>', methods=['POST'])
@is_logged_in
def delete_attendance(id):
    # Create cursor
    cur = mysql.connection.cursor()

    # Execute
    cur.execute("DELETE FROM attendance WHERE id = %s", [id])

    # Commit to DB
    mysql.connection.commit()

    #Close connection
    cur.close()

    flash('Attendance Deleted', 'success')

    return redirect(url_for('dashboardPro'))

if __name__ == '__main__':
    app.secret_key='secret123'
    app.run(debug=True, host='0.0.0.0')
