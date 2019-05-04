#!/usr/bin/env python3

from lxml import html
import requests
import pymongo
from pymongo import MongoClient
from dateutil.parser import parse
import hashlib

# BBC Sport Football results scraper v0.3

# dateslug "/2019-04"
baseurl = "https://www.bbc.co.uk/sport/football/premier-league/scores-fixtures/"

mongoClient = None


def getDatabase():

    global mongoClient

    if mongoClient == None:
        mongoClient = MongoClient(username="root", password="example")
    return mongoClient.football


def closeDatabase():
    mongoClient.close()


# scrapeMonthlyFixtures() returns a list of dictionary objects.
# Each dictionary contains details of one fixture
def scrapeMonthlyFixtures(dateslugyear=None, dateslugmonth=None):

    if dateslugyear == None or dateslugmonth == None:
        return None

    dateslug = str(dateslugyear) + "-" + "{:02d}".format(dateslugmonth)

    # Which season is it?
    # Season runs from month=8 to month=6 following the year
    if dateslugmonth >= 8:
        seasontag = dateslugyear
    else:
        seasontag = dateslugyear - 1

    url = baseurl + dateslug
    page = requests.get(url)
    tree = html.fromstring(page.content)

    xpathFixtures = '//article[@class="sp-c-fixture"]/descendant::span/text()'
    xpathDates = '//h3[@class="gel-minion sp-c-match-list-heading"]'

    fixtures = tree.xpath(xpathFixtures + ' | ' + xpathDates)

    data = []
    index = 0
    matchDate = ""

    while index <= len(fixtures) - 1:

        if isinstance(fixtures[index], html.HtmlElement):  # It's a date
            matchDate = fixtures[index].text_content() + \
                " " + str(dateslugyear)
            index += 1
        else:  # It's a fixture

            matchdetails = {}

            # {
            #   ".id": SHA1 hash of hometeam+awayteam+season
            #   "date": "Saturday 11th August 2018",
            #   "season": 2018,
            #   "attendance": 52000,
            #
            #   "home": {
            #       "team": "Liverpool",
            #       "score": 4,
            #       "players": [{"player_name": "Sadio Mane"}]
            #   },
            #   "away": {
            #       "team": "West Ham",
            #       "score": 0,
            #       "players": [{"player_name": "Mark Noble"}]
            #   }
            # }

            idhash = fixtures[index] + fixtures[index+2] + str(seasontag)

            matchdetails["_id"] = hashlib.sha1(idhash.encode()).hexdigest()
            matchdetails["date"] = parse(matchDate)
            matchdetails["season"] = int(seasontag)
            matchdetails["attendance"] = None
            matchdetails["home"] = {
                "team": fixtures[index],
                "score": int(fixtures[index+1]),
                "players": [{}]
            }
            matchdetails["away"] = {
                "team": fixtures[index+2],
                "score": int(fixtures[index+3]),
                "players": [{}]
            }

            # Store match in data[]
            data.append(matchdetails)

            index += 4

    return data

# Get fixtures for 2018/19 Season - from 2018-08 to 2019-04 - i.e 9 months


def scrapeFixtures(currentyear=2018, currentmonth=8, numberofmonths=9):

    # Sore results in list of match dictionaries
    results = []

    for _ in range(numberofmonths):

        results.extend(scrapeMonthlyFixtures(currentyear, currentmonth))

        if currentmonth >= 12:
            currentmonth = 1
            currentyear += 1
        else:
            currentmonth += 1

    # Store data in MongoDB
    db = getDatabase()
    # specify collection
    collection = db.results

    # save results to database
    try:
        collection.insert_many(results, ordered=False)
    except (pymongo.errors.BulkWriteError, pymongo.errors.ServerSelectionTimeoutError,
            pymongo.errors.OperationFailure) as e:
        print(e)
    except:
        print("Unhandled Error")
    else:
        print("Results saved")

    closeDatabase()


def displayFixtures(season=2018, club=None):
    db = getDatabase()

    query = {}
    query["season"] = season

    if club:
        query["$or"] = [{"home.team": club}, {"away.team": club}]

    fixtures = db.results.find(query).sort([("date", 1), ("home.team", 1)])

    for fixture in fixtures:
        home = fixture["home"]
        away = fixture["away"]
        print(home["team"] + " " + str(home["score"]) +
              "-" + str(away["score"]) + " " + away["team"])

    closeDatabase()
