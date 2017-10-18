'''
This function handles a Slack slash command and echoes the details back to the user.

Follow these steps to configure the slash command in Slack:

  1. Navigate to https://<your-team-domain>.slack.com/services/new

  2. Search for and select "Slash Commands".

  3. Enter a name for your command and click "Add Slash Command Integration".

  4. Copy the token string from the integration settings and use it in the next section.

  5. After you complete this blueprint, enter the provided API endpoint URL in the URL field.


To encrypt your secrets use the following steps:

  1. Create or use an existing KMS Key - http://docs.aws.amazon.com/kms/latest/developerguide/create-keys.html

  2. Click the "Enable Encryption Helpers" checkbox

  3. Paste <COMMAND_TOKEN> into the kmsEncryptedToken environment variable and click encrypt


Follow these steps to complete the configuration of your command API endpoint

  1. When completing the blueprint configuration select "Open" for security
     on the "Configure triggers" page.

  2. Enter a name for your execution role in the "Role name" field.
     Your function's execution role needs kms:Decrypt permissions. We have
     pre-selected the "KMS decryption permissions" policy template that will
     automatically add these permissions.

  3. Update the URL for your Slack slash command with the invocation URL for the
     created API resource in the prod stage.
'''

import boto3
import json
import logging
import os
import sys
import pymysql.cursors

from base64 import b64decode
from urlparse import parse_qs

import aiml
bot=aiml.Kernel()
bot.learn('uvaClasses.aiml')

ENCRYPTED_EXPECTED_TOKEN = os.environ['kmsEncryptedToken']

kms = boto3.client('kms')
expected_token = kms.decrypt(CiphertextBlob=b64decode(ENCRYPTED_EXPECTED_TOKEN))['Plaintext']

logger = logging.getLogger()
logger.setLevel(logging.INFO)

#Connect to database
DB_HOST = os.environ['db_host']
DB_USER = os.environ['db_user']
DB_PASSWORD = os.environ['db_password']
DB_NAME = os.environ['db_name']

connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, cursorclass=pymysql.cursors.DictCursor)

def respond(err, res=None):
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }

def lambda_handler(event, context):
    params = parse_qs(event['body'])
    token = params['token'][0]
    if token != expected_token:
        logger.error("Request token (%s) does not match expected", token)
        return respond(Exception('Invalid request token'))

    user = params['user_name'][0]
    command = params['command'][0]
    channel = params['channel_name'][0]
    command_text = params['text'][0]

    res = bot.respond(command_text)
    type_res = res.split('$')
    if type_res[0] == 'CMD':
        return respond(None, parse(command_text, type_res[1]))
    else:
        return respond(None, {
            "attachments": [
                {
                    "pretext": command_text,
                    "color": "#36a64f",
                    "text": str(type_res[1])
                }
            ]
        })

def validate(dept, number):
    with connection.cursor() as cursor:
        sql = 'SELECT count(1) FROM `CompSci1178Data` WHERE `Mnemonic`=%s' 
        cursor.execute(sql, dept)
        result = cursor.fetchone()
        if result['count(1)'] <= 0:
            return "I am not aware of that department at the University of Virginia."
        else:
            sql = 'SELECT count(1) FROM `CompSci1178Data` WHERE `Number`=%s' 
            cursor.execute(sql, number)
            result = cursor.fetchone()
            if result['count(1)'] <= 0:
                return "I am not aware of that course at the University of Virginia."
    
    return True

def parse(text, output):
    elements = output.split(' ')
    command = elements[0]

    reference = {
        "attachments": []
    }

    insert_template = {
        "fallback": "RESPONSE",
        "color": "#36a64f"
    }

    attachments = []
    with connection.cursor() as cursor:
        insert = insert_template.copy()
        insert['pretext'] = text
        # insert = {
        #     "fallback": "RESPONSE",
        #     "pretext": text,
        #     "color": "#36a64f",
        # }

        valid_check = validate(elements[1].upper(), elements[2])

        if valid_check == True:
            if command == "meet":
                sql = 'SELECT `Days`, `ClassNumber`, `Type` FROM `CompSci1178Data` WHERE `Mnemonic`=%s AND `Number`=%s'
                cursor.execute(sql, ((elements[1]).upper(), elements[2]))
                result=cursor.fetchall()

                if len(result) > 1:
                    insert['text'] = "There are multiple entries for this class that meet on different days/times."
                    class_values = ""
                    time_values = ""
                    insert['fields'] = []
                    for item in result:                       
                        class_values = class_values + "\n" + str(item['ClassNumber']) + " (" + str(item['Type']) +")"
                        time_values = time_values + "\n" + str(item['Days'])
                    
                    insert['fields'].append({
                        "title": "Class Number (Type)",
                        "value": class_values,
                        "short": True
                    })
                    insert['fields'].append({
                        "title": "Time",
                        "value": time_values,
                        "short": True
                    })
                else:
                    insert["text"] = elements[1].upper() + " " + str(elements[2]) + " meets on " + result[0]['Days']
                
                attachments.append(insert)
            
            elif command == "available":
                sql = 'SELECT `ClassNumber`, `Type`, `Enrollment`, `EnrollmentLimit`, `Waitlist` from `CompSci1178Data` WHERE `Mnemonic`=%s AND `Number`=%s'
                cursor.execute(sql, (elements[1].upper(), elements[2]))
                result=cursor.fetchall()

                if len(result) > 1:
                    insert['text'] = "There are multiple entries for this class that has different enrollment stats."
                    class_values = ""
                    avail_values = ""

                    insert['fields'] = []
                    for item in result:
                        class_values = class_values + "\n" + str(item['ClassNumber']) + " (" + str(item['Type']) +")"
                        diff = item['EnrollmentLimit'] - item['Enrollment']
                        avail_values = avail_values + "\n" + str(diff if diff > 0 else "WL " + str(item['Waitlist']) + 1)
                    insert['fields'].append({
                        "title": "Class Number (Type)",
                        "value": class_values,
                        "short": True
                    })
                    insert['fields'].append({
                        "title": "Availability",
                        "value": avail_values,
                        "short": True
                    })
                else:
                    result = result[0]
                    if result['Enrollment'] < result['EnrollmentLimit']:
                        insert['text'] = "The number of available seats for %s %s is %s" % (elements[1].upper(), elements[2], str(result['EnrollmentLimit']-result['Enrollment'])) 
                    else:
                        insert['text'] = "There are no available seats for %s %s currently. If you decide to enroll you will be on waitlist at position %s" % (elements[1], elements[2], str(result['Waitlist'] + 1))
                
                attachments.append(insert)

            elif command == "about":
                sql = 'SELECT `Description`, `Instructor` FROM `CompSci1178Data` WHERE `Mnemonic`=%s AND `Number`=%s'
                cursor.execute(sql, (elements[1].upper(), elements[2]))
                results = cursor.fetchall()
                Instructor_list = []
                Description_list = []
                for item in results:
                    Instructor_list.append(item['Instructor'])
                    Description_list.append(item['Description'])
                
                Instructor_set = set(Instructor_list)
                Description_set = set(Description_list)

                insert['title'] = "Course Description"
                insert['text'] = ''.join(str(e) for e in list(Description_set))
                # insert['fields'] = []
                # insert['fields'].append({
                #     "title": "Instructor(s)",
                #     "value": ', '.join(str(e) for e in list(Instructor_set)),
                #     "short": False
                # })
                attachments.append(insert)
                attachments.append({
                    "fallback": "RESPONSE",
                        "color": "#36a64f",
                        "title": "Instructors"
                })
                for instructor in list(Instructor_set):
                    attachments.append({
                        "fallback": "RESPONSE",
                        "color": "#36a64f",
                        "title": instructor,
                        "thumb_url": 'https://engineering.virginia.edu/sites/default/files/styles/faculty_headshot/public/' + instructor.replace(" ", "") +'_headshot.jpg'
                    })
        else:
            attachments.append({
                "fallback": "Error",
                "color": "#FF0000",
                "pretext": text,
                "title": "Something went wrong...",
                "text": valid_check
            })            
        reference['attachments'] = attachments
        return reference

# while True:
#     next_ = raw_input()
#     print(bot.respond(next_).replace("*", '\n'))
# sentence = "When does CS 6501 meet?"
# print bot.respond(sentence)