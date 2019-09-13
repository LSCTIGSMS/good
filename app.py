import os
from flask import Flask, url_for, redirect, render_template, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required, current_user
from flask_security.utils import encrypt_password
from werkzeug.utils import secure_filename
import flask_admin
from flask_admin.contrib import sqla
from flask_admin import helpers as admin_helpers
from flask_admin.base import MenuLink, Admin, BaseView, expose
from flask import Flask, Response, session, g, send_file
from flask import render_template_string, flash, send_from_directory, json
import mysql.connector
from flask import jsonify
from datetime import datetime
from twilio import twiml
from twilio.rest import TwilioRestClient
from twilio.rest import Client
import re
import json
from operator import itemgetter
from twilio.twiml.messaging_response import Body, Message, Redirect, MessagingResponse
import requests
import json
import requests
from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey
from sqlalchemy import inspect
import pymysql
from datetime import timedelta
from flask import make_response, request, current_app
from functools import update_wrapper
from flask_cors import CORS
import re
import time


# Create Flask application
app = Flask(__name__)
CORS(app)
app.config.from_pyfile('config.py')
db = SQLAlchemy(app)
app.config['UPLOAD_FOLDER'] = '/static/images/'
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
ALLOWED_EXTENSIONS = ['xlx', 'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif']

# Twilio API Connection
account_sid = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
auth_token = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
client = Client(account_sid, auth_token)
BASE_URL = "https://%s:%s@api.twilio.com" % (account_sid, auth_token)

# MySQL Connection
conn = mysql.connector.connect(host ='xxx.xxx.xxx.xxx', user='userid', password='password', database='dbname')
cursor = conn.cursor()

conn_pymysql = pymysql.connect(host='xxx.xxx.xxx.xxx', port=3306, user='userid', passwd='password', db='dbname')

# Define models
roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)


class Role(db.Model, RoleMixin):
    """Define Role schema model which is used to define a user's access within TextExpress.

    :param id: The _id field in the database. Unique Primary Key.
    :type id: integer
    :param name: The name of the role. Example: User, Admin, Super User
    :type name: string (80)
    :param description:  Description of the role and the abilities that it has in the system.
    :type description: string (255)

    """
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

    def __str__(self):
        """ Used in an Str() call, the instance's name property is used to represent the role.

            :rtype: string

        """
        return self.name


class User(db.Model, UserMixin):
    """Define User schema model which is used to create a user record within TextExpress.

    :param id: The id field in the database. Unique Primary Key.
    :type id: integer
    :param first_name : The first name of the user.
    :type name: string (255)
    :param last_name : The last name of the user.
    :type name: string (255)
    :param email:  Email address used for registration. Unique.
    :type email: string (255)
    :param twilio_phone_number: Phone number used to send and receive text from contacts.
    :type twilio_phone_number: string (12)
    :param password: The user password used to log in to TextExpress. Encrypted string.
    :type password: string (255)
    :param active: Describes if the acount is active or not. Inactive accounts don't have access.
    :type active: boolean
    :param confirmed_at: Date the user's email account was confirmed.
    :type confirmed_at: SqlAlchemy.DateTime()
    :param role: Describes a User's access. Foreign key from the Roles table.
    :type role: int

    """
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    twilio_phone_number = db.Column(db.String(12))
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))

    def __str__(self):
        """ Used in an Str() call, the instance's email property is used to represent the user.

            :rtype: string

        """
        return self.email


# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)

can_view = ''
# Create customized model view class
class MyModelView(sqla.ModelView):
    """ Determines whether a view is accessible to the user based upon assigned roles.

    """
    def is_accessible(self):
        """ Checks for authentication and role. 

        :rtype: boolean
        """
        if not current_user.is_active or not current_user.is_authenticated:
            return False
            can_view = False
        if current_user.has_role('superuser'):
            can_view = True
            return True

        # return False

    def _handle_view(self, name, **kwargs):
        """
        Override builtin _handle_view in order to redirect users when a view is not accessible.

        :rtype: Forbidden error 403 or URL Redirect to login page.

        """
        if not self.is_accessible():
            if current_user.is_authenticated:
                # permission denied
                abort(403)
            else:
                # login
                return redirect(url_for('security.login', next=request.url))


def crossdomain(origin=None, methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    """ CORS cross-domain management function.

    Used to set response headers when communicating used by outside domain API calls. See `MDN Article CORS - <https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS>` _ for more information.

    :param origin: The value of the origin in the request header.
    :type origin: string | string[]
    :param methods: Define allowable methods for CORS preflight. GET, POST, PUT, DELETE, etc.
    :type methods: string | string[]
    :param max_age: The maximum age for the CORS policy. Default: 21600 seconds.
    :type max_age: integar | DateTime.timedelta
    :param attach_to_all: Set headers on all origins defined. Default: True
    :type attach_to_all: boolean

    """
    # Create a comma separated string of methods from a list
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    # Create a comma separated string of headers from a list
    if headers is not None and not isinstance(headers, basestring):
        headers = ', '.join(x.upper() for x in headers)
    # Create a comma separated list of origins
    if not isinstance(origin, basestring):
        origin = ', '.join(origin)
    # If received DateTime object delta, convert to seconds
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        """ returns the list of methods as a string

            :rtype: string
        """
        if methods is not None:
            return methods
       
        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    @app.after_request
    def after_request(response):
        """ Sets the headers to allow cross-site requests if authorized from any domain.

        :rtype: HTTP.response

        """
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response




# Flask views

@app.route('/')
def index():
    return render_template('index.html')


class MyView(BaseView):
    @expose('/')
    def index(self):
        return self.render('admin/index.html')





@app.route('/upload', methods=['POST'])
def upload():
    """ Upload and send an image attachment to be used in a text message.

    POST: Receives a file image attachment.
    :param phone: Outbound telephone number.
    :param media_id: id of the media object.
    :param file: The file to be imported.

    Response::
    200OK
    content-type: JSON
    {
        user_twilio_phone_number: ###-###-###,
        file_size: n bytes
    }

    Saves images to /images folder on the web root.

    """
    user_twilio_phone_number = current_user.twilio_phone_number
    # files = request.files['file']

    outbound_number = request.values.get('phone', None)
    clean_outbound_number = re.sub("\D", "", outbound_number)
    media_id = request.values.get('media_id', None)

    media_counter = 0

    file = request.files['file']
    # if user does not select file, browser also
    # submit a empty part without filename
    if file.filename == '':
        
        return jsonify(user_twilio_phone_number=user_twilio_phone_number, size='file_size')
    # if (ext == ".jpg") or (ext == ".jpeg") or(ext == ".png" or (ext == ".pdf") or (ext == ".doc")):
    #     print("File supported moving on...")
    # else:
    target = os.path.join(APP_ROOT, 'static/{}'.format('images'))
    # filename = str(media_id) + "_" + upload.filename
    # filename = media_id + '_' + upload.filename

    filename = secure_filename(file.filename)
    destination = "/".join([target, filename])
    file.save(destination)
    try:
        # Create a new record
        query = "INSERT INTO mms(mms_id, sms_id, new_media_name, from_phone, to_phone, sms_table_id) VALUES (%s,%s,%s,%s,%s,%s)"
        cursor.execute(query, (media_id, '', filename, user_twilio_phone_number, clean_outbound_number, 1))
        conn.commit()

    except mysql.connector.Error as err:
        print("Error inserting into sms table: {}".format(err))

   
    
    return jsonify(user_twilio_phone_number=user_twilio_phone_number, size='file_size')



# Create admin
admin = flask_admin.Admin(
    app,
    'Text_Express',
    base_template='my_master.html',
    template_mode='bootstrap3',
)

# Add model views
admin.add_view(MyView(name='LASOC Groups'))
admin.add_view(MyModelView(Role, db.session))

admin.add_view(MyModelView(User, db.session))


@security.context_processor
def security_context_processor():
    return dict(
        admin_base_template=admin.base_template,
        admin_view=admin.index_view,
        h=admin_helpers,
        get_url=url_for
    )


# Routes
@app.route('/load_simple_phone_book', methods=['GET'])
def load_simple_phone_book():
    """ Load a user's phone book with simplified display from the database.

    GET: Returns a list of client contacts from the phonebook. Simplified view.
    :param contact_type: Active or inactive contact.

    Response::
    200OK
    content-type: JSON
    {
        a_list: [
            {
                "id": "1234",
                "contact_phone": "###-###-####",
                "first_last": "john doe"
            },
            {
                "id": "1235",
                "contact_phone": "###-###-####",
                "first_last": "jane doe"
            }
        ]
    }

    """
    # This time use pymysql... just because...
    a_list = []
    cur = conn_pymysql.cursor()

    contact_type = request.args.get('contact_type', 0, type=str)
    user_twilio_phone_number = current_user.twilio_phone_number
    query = ("SELECT id, contact_phone, CONCAT(contact_first_name,' ',contact_last_name) FROM contact_1 where contact_active = %s and attorney_twilio_number = %s")
   
    cur.execute(query, (contact_type, user_twilio_phone_number,))

    try:
        for row in cur._rows:
            a_list.append(row)
    except Exception as e:
        print(e)
        self.connection.rollback()
    

    return jsonify(a_list)



@app.route('/load_extended_phone_book', methods=['GET'])
def load_extended_phone_book():
    """ Load a contact's detailed information from the database in the phone book view.

    GET: Returns a single contact with a more complete list of details from the phonebook by id.
    :param id: id of the user.

    Responses::
    200 OK
    content-type: JSON
    {
        {
            "id": "1234",
            "contact_phone": "###-###-####",
            "first_name": "john",
            "last_name": "doe",
            "phone_number": "###-###-####",
            "email": "john.doe@gmail.com",
            "contact_active": "true",
            "contact_notes":"Upcoming court date on June 2nd."
        }
        
    }

    500 Server Error - Failure to update.

    """
    id = request.args.get('id', 0, type=str)
    a_list = ''
    print(id)

    try:
        query = "SELECT id, contact_first_name, contact_last_name, contact_phone, contact_email, contact_case_number, contact_active, contact_notes from contact_1 where id = '%s'" % id
        cursor.execute(query)
        a_list = cursor.fetchall()

    except mysql.connector.Error as err:
        print("Error from route contact_list(): {}".format(err))
        return_string = "Failure to update: {}".format(err)

    print(a_list)
    return jsonify(a_list)

@app.route('/update_contact', methods=['GET'])
def update_contact():
    """ Update a contact's information

    GET: Updates a specified contact's information in the phone book.

    :param phone_book_id: id of the contact to be updated.
    :param insert_update: If this is a new entry, this value is "Insert", otherwise update.
    :param first_name: contact's first name.
    :param last_name: contact's surname.
    :param phone_number: contact's phone number.
    :param is_active: Whether the contact is active. true or false value.
    :param email: Contact's email address.
    :param case_number: Case number related to the contact.
    :param notes: Addional notes.

    Responses::
    200 Success
    500 Server Error - Failure to Save/Update.

    """
    return_string = 'good'
    d = datetime.today().strftime('%Y-%m-%d %H:%M')
    phone_book_id = request.args.get('phone_book_id', 0, type=str)
    insert_update = request.args.get('insert_update', 0, type=str)
    first_name = request.args.get('first_name', 0, type=str)
    last_name = request.args.get('last_name', 0, type=str)
    phone_number = request.args.get('phone_number', 0, type=str)
    user_twilio_phone_number = current_user.twilio_phone_number
    is_active = request.args.get('is_active', 0, type=str)
    email = request.args.get('email', 0, type=str)
    case_number = request.args.get('case_number', 0, type=str)
    notes = request.args.get('notes', 0, type=str)
    # contact_type = request.args.get('contact_type', 0, type=str)
    
    #Add new record.
    if insert_update == 'Insert': 
        try:
            query = "INSERT INTO contact_1 (contact_date_updated, contact_first_name, contact_last_name, contact_phone, contact_email, contact_case_number, contact_active, contact_notes, attorney_twilio_number) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            cursor.execute(query, (d, first_name, last_name, phone_number, email, case_number, is_active, notes, user_twilio_phone_number))

            conn.commit()
        except mysql.connector.Error as err:
            print("Error from route contact_list(): {}".format(err))
            return_string = "Failure to save: {}".format(err)
    
    #Update existing record.
    else:
        try:
            query = "update contact_1 set contact_date_updated=%s, contact_first_name=%s, contact_last_name=%s, contact_phone=%s, contact_email=%s, contact_case_number=%s, contact_active=%s, contact_notes=%s, attorney_twilio_number=%s where id=%s"
            cursor.execute(query, (d, first_name, last_name, phone_number, email, case_number, is_active, notes, user_twilio_phone_number, phone_book_id))
            conn.commit()
        except mysql.connector.Error as err:
            print("Error from route contact_list(): {}".format(err))
            return_string = "Failure to update: {}".format(err)
            
    return return_string



@app.route('/delete_contact', methods=['GET'])
def delete_contact():
    """ Delete a given contact from the phone book.

    GET: Should return 'good' upon successful deletion.

    :phone_book_id: id of the contact to be deleted.

    200 OK: good
    500 Server Error: Failure to Delete.
    """
    return_string = 'good'
    phone_book_id = request.args.get('phone_book_id', 0, type=str)
    #Delete record.
    try:
        query = "DELETE FROM contact_1 WHERE id = %s"
        cursor.execute(query, (phone_book_id,))

        conn.commit()

    except mysql.connector.Error as err:
        print("Error from route contact_list(): {}".format(err))
        return_string = "Failure to delete: {}".format(err)

    return dict(
        title=return_string
    )


try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin

import requests


@app.route('/load_group_requests', methods=['GET'])
def load_group_requests():
    """ Get group of SMS fields as a single string

        Get: Receive a group of SMS messages in a single string
        :param contact_type: Active or inactive

        Response::
        200OK
        content-type: JSON
        {
            "a_list" : [
                "date": "2019-05-30 8:30AM",
                "fr_phone_number": "###-###-####",
                "sms_note": "As per our discussion,"
            ]
        }
    """
    # This time use pymysql... just because...
    a_list = []
    cur = conn_pymysql.cursor()

    contact_type = request.args.get('contact_type', 0, type=str)

    query = ("SELECT CONCAT (DAYNAME(sms.sms_create_date), ' ', DATE_FORMAT(sms.sms_create_date, '%h:%i %p')), sms.fr_phone_number, sms.sms_note FROM sms")
    
    cur.execute(query)

    try:
        for row in cur._rows:
            a_list.append(row)
    except Exception as e:
        print(e)
        self.connection.rollback()
    

    return jsonify(a_list)
    




#--------------------------------------------------------
#SMS Routes
#--------------------------------------------------------
from PIL import Image
import requests
from io import BytesIO
import requests

@app.route('/load_convo', methods=['GET'])
def load_conversation():
    """ Load an SMS conversation from conversation history. List option determines the view.

    GET: Load SMS conversation from contact. The List option will determine whether the messages displayed are your last text messages when no list option is provided, or if they are from a specific person.

    :param from: The sender of the SMS message. Inbound message.
    :param list_option: 'single' or phone number ###-###-####
    """
    twilio_phone_number = current_user.twilio_phone_number
    inbound_number = request.values.get('From', None)
    list_option = request.values.get('list_option', None)
    a_list = []
    
    try:
        if(list_option == 'single'):
            query = ("SELECT sms.*, contact_1.contact_first_name, contact_1.contact_last_name from sms INNER JOIN contact_1 ON contact_1.contact_phone = sms.sms_phone where sms.id IN (SELECT MAX(sms.id) from sms WHERE sms.to_phone_number = %s OR sms.fr_phone_number = %s GROUP BY sms_phone) ORDER BY sms.id desc")
            cursor.execute(query, (twilio_phone_number, twilio_phone_number))
        else:
            query2 = """ UPDATE sms
                SET sms_viewed = %s
                WHERE sms.to_phone_number = %s """
        
            data = ("1", str(list_option))
        
            try:
            
                # update book title
                cursor2 = conn.cursor()
                cursor2.execute(query2, data)
        
                # accept the changes
                conn.commit()
        
            except Error as error:
                print(error)
            
            query = ("SELECT sms.*, contact_1.contact_first_name, contact_1.contact_last_name,mms.new_media_name FROM sms LEFT OUTER JOIN mms ON mms.mms_id = sms.media_id INNER JOIN contact_1 ON contact_1.contact_phone = sms.sms_phone where to_phone_number = %s or fr_phone_number = %s ORDER BY sms.id ASC")
            cursor.execute(query, (list_option, list_option))

        a_list = cursor.fetchall() 
    except mysql.connector.Error as err:
            print("Error from route contact_list(): {}".format(err))
            return_string = "Failure to update: {}".format(err)

    return jsonify(a_list)




"""INCOMMING SMS FROM CLIENT."""
@app.route('/sms',  methods=['GET', 'POST'])
def sms_reply():
    """ Receive SMS Message as text, doc, or image to be stored for user from contact.

    GET: User reading the incomming message from the contact.
    POST: User reading the incomming message from the contact.

    :param from: Inbound phone number from client.
    :param to: Outbound phone number from attorney.
    :param body: message body
    :param messageid: message id of the inbound message.
    :param mediaUrl0: url for the attachment. Must be supported mime-type jpg, jpeg, pdf or doc. 
    :param smsmessageid: message id of twilio message.

    Response::
    200OK - asdf
    500 Server Error - Error inserting into SMS table
    """
    print("INCOMMING SMS FROM CLIENT.")
    #from client
    inbound_number = request.values.get('From', None)
    inbound_number = inbound_number[2:]
    #to attorney
    outbound_number = request.values.get('To', None)
    outbound_number = outbound_number[2:]
    
    inbound_message = request.values.get('Body', None)
    inbound_message_id = request.values.get('MessageSid', None)

    caller_test = get_caller_info(inbound_number)
    checker = 0

    MediaUrl0 = request.values.get('MediaUrl0', None)
    SmsMessageSid = request.values.get('SmsMessageSid', None)
    
    if MediaUrl0 != None:
        
        target = os.path.join(APP_ROOT, 'static/{}'.format('images'))
        
        filename = SmsMessageSid
        # This is to verify files are supported
        ext = request.values.get('MediaContentType0', None)
        
        if ("jpg" in ext or "jpeg" in ext or "png" in ext or "pdf" in ext or "doc" in ext):
            print("File supported moving on...")
        else:
            render_template("Error.html", message="Files uploaded are not supported...")

        destination = "/".join([target, filename])
        print("Accept incoming file:", filename)
        print("Save it to:", destination)

        response = requests.get(MediaUrl0)
        img = Image.open(BytesIO(response.content))
        img.save(destination + '.jpg')    


        try:
            # Create a new record
            query = "INSERT INTO mms(mms_id, sms_id, new_media_name, from_phone, to_phone, sms_table_id) VALUES (%s,%s,%s,%s,%s,%s)"
            cursor.execute(query, (filename, '', filename + '.jpg', inbound_number, outbound_number, 1))
            conn.commit()

        except mysql.connector.Error as err:
            print("Error inserting into sms table: {}".format(err))


    return_string = 'Hello '
    first_name = ''

    #First save to Scheduler:
    now = datetime.now()
    year =now.year
    month =now.month
    day = now.day
    hour = now.hour
    minute = now.minute
    phone = inbound_number
    message = inbound_message
    case_number = ''
    desc = 'Incoming from client through Twilio.'
    
    try:
        # Create a new record
        try:
         
            query = "INSERT INTO sms (sms_create_date, sms_sched_year,  sms_sched_month,  sms_sched_day,  sms_sched_hour,  sms_sched_minute,  sms_phone,  sms_note, sms_case_number, sms_desc, sms_direction, sms_sent, fr_phone_number, to_phone_number,media_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            cursor.execute(query, (datetime.now().strftime("%Y-%m-%d %H:%M"), year, month, day, hour, minute, phone, inbound_message, case_number, desc, "inbound", "0", inbound_number, outbound_number, inbound_message_id))
            last_id = cursor.lastrowid
            conn.commit()
         

        except mysql.connector.Error as err:
                    print("Error inserting into sms table: {}".format(err))

    except mysql.connector.Error as err:
        print("Error inserting into sms table: {}".format(err))

        return "Error inserting into sms table."


    

    

#--------------------------------------------------------
#                LOOK FOR CODES
#--------------------------------------------------------
    try:
      
       phone_number = inbound_number
       query = ("SELECT contact_first_name, contact_last_name from contact where contact_phone = '%s'" % phone_number)
       cursor.execute(query, ())
       a_list = cursor.fetchall() 
       for row in a_list:
           return_string += row[0]
           first_name = row[0]
           return_string += ' '
           return_string += row[1]
           return_string += '!'
           return_string += '\rtext #help for a list of available commands'
   
    except mysql.connector.Error as err:
       print("Error from route contact_list(): {}".format(err))
  
          
    #Look for Key Words, just a couple of silly examples, could easily query db for real data.
    word_list = inbound_message.split(' ')
    for item in word_list:
       if item == '#help':
           checker = 1
           return_string = ''
           return_string += '#time\r'
           return_string += '#meetings\r'
        
       elif item == '#time':
           checker = 1
           now_utc = datetime.now(timezone('UTC'))
           now_pacific = now_utc.astimezone(timezone('US/Pacific'))
           return_string += ' The current time is ' +str(now_pacific.strftime("%I:%M %p"))
       elif item == '#meetings':
           checker = 1
           return_string = 'Hey ' + first_name + ', you have 4 meetings.'
      
       else:
           return_string += ''

   
    print(return_string)
    resp = MessagingResponse()
    if checker == 1:
       resp.message(return_string)
     
        
   
    return str('asdf')


def get_caller_info(inbound_number):
    """ Get SMS information for contact by the inbound_number

    :param inbound_number: The inbound telephone number for the contact.
    :rtype: string[], the sms information of the contact
    """
    query = ("SELECT sms_case_number, sms_desc from sms where sms_phone = '%s'" % inbound_number)
    cursor.execute(query, ())
    a_list = cursor.fetchall() 


    return a_list


"""INCOMMING SMS FROM ATTORNEY (or Matrix)."""
@app.route('/sms_sched', methods=['GET', 'POST'])
def sms_sched():
    """ Message sent from user to the sms scheduler as text, doc or img - jpg, jpeg, doc, pdf.
    
    GET: Contact is sent a message from the user.
    POST: Contact is sent a message from the user.

    :param media_id: id of the media file.
    :param year: year.
    :param month: month.
    :param day: day.
    :param hour: hour.
    :param minute: minute.
    :param phone: phone number of the contact.
    :param message: The content of the sms message.
    :param case_number: case number for the contact and user.
    :param desc: description of the sms.

    Response::
    200OK: 

    """
    error_string = ""
    
    user_twilio_phone_number = current_user.twilio_phone_number
    
    media_id = request.values.get('media_id', None)
   
    year = request.values.get('year', None)
    month = request.values.get('month', None)
    day = request.values.get('day', None)
    hour = request.values.get('hour', None)
    minute = request.values.get('minute', None)
    if minute == '':
        minute = 0
    phone = request.values.get('phone', None)
    message = request.values.get('message', None)
    case_number = request.values.get('case_number', None)
    desc = request.values.get('desc', 0, type=str)
  
    if error_string == '':
        try:
            # Create a new record
            query = "INSERT INTO sms (sms_create_date, sms_sched_year,  sms_sched_month,  sms_sched_day,  sms_sched_hour,  sms_sched_minute,  sms_phone,  sms_note, sms_case_number, sms_desc, sms_sent, sms_direction, media_id, to_phone_number, fr_phone_number) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            cursor.execute(query, (datetime.now().strftime("%Y-%m-%d %H:%M"), year, month, day, hour, minute, phone, message, case_number, desc,"0", "outbound", media_id, phone, user_twilio_phone_number))

            conn.commit()

        except mysql.connector.Error as err:
            print("Error from route contact_list(): {}".format(err))
            return_string = "Failure to save: {}".format(err)

        finally:
            blah = ''
            #conn.close()
    else:
        print(error_string)

    if error_string == '':
        error_string = 'Message Saved Succesfully!'


    return ""



def remove_prefix(text, prefix):
    """ Utility that removes the given prefix from a string and returns the trimmed value.
    
    :param text: The text that is used as the source string.
    :type text: string
    :param prefix: The prefix that will be trimmed from string.
    :type prefix: string
    :rtype: string

    """
    if text.startswith(prefix):
        return text[len(prefix):]
    return text 



if __name__ == '__main__':

   
    app.run(host='0.0.0.0', port=5000)
    
