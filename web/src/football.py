#!/usr/bin/env python3

from lxml import html
import requests
import pymongo
from pymongo import MongoClient
from dateutil.parser import parse
import hashlib
import datetime

# BBC Sport Football results scraper v0.3

# dateslug "/2019-04"
baseurl = "https://www.bbc.co.uk/sport/football/premier-league/scores-fixtures/"

mongoClient = None


def getDatabase():

    global mongoClient

    if mongoClient == None:
        mongoClient = MongoClient("localhost", username="root", password="example")
    return mongoClient.football


def closeDatabase():
    
    if mongoClient != None:
        mongoClient.close()     


def whichSeason(month, year, fulldate=None):

    # Which season is it?
    # Season runs from month=8 to month=6 following the year
    
    season = 0

    if fulldate != None:
        month = fulldate.month
        year = fulldate.year

    if month >= 8:
        season = year
    else:
        season = year - 1

    return season


# scrapeMonthlyFixtures() returns a list of dictionary objects.
# Each dictionary contains details of one fixture
def scrapeMonthlyFixtures(dateslugyear=None, dateslugmonth=None):

    if dateslugyear == None or dateslugmonth == None:
        return None

    dateslug = str(dateslugyear) + "-" + "{:02d}".format(dateslugmonth)

    seasontag = whichSeason(dateslugmonth, dateslugyear)

    url = baseurl + dateslug + "?filter=results"
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

# Get fixtures for 2018/19 Season - from 2018-08 to 2019-05 - i.e 10 months
def scrapeFixtures(currentyear=2018, currentmonth=8, numberofmonths=10):

    # Sore results in list of match dictionaries
    results = []

    for _ in range(numberofmonths):

        results.extend(scrapeMonthlyFixtures(currentyear, currentmonth))

        #print ("Getting: " + str(currentmonth) + " " + str(currentyear))

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


def getFixtures(season=2018, club=None, print_to_stdout=False):
    db = getDatabase()

    query = {}
    query["season"] = season

    if club:
        query["$or"] = [{"home.team": club}, {"away.team": club}]

    fixtures = db.results.find(query).sort([("date", 1), ("home.team", 1)])

    if print_to_stdout == True:
        for fixture in fixtures:
            home = fixture["home"]
            away = fixture["away"]
            print(home["team"] + " " + str(home["score"]) +
                "-" + str(away["score"]) + " " + away["team"])

    return list(fixtures)


def getTeamForm(team, scope=None, lastdate=None, games=5):

    query = {}

    if lastdate != None:
        parsed_date = parse(str(lastdate))
        query["date"] = {"$lte":parsed_date}

    if scope == "home":
        query["home.team"] = team
    elif scope == "away":
        query["away.team"] = team
    else:
        query["$or"] = [{"home.team": team}, {"away.team": team}]

    db = getDatabase()
    
    fixtures = db.results.find(query).sort("date", -1).limit(games)

    form = []
    
    for fixture in fixtures:

        # Is it a home game?
        if fixture["home"]["team"] == team:
            if fixture["home"]["score"] > fixture["away"]["score"]:
                form.append("W")
            elif fixture["home"]["score"] < fixture["away"]["score"]:
                form.append("L")
            else:
                form.append("D")
        else:
            if fixture["home"]["score"] < fixture["away"]["score"]:
                form.append("W")
            elif fixture["home"]["score"] > fixture["away"]["score"]:
                form.append("L")
            else:
                form.append("D") 

    form.reverse()

    return form

def buildTable(season=2018, lastdate=None):

    # Analyse results for season & generate a league table
    # Table format

    # _id: hash of table date
    # date: date table goes up to i.e. date of last fixture
    # season: season id tag e.g. 2018
    # table {  - a dictionary containing 1 dictionary per team
    #   "Liverpool":
    #   {
    #       "home": {
    #               "played": 0
    #               "won": 0,
    #               "drawn": 0,
    #               "lost": 0,
    #               "for": 0,
    #               "against": 0,
    #               "gd": 0,
    #               "points": 0,
    #               "form": []
    #             },
    #       "away": {
    #               "played": 0        
    #               "won": 0,
    #               "drawn": 0,
    #               "lost": 0
    #               "for": 0,
    #               "against": 0,
    #               "gd": 0,
    #               "points": 0
    #               "form": []
    #             },
    #       "totals": {
    #               "played": 0
    #               "won": 0,
    #               "drawn": 0,
    #               "lost": 0
    #               "for": 0,
    #               "against": 0,
    #               "gd": 0,
    #               "points": 0
    #               "form": []
    #             }
    #   }
    # }

    # Get all the results
    db = getDatabase()

    query = {}
    query["season"] = season
    
    if lastdate != None:
        parsed_date = parse(str(lastdate))
        query["date"] = {"$lte":parsed_date}

    fixtures = db.results.find(query).sort([("date", 1), ("home.team", 1)])

    table = {}
    table["date"] = None
    table["season"] = season
    table["standings"] = {}

    t = {}
    lastFixtureDate = None
    fixture_count = 0

    for fixture in fixtures:

        if lastFixtureDate == None:
            lastFixtureDate = fixture["date"]
        else:
            if fixture["date"] > lastFixtureDate:
                lastFixtureDate = fixture["date"]

        home = fixture["home"]
        away = fixture["away"]

        # is team already in table? If not add it and set starting values
        for team in [home, away]:
            if team["team"] not in t:
                t[team["team"]] = {
                                    "home": {"played": 0,"won": 0,"drawn": 0,"lost": 0,"for": 0,"against": 0,"gd": 0,"points": 0},
                                    "away": {"played": 0,"won": 0,"drawn": 0,"lost": 0,"for": 0,"against": 0,"gd": 0,"points": 0},
                                    "totals": {"played": 0,"won": 0,"drawn": 0,"lost": 0,"for": 0,"against": 0,"gd": 0,"points": 0}
                                }

        # Add goals to table
        # home team
        t[home["team"]]["home"]["for"] += home["score"]
        t[home["team"]]["home"]["against"] += away["score"]
        t[home["team"]]["home"]["gd"] += (home["score"] - away["score"])
        # away team
        t[away["team"]]["away"]["for"] += away["score"]
        t[away["team"]]["away"]["against"] += home["score"]
        t[away["team"]]["away"]["gd"] += (away["score"] - home["score"])       

        # Who won?
        if home["score"] > away["score"]: # Home Win
            t[home["team"]]["home"]["won"] += 1
            t[home["team"]]["home"]["points"] += 3
            t[away["team"]]["away"]["lost"] += 1

        elif away["score"] > home["score"]: # Away Win
            t[away["team"]]["away"]["won"] += 1
            t[away["team"]]["away"]["points"] += 3
            t[home["team"]]["home"]["lost"] += 1
        else: # draw
            t[home["team"]]["home"]["drawn"] += 1
            t[home["team"]]["home"]["points"] += 1
            t[away["team"]]["away"]["drawn"] += 1
            t[away["team"]]["away"]["points"] += 1
        
        # Add the game
        t[home["team"]]["home"]["played"] += 1
        t[away["team"]]["away"]["played"] += 1

        fixture_count += 1

    if fixture_count == 0: # No fixtures processed so no table either
        return None

    table["standings"] = t
    table["date"] = parse(str(lastFixtureDate))
    table["_id"] = hashlib.sha1(str(table["date"]).encode()).hexdigest()

    # Calculate Totals
    for team in table["standings"]:
        t = table["standings"][team]
        t["totals"]["played"] = t["home"]["played"] + t["away"]["played"]
        t["totals"]["won"] = t["home"]["won"] + t["away"]["won"]
        t["totals"]["lost"] = t["home"]["lost"] + t["away"]["lost"]
        t["totals"]["drawn"] = t["home"]["drawn"] + t["away"]["drawn"]
        t["totals"]["for"] = t["home"]["for"] + t["away"]["for"]
        t["totals"]["against"] = t["home"]["against"] + t["away"]["against"]
        t["totals"]["gd"] = t["home"]["gd"] + t["away"]["gd"]
        t["totals"]["points"] = t["home"]["points"] + t["away"]["points"]
        # Form
        t["home"]["form"] = getTeamForm(team,"home",table["date"])
        t["away"]["form"] = getTeamForm(team,"away",table["date"])
        t["totals"]["form"] = getTeamForm(team,None,table["date"])

    # Save table to DB
    # specify collection
    collection = db.tables

    # save results to database
    try:
        collection.insert_one(table)
    except (pymongo.errors.BulkWriteError, pymongo.errors.ServerSelectionTimeoutError,
            pymongo.errors.OperationFailure) as e:
        print(e)
    except:
        print("Unhandled Error")
    else:
        print("Table saved")

    return table

# scope must be home or away
def getTable(season=2018, scope=None, lastdate=datetime.datetime.now()):

    lastdate = str(lastdate)

    # scope will order the final table by home, away or combined totals
    if (scope != "home") and (scope != "away"):
        scope = "totals"

    # Get table
    db = getDatabase()

    query = {}
    query["season"] = season

    # add date filter to query
    query["date"] = {"$lte":parse(lastdate)}

    try:
        # use .next() to get document rather than cursor
        data = db.tables.find(query).sort("date", -1).limit(1).next() 
    except StopIteration:
        print ("No tables found - Generate one")
        data = buildTable(season, parse(lastdate))
        if data == None:
            print ("No tables could be generated")
            return None

    # If there are any games between table date and lastdate then
    # generate new table for date of last game

    query = {}
    query["season"] = season
    query["date"] = {"$gt":data["date"],"$lte":parse(lastdate)}

    numberofgames = db.results.count_documents(query)
    
    if numberofgames > 0:
        
        # Get date of the latest game
        games = db.results.find(query).sort("date", -1).limit(1)

        # Generate a new table            
        data = buildTable(season, parse(str(games[0]["date"])))

        if data == None:
            print ("No tables could be generated")
            return None

    standings = data["standings"]

    # Sort by Name, Goals For, GD and then Points
    # return sorted list - table  [ (team, {data}) ]
    table = sorted(standings.items(),key=lambda x: x[0])
    table = sorted(table,key=lambda x: x[1][scope]["for"], reverse=True)
    table = sorted(table,key=lambda x: x[1][scope]["gd"], reverse=True)
    table = sorted(table,key=lambda x: x[1][scope]["points"], reverse=True)

    #for x in table:
    #    print (x[0] + " " + str(x[1]["totals"]["gd"]) + " " + str(x[1]["totals"]["points"]) + \
    #            " " + str(x[1]["totals"]["form"]))
    
    return table

#scrapeFixtures(2018)
getTable(2018)

closeDatabase()
