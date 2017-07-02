import requests
import json
import sendgrid
import os
from sendgrid.helpers.mail import *
import MySQLdb
import datetime
import time
from apscheduler.schedulers.blocking import BlockingScheduler
from time import gmtime, strftime

def readPropertiesFile():
	global EMAIL_THRESHOLD, MYSQL_DB_HOSTANE, USERNAME, PASSWORD, DATABASE, RESTAURANT_ID, USER_KEY, EMAIL_TO, EMAIL_FROM, HOURS, IS_PERIODIC
	dictionary = {}
	with open("properties") as file:
		for line in file:
			splitLine = line.split("=")
			dictionary[splitLine[0]] = splitLine[1].strip('\n').strip(' ')
	EMAIL_THRESHOLD = dictionary["EMAIL_THRESHOLD"]
	MYSQL_DB_HOSTANE = dictionary["MYSQL_DB_HOSTANE"]
	USERNAME = dictionary["USERNAME"]
	PASSWORD = dictionary["PASSWORD"]
	DATABASE = dictionary["DATABASE"]
	RESTAURANT_ID = dictionary["RESTAURANT_ID"]
	USER_KEY = dictionary["USER_KEY"]
	EMAIL_TO = dictionary["EMAIL_TO"]
	EMAIL_FROM = dictionary["EMAIL_FROM"]
	HOURS = dictionary["HOURS"]
	IS_PERIODIC = dictionary["IS_PERIODIC"]

def getQueryResults1(url):
	headers = {"content-type":"application/json","user-key": USER_KEY}
	request = requests.get(url, headers=headers)
	response = request.json()
	return response

def getQueryResults2(url, payload):
	headers = {"content-type":"application/json","user-key": USER_KEY}
	request = requests.get(url, params=payload, headers=headers)
	#(request.url)
	response = request.json()
	return response

def checkArrayAndGetId(array, keyword, id):
	for jsonObj in array:
		obj = jsonObj[keyword]
		jsonId = compareAndReturn(obj, id) # Working only for Casual dining type of restaurants
		if(jsonId==id):
			return id
	return -1

def compareAndReturn(obj, id):
	if(obj['id']==id): 
		return id
	else:
		return -1

def getCityId():
	#Checking for city Delhi
	urlCity = "https://developers.zomato.com/api/v2.1/cities?q=delhi"
	cityResponse = getQueryResults1(urlCity)
	cities = cityResponse['location_suggestions']
	for city in cities:
		cityId = compareAndReturn(city, 1) #As working only for Delhi - India, whose cityId=1
		if(cityId==1):
			break
	return cityId

def getEstablishmentId(cityId, id):
	establishmentParams = {'city_id':cityId}
	urlEstablishments = "https://developers.zomato.com/api/v2.1/establishments"
	establishmentsResponse = getQueryResults2(urlEstablishments, establishmentParams)
	# I have chosen the establishment ID 16 which is Casual Dining
	establishmentId = checkArrayAndGetId(establishmentsResponse['establishments'], 'establishment', id) 
	return establishmentId

def getRestaurantId(establishmentId, id):
	restaurantsParams = {'entity_id':'1','entity_type':'city','establishment_type':establishmentId}
	urlRestaurants = "https://developers.zomato.com/api/v2.1/search"
	restaurantsResponse = getQueryResults2(urlRestaurants, restaurantsParams)
	# I am choosing a particular restaurant whose is mentioned here
	restaurantId = checkArrayAndGetId(restaurantsResponse['restaurants'], 'restaurant', id)
	return restaurantId

def readFromFile(fname):
	with open(fname) as f:
	    content = f.readlines()
	content = [x.strip() for x in content] 
	return content

def writeToFile(fname, list):
	file = open(fname, 'w')
	for item in list:
  		print>>file, item

def removeStopWords(reviewText):
	stopWords = readFromFile("stopWords")
	reviewList = reviewText.split()
	intersection = list(set(stopWords)&set(reviewList))
	for word in intersection:
		reviewList.remove(word)
	return reviewList

def getIntersection(reviewList, fname):
	wordsLlist = readFromFile(fname)
	intersection = list(set(wordsLlist)&set(reviewList))
	for word in intersection:
		reviewList.remove(word)
	return reviewList

def getScore(reviewList, fname):
	wordsLlist = readFromFile(fname)
	intersection = list(set(wordsLlist)&set(reviewList))
	return len(intersection)

def getReviews(restaurantId):
	reviewsParams = {'res_id':str(restaurantId)}
	urlReviews = "https://developers.zomato.com/api/v2.1/reviews"
	reviewsResponse = getQueryResults2(urlReviews, reviewsParams)
	reviews = reviewsResponse['user_reviews']
	reviewList = []
	for review in reviews:
		obj = review['review']
		##rating = obj['rating']
		#reviewText = obj['review_text']
		#reviewId = obj['id']
		#reviewTimestamp = obj['timestamp']
		#print ("Review Data: " + str(rating) +  " " + str(reviewId) + " " + str(reviewTimestamp))
		reviewDict = {}
		reviewDict["id"]=obj['id']
		reviewDict["rating"]=obj['rating']
		reviewDict["text"]=obj['review_text']
		reviewDict["timestamp"]=obj['timestamp']
		reviewList.append(reviewDict)
	return reviewList

def sendMail(review):
	sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))
	from_email = Email(EMAIL_FROM)
	to_email = Email(EMAIL_TO)
	subject = "Negative review notification"
	body = ("Hello. You are getting this email because you just got a negative review. The review is as follows: \n" 
	+ "\n" + str(review['text']) + "\n" + "The rating given is: " + str(review['rating']))
	content = Content("text/plain", body)
	mail = Mail(from_email, subject, to_email, content)
	response = sg.client.mail.send.post(request_body=mail.get())
	print(response.status_code)

def getDateTime(timestamp):
	sec = timestamp / 1000.0
	dateTime = datetime.datetime.fromtimestamp(sec/1000.0).strftime('%Y-%m-%d %H:%M:%S')
	return dateTime

def addToDb(review, totalNegativeReview):
	conn = MySQLdb.connect(MYSQL_DB_HOSTANE, USERNAME, PASSWORD, DATABASE)
	request = conn.cursor()
	sentimentIdQuery = "SELECT `id` FROM `review_sentiment` WHERE `sentiment`="
	if(totalNegativeReview<int(EMAIL_THRESHOLD)):
		sentimentIdQuery += "'POSITIVE'"
		sentiment = 1
	else:
		sentimentIdQuery += "'NEGATIVE'"
		sentiment = 2
	request.execute(sentimentIdQuery)
	for row in request:
		sentimentId = row[0]
	dateTime = getDateTime(review['timestamp'])
	reviewInsertQuery = "INSERT INTO `reviews`(`review_id`, `review_sentiment`, `review_timestamp`) VALUES ('" + str(review['id']) + "'," + str(sentimentId) + ",'" + str(dateTime) + "'" + ")"
	try:
		request.execute(reviewInsertQuery)
		conn.commit()
	except (MySQLdb.Error, MySQLdb.Warning) as e:
		print e
		conn.rollback()
	finally:
		conn.close()
	if(sentiment==2):
		sendMail(review)

def addSentiment(reviewList):
	conn = MySQLdb.connect(MYSQL_DB_HOSTANE, USERNAME, PASSWORD,DATABASE)
	request = conn.cursor()
	global reviewCount
	reviewCount = 0
	for review in reviewList:
		reiewIdQuery = "SELECT `id` FROM `reviews` WHERE `review_id`=" + "'" + str(review['id']) + "'"
		request.execute(reiewIdQuery)
		rowCount = request.rowcount
		if(rowCount==0): # If the review is not already present/processed in database
			reviewCount = reviewCount + 1
			reviewText = review['text'].split()
			if(len(reviewText)>0):
				updatedReview = getIntersection(reviewText, "stopWords")
			negativeRating = 50-(review['rating']*10)
			if(len(updatedReview)>0): #if there is no review text, we cannot do sentiment analysis and 
									  #thus will add a sentiment based on rating only
				positiveReview = getScore(updatedReview, "positiveWords")
				negativeReview = getScore(updatedReview, "negativeWords")
				negativeScore = 0
				if(positiveReview > 0 or negativeReview > 0):
					negativeScore = (negativeReview/float(positiveReview + negativeReview))*(50)
				if(negativeScore!=0):
					totalNegativeReview = negativeScore + negativeRating
				else:
					totalNegativeReview = negativeRating*2
			else:
				totalNegativeReview = negativeRating*2
			addToDb(review, totalNegativeReview)
	conn.close()

def sentimentAnalysis():
	reviewList = getReviews(RESTAURANT_ID)
	addSentiment(reviewList)

# Start the scheduler
def startScheduler():
	sched = BlockingScheduler()
	sched.add_job(sentimentAnalysis,  'interval', hours=int(HOURS))
	sched.start()
#Checking for city Delhi
#cityId = getCityId()
#print ("cityId: " + str(cityId))

#establishmentId = getEstablishmentId(str(cityId), 16)
#print ("establishmentId: " + str(establishmentId))

#restaurantId = getRestaurantId(str(establishmentId), '18273624')
#print ("restaurantId: " + str(restaurantId))

#getReviews(str(restaurantId))
readPropertiesFile()

if(IS_PERIODIC=='1'):
	startScheduler()
else:
	sentimentAnalysis()







