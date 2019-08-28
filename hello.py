#!/usr/bin/env python

from cloudant import Cloudant
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import atexit
import os
import json
import random
import uuid
from twilio.twiml.messaging_response import MessagingResponse
import googlemaps
# from IPython import embed
from ibm_watson import NaturalLanguageUnderstandingV1
from ibm_watson.natural_language_understanding_v1 import Features, KeywordsOptions
import gensim
import prioritize_health
gmaps = googlemaps.Client(key='AIzaSyA7bV-H25Upx5HMPLQ_-5zDGfNNTypK6u4')

app = Flask(__name__, static_url_path='')
CORS(app)
app.secret_key = 'BRYANHPCHIANG' + str(random.randint(1, 1000000000))

db_name = 'rove'
client = None
db = None

suggested_hygiene_supplies=["Tooth brush","Toothpaste","Tissues","Toliet paper","Tampons","Pads"]
suggested_health_supplies=["Bandage","Gauze"]
DELIM=", "

if 'VCAP_SERVICES' in os.environ:
    vcap = json.loads(os.getenv('VCAP_SERVICES'))
    print('Found VCAP_SERVICES')
    if 'cloudantNoSQLDB' in vcap:
        creds = vcap['cloudantNoSQLDB'][0]['credentials']
        user = creds['username']
        password = creds['password']
        url = 'https://' + creds['host']
        client = Cloudant(user, password, url=url, connect=True)
        db = client.create_database(db_name, throw_on_exists=False)
elif "CLOUDANT_URL" in os.environ:
    client = Cloudant(os.environ['CLOUDANT_USERNAME'],
                      os.environ['CLOUDANT_PASSWORD'],
                      url=os.environ['CLOUDANT_URL'],
                      connect=True)
    db = client.create_database(db_name, throw_on_exists=False)
elif os.path.isfile('vcap-local.json'):
    with open('vcap-local.json') as f:
        vcap = json.load(f)
        print('Found local VCAP_SERVICES')
        creds = vcap['services']['cloudantNoSQLDB'][0]['credentials']
        user = creds['username']
        password = creds['password']
        url = 'https://' + creds['host']
        client = Cloudant(user, password, url=url, connect=True)
        db = client.create_database(db_name, throw_on_exists=False)
# embed()

# client.delete_database(db_name)
# On IBM Cloud Cloud Foundry, get the port number from the environment variable PORT
# When running this app on the local machine, default the port to 8000
port = int(os.getenv('PORT', 8000))
model = gensim.models.KeyedVectors.load_word2vec_format('GoogleNews-vectors-negative300-SLIM.bin', binary=True)
print("Model loaded")

@app.route('/')
def root():
    return app.send_static_file('index.html')


# /* Endpoint to greet and add a new visitor to database.
# * Send a POST request to localhost:8000/api/visitors with body
# * {
# *     "name": "Bob"
# * }
# */
@app.route('/api/visitors', methods=['GET'])
def get_visitor():
    if client:
        return jsonify(list(map(lambda doc: doc['name'], db)))
    else:
        print('No database')
        return jsonify([])

# /**
#  * Endpoint to get a JSON array of all the visitors in the database
#  * REST API example:
#  * <code>
#  * GET http://localhost:8000/api/visitors
#  * </code>
#  *
#  * Response:
#  * [ "Bob", "Jane" ]
#  * @return An array of all the visitor names
#  */
@app.route('/api/visitors', methods=['POST'])
def put_visitor():
    user = request.json['name']
    data = {'name': user}
    if client:
        my_document = db.create_document(data)
        data['_id'] = my_document['_id']
        return jsonify(data)
    else:
        print('No database')
        return jsonify(data)

def get_health_priority(doc):
    sentence=doc['health']['health_description']
    print("Sentence={}".format(sentence))

    keywords,priority_score=prioritize_health.prioritize_health(sentence,model)
    return keywords,priority_score

def get_hygiene_priority(doc):
    return len(doc['hygiene']['needed_hygiene_supplies'])/5

def get_food_priority(doc):
    num_people=doc['food']['n_people']
    num_days_left=doc['food']['num_days_left']
    raw_priority=float(num_people)/num_days_left
    # min(x)=1,max(x)=10
    return (raw_priority-1)/9

def update_priority_scores():
    for doc in db:
        health_key_words,health_priority=get_health_priority(doc)
        food_priority=get_food_priority(doc)
        hygiene_priority=get_hygiene_priority(doc)
        doc['health']['priority']=health_priority
        doc['health']['key_words']=health_key_words
        doc['food']['priority']=food_priority
        doc['hygiene']['priority']=hygiene_priority
        doc.save()

@app.route("/users",methods=['GET'])
def users():
    # Calculate individual priority scores for each user
    update_priority_scores()
    for doc in db:
        print(doc)
    return jsonify([doc for doc in db])

@app.route("/sms", methods=['GET', 'POST'])
def sms():
    counter = session.get('counter', 0)
    counter += 1
    session['counter'] = counter
    resp = MessagingResponse()
    data = request.values
    msg = data.get('Body', None)
    if not msg:
        session['counter']=0
        return str(resp.message("Sorry, I didn't get that. Try again? Enter START to begin if you haven't already."))
    msg=str(msg)
    print(msg)
    if 'id' in session:
        doc=db[session['id']]
    else:
        doc=db.create_document({'_id':str(uuid.uuid4())})
        session['id']=doc['_id']
    if counter == 1:
        if not msg == 'START':
            resp.message("{} Sorry, I didn't quite understand that. Enter START to begin the process.".format(msg))
            session['counter'] = 0
        else:
            resp.message("Hi, what is your name and phone number? Separate the two with a comma please.")
    elif counter == 2:
        # Get the user's name
        name,phone_number=msg.split(",")
        phone_number=int(phone_number)
        resp.message("Great to meet you, {}! What is your address the moment?".format(name))
        # Add them to the database
        doc['name']=name
        doc['phone_number']=phone_number
    elif counter==3:
        address=msg
        # Geocode the address
        geocode_result=gmaps.geocode(address)
        if not geocode_result:
            resp.message("Sorry, we couldn't find anything for that address. Try again?")
            session['counter']-=1
        else:
            top_result=geocode_result[0]
            doc['location_information']=top_result
            doc.save()
            resp.message("Great, we determined your address to be {}. \n Now we're going to ask a few questions about your health. First, describe any medical issues you're facing."
                .format(top_result["formatted_address"]))
    elif counter==4:
        health_description=msg
        print(health_description)
        doc['health']={}
        doc['health']['health_description']=health_description
        resp.message("\n".join([
            "Do you need any specific medical supplies?",
            "Here are some suggestions: {}".format(DELIM.join(suggested_health_supplies)),
            ]))
    elif counter==5:
        health_supplies_needed=msg.replace(',','').split(" ")
        print(health_supplies_needed)
        doc['health']['health_supplies_needed']=health_supplies_needed
        resp.message("Noted. Second, how many people are with you?")
    elif counter==6:
        doc['food']={}
        doc['food']['n_people']=int(msg)
        resp.message("Got it. What are the ages of all the males? Separate your answer with a comma.")
    elif counter==7:
        ages=[int(x.strip()) for x in msg.split(",")]
        doc['food']['male_ages']=ages
        resp.message("Got it. What is the ages of all the females? Separate your answer with a comma.")
    elif counter==8:
        ages=[int(x.strip()) for x in msg.split(",")]
        doc['food']['female_ages']=ages
        resp.message("Got it. How many days of food/water do you have left?")
    elif counter==9:
        num_days_left=int(msg)
        doc['food']['num_days_left']=num_days_left
        resp.message("\n".join([
            "Got it, we'll be sending some supplies over.",
            "Third, do you need any personal hygiene supplies?",
            "Here are some suggested options: {}".format(DELIM.join(suggested_hygiene_supplies)),
        ]))
    elif counter==10:
        needed_hygiene_supplies=msg.replace(',','').split(" ")
        doc['hygiene']={}
        doc['hygiene']['needed_hygiene_supplies']=needed_hygiene_supplies
        # Potentially ask about need for shelter
        resp.message("Great. That's all the questions we have for now - we'll text you if we have any updates.")
    doc.save()
    for doc in db:
        print(doc)        
    return str(resp)

@atexit.register
def shutdown():
    if client:
        client.disconnect()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
