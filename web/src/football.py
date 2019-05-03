#!/usr/bin/env python

from lxml import html
import requests
import json
import pymongo
from pymongo import MongoClient
from dateutil.parser import parse

# BBC Sport Football results scraper v0.1

baseurl = "https://www.bbc.co.uk/sport/football/premier-league/scores-fixtures/" # dateslug "/2019-04"

def printJSON(data, indentvalue=2):
    print (json.dumps(json.loads(data), indent=indentvalue, sort_keys=True))

# getMonthlyFixtures() returns a list of dictionary objects. 
# Each dictionary contains details of one fixture
def scrapeMonthlyFixtures(dateslugyear=None, dateslugmonth=None):
    
    if dateslugyear == None or dateslugmonth == None:
        return None

    dateslug = str(dateslugyear) + "-" + "{:02d}".format(dateslugmonth)

    url = baseurl + dateslug
    page = requests.get(url)
    tree = html.fromstring(page.content)

    xpathFixtures = '//article[@class="sp-c-fixture"]/descendant::span/text()'
    xpathDates = '//h3[@class="gel-minion sp-c-match-list-heading"]'

    fixtures = tree.xpath(xpathFixtures + ' | ' + xpathDates)

    #{
    #   "date": "Saturday 11th August 2018",
    #   "hometeam": "Liverpool",
    #   "awayteam": "West Ham United",
    #   "homescore": "4",
    #   "awayscore": "0"
    #}

    data = []
    index = 0
    matchDate = ""
    matchcounter = 0

    while index <= len(fixtures) - 1:

        if isinstance(fixtures[index], html.HtmlElement): #It's a date
            matchDate = fixtures[index].text_content() + " " + str(dateslugyear)
            index += 1
        else: # It's a fixture
            # Store match in data[]
            matchdetails = {}
            matchdetails["date"] = parse(matchDate)
            matchdetails["hometeam"] = fixtures[index]
            matchdetails["homescore"] = int(fixtures[index+1])
            matchdetails["awayteam"] = fixtures[index+2]
            matchdetails["awayscore"] = int(fixtures[index+3])

            data.append(matchdetails)

            matchcounter += 1
            index += 4
    
    return data

# Get fixtures for 2018/19 Season - from 2018-08 to 2019-04 - i.e 9 months
def getFixtures(currentyear,currentmonth=8,numberofmonths=9):
    
    # Sore results in list of match dictionaries
    results = []

    for m in range(numberofmonths):

        results.extend(scrapeMonthlyFixtures(currentyear, currentmonth))

        if currentmonth >= 12:
            currentmonth = 1
            currentyear += 1
        else:
            currentmonth += 1

    # Store data in MongoDB
    # connect to mongo
    client = MongoClient(username="root", password="example")
    # specify database
    db = client.football_database
    # specify collection
    collection = db.results_collection

    # save results to database
    try:
        resultIDs = collection.insert_many(results)
    except (pymongo.errors.BulkWriteError, pymongo.errors.ServerSelectionTimeoutError, 
            pymongo.errors.OperationFailure) as e:
        print (e)
    except:
        print ("Unhandled Error")
    else:
        print ("Results saved")

    client.close()

