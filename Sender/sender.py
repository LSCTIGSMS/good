import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import schedule
import datetime
import time
import threading
import pymysql.cursors
from twilio.rest import Client
from tornado.options import define, options
import mysql.connector


account_sid = "xxxxxxxxxxxxxxxxxxxxxxxx"
auth_token = "xxxxxxxxxxxxxxxxxxxxxxxxxxx"
client = Client(account_sid, auth_token)

define("port", default=8888, help="run on the given port", type=int)

#SENDER
def job():
    print('Start Job....')
    connection = pymysql.connect(host='xxx.xxx.xxx.xxx',
                                     user='user',
                                     password='password',
                                     db='dbname',
                                     charset='utf8mb4',
                                     cursorclass=pymysql.cursors.DictCursor)

    cur = connection.cursor()
    current_date = time.strftime("%m/%d/%Y")
    now = datetime.datetime.now()

    return_string = now.strftime("%Y-%m-%d %H:%M:%S") + '  Listening on 8888...'
  
    try:
        # Send anything older than today in case of error or server shutdown
        cur.execute("SELECT * FROM sms where sms.sms_sent = '0' AND sms_sched_year <='" + str(now.year) + "' AND TRIM(LEADING '0' FROM sms_sched_month) <=" + str(int(now.month)) + " AND TRIM(LEADING '0' FROM sms_sched_day) <" + str(int(now.day)))
        if cur.rowcount > 0:
            for row in cur:
                i_d =  str(row['id'])
                cur.execute("UPDATE sms set sms.sms_sent=1 where sms.id =" + i_d)
                connection.commit()
                message = client.messages.create(to=row['sms_phone'], from_="+phonenumber", body=row['sms_note'], status_callback="http://callaw.org:5555/verify_sms")

                print('Database Updated.')        


    except:
        print("Exception hit!")
        # Raise the exception again.
        raise

    finally:
        print(return_string)

    cur.close()
  
    connection.close()
    #Delete any MMS attachents that are stored on Twilio for security reasons.

    connection = pymysql.connect(host='xxx.xxx.xxx.xxx',
                                     user='user',
                                     password='password',
                                     db='database name',
                                     charset='utf8mb4',
                                     cursorclass=pymysql.cursors.DictCursor)

    cur = connection.cursor()

    cur = connection.cursor()
    cur.execute("SELECT sms_id, mms_id FROM mms where mms.removed_from_twilio = 0")

    if cur.rowcount > 0:
        for row in cur:
            media_id = str(row['mms_id'])
            print('media_id ' + media_id)
            message_id = str(row['sms_id'])
            print('message_id ' + message_id)
            try:
                client.messages(message_id) \
                .media(media_id) \
                .delete()
                print('Media Deleted. Media Id: ' + media_id)

                # Now update MMS so that we are not trying to delete an image that is already delted
                try:
                    query = "update mms set removed_from_twilio=1 where mms_id=%s"
                    cur.execute(query, (media_id))
                    connection.commit()

                except mysql.connector.Error as err:
                    print("Error from route contact_list(): {}".format(err))
                    return_string = "Failure to update: {}".format(err)

            except mysql.connector.Error as err:
                print("Error from route contact_list(): {}".format(err))
    cur.close()
    connection.close()


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    job_thread.start()


schedule.every(10).seconds.do(run_threaded, job)

#
while True:
    schedule.run_pending()
    time.sleep(1)



class MainHandler(tornado.web.RequestHandler):
    def get(self):
        #self.render("index.html")
       
        self.write("Hello from John!")


def main():
    tornado.options.parse_command_line()
    application = tornado.web.Application([
        (r"/", MainHandler),
    ])
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(options.port)
#    tornado.ioloop.IOLoop.current().start()
    tornado.ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=5), self.main)



class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler)
        ]
        tornado.web.Application.__init__(self, handlers)



if __name__ == "__main__":
    main()
    
