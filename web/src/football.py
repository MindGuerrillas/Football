#!/usr/bin/env python

from lxml import html
import requests
import json
import pymongo
from pymongo import MongoClient
from dateutil.parser import parse
import hashlib

# BBC Sport Football results scraper v0.2

# dateslug "/2019-04"
baseurl = "https://www.bbc.co.uk/sport/football/premier-league/scores-fixtures/"

mongoClient = None


def getDatabase():

    global mongoClient

    if mongoClient == None:
        mongoClient = MongoClient(username="root", password="example")
    return mongoClient.football_database


def closeDatabase():
    mongoClient.close()


def printJSON(data, indentvalue=2):
    print (json.dumps(json.loads(data), indent=indentvalue, sort_keys=True))


# getMonthlyFixtures() returns a list of dictionary objects.
# Each dictionary contains details of one fixture
def scrapeMonthlyFixtures(dateslugyear=None, dateslugmonth=None, seasontag=""):

    if dateslugyear == None or dateslugmonth == None:
        return None

    dateslug = str(dateslugyear) + "-" + "{:02d}".format(dateslugmonth)

    url = baseurl + dateslug
    page = requests.get(url)
    tree = html.fromstring(page.content)

    xpathFixtures = '//article[@class="sp-c-fixture"]/descendant::span/text()'
    xpathDates = '//h3[@class="gel-minion sp-c-match-list-heading"]'

    fixtures = tree.xpath(xpathFixtures + ' | ' + xpathDates)

    # {
    #   ".id": SHA1 hash of hometeam+awayteam+season
    #   "date": "Saturday 11th August 2018",
    #   "hometeam": "Liverpool",
    #   "awayteam": "West Ham United",
    #   "homescore": "4",
    #   "awayscore": "0"
    #   "season": 2018
    # }

    data = []
    index = 0
    matchDate = ""
    matchcounter = 0

    while index <= len(fixtures) - 1:

        if isinstance(fixtures[index], html.HtmlElement):  # It's a date
            matchDate = fixtures[index].text_content() + \
                " " + str(dateslugyear)
            index += 1
        else:  # It's a fixture
            # Store match in data[]
            matchdetails = {}

            idhash = fixtures[index] + fixtures[index+2] + str(seasontag)

            matchdetails["_id"] = hashlib.sha1(idhash.encode()).hexdigest()
            matchdetails["date"] = parse(matchDate)
            matchdetails["hometeam"] = fixtures[index]
            matchdetails["homescore"] = int(fixtures[index+1])
            matchdetails["awayteam"] = fixtures[index+2]
            matchdetails["awayscore"] = int(fixtures[index+3])
            matchdetails["season"] = int(seasontag)

            data.append(matchdetails)

            matchcounter += 1
            index += 4

    return data

# Get fixtures for 2018/19 Season - from 2018-08 to 2019-04 - i.e 9 months


def getFixtures(currentyear=2018, currentmonth=8, numberofmonths=9):

    # Sore results in list of match dictionaries
    results = []
    seasontag = currentyear

    for _ in range(numberofmonths):

        results.extend(scrapeMonthlyFixtures(
            currentyear, currentmonth, seasontag))

        if currentmonth >= 12:
            currentmonth = 1
            currentyear += 1
        else:
            currentmonth += 1

    # Store data in MongoDB
    db = getDatabase()
    # specify collection
    collection = db.results_collection

    # save results to database
    try:
        collection.insert_many(results)
    except (pymongo.errors.BulkWriteError, pymongo.errors.ServerSelectionTimeoutError,
            pymongo.errors.OperationFailure) as e:
        print (e)
    except:
        print ("Unhandled Error")
    else:
        print ("Results saved")

    closeDatabase()


def displayFixtures(season=2018, club=None):
    db = getDatabase()

    query = {}
    query["season"] = season

    if club:
        query["$or"] = [{"hometeam": club}, {"awayteam": club}]

    fixtures = db.results_collection.find(query).sort([("date", 1), ("hometeam", 1)])

    for fixture in fixtures:
        print fixture["hometeam"] + " " + str(fixture["homescore"]) + \
            "-" + str(fixture["awayscore"]) + " " + fixture["awayteam"]


displayFixtures(2018, "Liverpool")
