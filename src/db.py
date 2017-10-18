import sys
import os
import pymysql.cursors

command = sys.argv[1]

#Connect to database
DB_HOST = os.environ['db_host']
DB_USER = os.environ['db_user']
DB_PASSWORD = os.environ['db_password']
DB_NAME = os.environ['db_name']

connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, cursorclass=pymysql.cursors.DictCursor)

try:
    with connection.cursor() as cursor:
        if command == "meet":
            sql = 'SELECT `Days`, `ClassNumber` FROM `CompSci1178Data` WHERE `Mnemonic`=%s AND `Number`=%s'
            cursor.execute(sql, ((sys.argv[2]).upper(), sys.argv[3]))
            result=cursor.fetchall()
            if len(result) > 1:
                print("There are multiple sections for this class that meet on different days/times.")
                
                for item in result:
                    print "%s \t meets on \t %s \n" % (item['ClassNumber'], item['Days'])
            else:
                print "%s meets on %s" % (((sys.argv[2]).upper() + " " + str(sys.argv[3])), result['Days'])
        elif command == "available":
            sql = 'SELECT `Enrollment`, `EnrollmentLimit`, `Waitlist` from `CompSci1178Data` WHERE `Mnemonic`=%s AND `Number`=%s'
            cursor.execute(sql, (sys.argv[2].upper(), sys.argv[3]))
            result=cursor.fetchone()
            if result['Enrollment'] != result['EnrollmentLimit']:
                print "The number of available seats for %s %s is %s" % (sys.argv[2], sys.argv[3], result['EnrollmentLimit']-result['Enrollment'])
            else:
                print result
                print "There are no available seats for %s %s currently. If you decide to enroll you will be on waitlist at position %s" % (sys.argv[2], sys.argv[3], result['Waitlist'])
finally:
    connection.close()