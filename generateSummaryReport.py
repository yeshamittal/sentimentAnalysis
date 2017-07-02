import requests
import json
import MySQLdb

def readPropertiesFile():
	global MYSQL_DB_HOSTANE, USERNAME, PASSWORD, DATABASE
	dictionary = {}
	with open("properties") as file:
		for line in file:
			splitLine = line.split("=")
			dictionary[splitLine[0]] = splitLine[1].strip('\n').strip(' ')
	MYSQL_DB_HOSTANE = dictionary["MYSQL_DB_HOSTANE"]
	USERNAME = dictionary["USERNAME"]
	PASSWORD = dictionary["PASSWORD"]
	DATABASE = dictionary["DATABASE"]

def writeReviewSummary():
	f = open("SummaryReport", 'write')
	reviewGetQuery = "SELECT * FROM `reviews`"
	conn = MySQLdb.connect(MYSQL_DB_HOSTANE, USERNAME, PASSWORD, DATABASE)
	request = conn.cursor()
	request.execute(reviewGetQuery)
	totalProcessed = "Total reviews processed are: " + str(request.rowcount) + "\n" + "Their summary is as follows: \n"
	header = "Review Id \t Review timestamp \t 	Sentiment \t Review Process Timestamp\n"
	f.write(str(totalProcessed) + header)
	for row in request:
		reviewId = row[1]
		reviewSentiment = row[2]
		reviewTimestamp = row[3]
		timestamp = row[4]
		if(reviewSentiment==1):
			sentiment = "POSITIVE"
		else:
			sentiment = "NEGATIVE"
		body = (str(reviewId) + "\t" + str(reviewTimestamp) + "\t" + str(sentiment) + "\t" + str(timestamp) + "\n")
		f.write(body)

readPropertiesFile()
writeReviewSummary()
