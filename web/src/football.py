#!/usr/bin/env python3

from lxml import html
import requests
import pymongo
from pymongo import MongoClient
from dateutil.parser import parse
import hashlib
import datetime
import constant as const
import unicodedata
import utilities as utils

# BBC Sport Football results scraper v0.3

mongoClient = None

def getDatabase():

    global mongoClient

    if mongoClient == None:
        mongoClient = MongoClient(
            const.MONGODB_SERVER,
            username=const.MONGODB_USER,
            password=const.MONGODB_PASSWORD
        )
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

    if month >= const.SEASON_START_MONTH:
        season = year
    else:
        season = year - 1

    return season

def currentSeason():
    return whichSeason(0,0,datetime.datetime.now())

def strip_accents(text):

    try:
        text = unicode(text, 'utf-8')
    except NameError: # unicode is a default on python 3 
        pass

    text = unicodedata.normalize('NFD', text)\
           .encode('ascii', 'ignore')\
           .decode("utf-8")

    return str(text)

def __teamnameSlug(team):
    # return lower case team name
    # replace spaces with - dash

    return strip_accents(team).lower().replace(" ", "-")

def __teamnameSlugReverse(teamslug):
    return teamslug.capitalize().replace("-", " ")


# __scrapeMonthlyFixtures() returns a list of dictionary objects.
# Each dictionary contains details of one fixture
def __scrapeMonthlyFixtures(dateslugyear=None, dateslugmonth=None, league=const.PREMIER_LEAGUE):

    if dateslugyear == None or dateslugmonth == None:
        return None

    dateslug = str(dateslugyear) + "-" + "{:02d}".format(dateslugmonth)

    seasontag = whichSeason(dateslugmonth, dateslugyear)

    url = const.BASE_URL.replace("LEAGUETAG", league) + dateslug + "?filter=results"

    utils.debuggingPrint("Scraping " + url)
    
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
            #   ".id": SHA1 hash of hometeam+awayteam+season+date
            #   "date": "Saturday 11th August 2018",
            #   "season": 2018,
            #   "league": premier-league,
            #   "tag": "",
            #   "attendance": 52000,
            #
            #   "home": {
            #       "team": "Liverpool",
            #       "teamslug": "liverpool",
            #       "score": 4,
            #       "players": [{"player_name": "Sadio Mane"}]
            #   },
            #   "away": {
            #       "team": "West Ham",
            #       "teamslug": "west-ham-united",
            #       "score": 0,
            #       "players": [{"player_name": "Mark Noble"}]
            #   }
            # }

            idhash = fixtures[index] + fixtures[index+2] + str(seasontag) + str(parse(matchDate))

            matchdetails["_id"] = hashlib.sha1(idhash.encode()).hexdigest()
            matchdetails["date"] = parse(matchDate)
            matchdetails["season"] = int(seasontag)
            matchdetails["attendance"] = None
            matchdetails["league"] = league
            matchdetails["tag"] = ""

            matchdetails["home"] = {
                "team": fixtures[index],
                "teamslug": __teamnameSlug(fixtures[index]),
                "score": int(fixtures[index+1]),
                "players": [{}]
            }
            matchdetails["away"] = {
                "team": fixtures[index+2],
                "teamslug": __teamnameSlug(fixtures[index+2]),
                "score": int(fixtures[index+3]),
                "players": [{}]
            }

            # Store match in data[]
            data.append(matchdetails)

            index += 4

    return data

# Get fixtures for named season - August to May - i.e 10 months
def scrapeFixtures(currentyear=currentSeason(), league=const.PREMIER_LEAGUE, 
                    currentmonth=const.SEASON_START_MONTH, numberofmonths=const.SEASON_LENGTH
                ):

    # Store results in list of match dictionaries
    results = []

    for _ in range(numberofmonths):

        results.extend(__scrapeMonthlyFixtures(currentyear, currentmonth, league))

        utils.debuggingPrint("Getting: " + str(currentmonth) + " " + str(currentyear))

        if currentmonth >= 12:
            currentmonth = 1
            currentyear += 1
        else:
            currentmonth += 1

    # Store data in MongoDB
    db = getDatabase()
    # specify collection
    collection = db.results

    utils.debuggingPrint("Saving " + str(len(results)) + " results" )

    # save results to database
    try:
        collection.insert_many(results, ordered=False)
    except (pymongo.errors.BulkWriteError, pymongo.errors.ServerSelectionTimeoutError,
            pymongo.errors.OperationFailure) as e:
        print (e)
        #print(e.details["writeErrors"])
    except:
        print("Unhandled Error")
    else:
        print("Results saved")

    closeDatabase()


def getFixtures(league=const.PREMIER_LEAGUE, season=currentSeason(), club=None, month=None):
    
    # Sanity check
    if season == None:
        season = currentSeason()
    if league == None:
        league = const.PREMIER_LEAGUE

    db = getDatabase()
 
    query = {}
    query["season"] = season
    query["league"] = league

    if month:
        query["$expr"] = { "$eq": [{ "$month": "$date" }, month] }

    if club:
        club = __teamnameSlug(club)
        query["$or"] = [{"home.teamslug": club}, {"away.teamslug": club}]

    fixtures = db.results.find(query).sort([("date", 1), ("home.team", 1)])

    closeDatabase()

    return list(fixtures)


def getTeamForm(team, scope=None, lastdate=None, games=5):

    query = {}

    team = __teamnameSlug(team)

    if lastdate != None:
        parsed_date = parse(str(lastdate))
        query["date"] = {"$lte":parsed_date}

    if scope == "home":
        query["home.teamslug"] = team
    elif scope == "away":
        query["away.teamslug"] = team
    else:
        query["$or"] = [{"home.teamslug": team}, {"away.teamslug": team}]

    db = getDatabase()
    
    fixtures = db.results.find(query).sort("date", -1).limit(games)

    form = []
    
    for fixture in fixtures:

        # Is it a home game?
        if fixture["home"]["teamslug"] == team:
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

def __buildTable(season=currentSeason(), lastdate=None, league=const.PREMIER_LEAGUE, tableType=const.TABLE_FULL):

    # Analyse results for season & generate a league table
    # Table format

    # _id: hash of league + type + table date
    # date: date table goes up to i.e. date of last fixture
    # season: season id tag e.g. 2018
    # league: premier-league
    # type: "full" 
    # standings {  - a dictionary containing 1 dictionary per team
    #   "liverpool":     # This is the __teamnameSlug e.g. west-ham-united
    #   {
    #       "teamname": Liverpool,
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
    query["league"] = league

    if lastdate != None:
        parsed_date = parse(str(lastdate))
        query["date"] = {"$lte":parsed_date}

    if tableType != const.TABLE_FULL:

        teamsFilter = []

        if tableType == const.TABLE_TOPTEAMS:
            teamsFilter = const.TOPTEAMS[league]

        query["home.teamslug"] = { "$in": teamsFilter}
        query["away.teamslug"] = { "$in": teamsFilter}


    fixtures = db.results.find(query).sort([("date", 1), ("home.team", 1)])

    table = {}
    table["date"] = None
    table["season"] = season
    table["league"] = league
    table["type"] = tableType    
    table["standings"] = {}

    standings = {}
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
            if team["teamslug"] not in standings:
                standings[team["teamslug"]] = {
                                    "teamname": team["team"],
                                    "home": {"played": 0,"won": 0,"drawn": 0,"lost": 0,"for": 0,"against": 0,"gd": 0,"points": 0},
                                    "away": {"played": 0,"won": 0,"drawn": 0,"lost": 0,"for": 0,"against": 0,"gd": 0,"points": 0},
                                    "totals": {"played": 0,"won": 0,"drawn": 0,"lost": 0,"for": 0,"against": 0,"gd": 0,"points": 0}
                                }
        
        # Add goals to table
        # home team
        standings[home["teamslug"]]["home"]["for"] += home["score"]
        standings[home["teamslug"]]["home"]["against"] += away["score"]
        standings[home["teamslug"]]["home"]["gd"] += (home["score"] - away["score"])
        # away team
        standings[away["teamslug"]]["away"]["for"] += away["score"]
        standings[away["teamslug"]]["away"]["against"] += home["score"]
        standings[away["teamslug"]]["away"]["gd"] += (away["score"] - home["score"])       

        # Who won?
        if home["score"] > away["score"]: # Home Win
            standings[home["teamslug"]]["home"]["won"] += 1
            standings[home["teamslug"]]["home"]["points"] += 3
            standings[away["teamslug"]]["away"]["lost"] += 1

        elif away["score"] > home["score"]: # Away Win
            standings[away["teamslug"]]["away"]["won"] += 1
            standings[away["teamslug"]]["away"]["points"] += 3
            standings[home["teamslug"]]["home"]["lost"] += 1
        else: # draw
            standings[home["teamslug"]]["home"]["drawn"] += 1
            standings[home["teamslug"]]["home"]["points"] += 1
            standings[away["teamslug"]]["away"]["drawn"] += 1
            standings[away["teamslug"]]["away"]["points"] += 1
        
        # Add the game
        standings[home["teamslug"]]["home"]["played"] += 1
        standings[away["teamslug"]]["away"]["played"] += 1

        fixture_count += 1

    if fixture_count == 0: # No fixtures processed so no table either
        utils.debuggingPrint("No games found - No table produced")
        return None

    table["standings"] = standings
    table["date"] = parse(str(lastFixtureDate))
    
    # generate _id hash
    idhash = league + tableType + str(table["date"])
    table["_id"] = hashlib.sha1(idhash.encode()).hexdigest()

    # Calculate Totals
    for team in table["standings"]:
        t = table["standings"][team]

        # Add home & away numbers
        for item in ["played","won","lost","drawn","for","against","gd","points"]:
            t["totals"][item] = t["home"][item] + t["away"][item]
            
        # Form
        for scope in ["home","away","totals"]:
            t[scope]["form"] = getTeamForm(team,scope,table["date"])
        

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

    closeDatabase()

    return table

# scope must be totals, home or away
def getTable(league=const.PREMIER_LEAGUE, season=currentSeason(), 
            scope=None, tableType=const.TABLE_FULL, 
            lastdate=datetime.datetime.now()
            ):

    # Sanity check
    if season == None:
        season = currentSeason()
    if lastdate == None:
        lastdate = datetime.datetime.now()
    if scope not in ["totals","home","away"]:
        scope = "totals"
    if league == None:
        league = const.PREMIER_LEAGUE
    if tableType == None:
        tableType = const.TABLE_FULL

    lastdate = parse(str(lastdate))

    # scope will order the final table by home, away or combined totals
    if (scope != "home") and (scope != "away"):
        scope = "totals"

    # Get table
    db = getDatabase()

    query = {}
    query["season"] = season
    query["league"] = league
    query["type"] = tableType

    # add date filter to query
    query["date"] = {"$lte":lastdate}

    try:
        # use .next() to get document rather than cursor
        # pull the latest table from the database
        data = db.tables.find(query).sort("date", -1).limit(1).next() 
    except StopIteration:
        utils.debuggingPrint("No tables found - Generate one")
        data = __buildTable(season, lastdate, league, tableType)
        if data == None:
            utils.debuggingPrint("No tables could be generated")
            return None

    # If there are any games between table date and lastdate then
    # generate new table for date of last game

    resultsquery = {}
    resultsquery["season"] = season
    resultsquery["league"] = league
    resultsquery["date"] = {"$gt":data["date"],"$lte":lastdate}
    
    if tableType != const.TABLE_FULL:

        teamsFilter = []

        if tableType == const.TABLE_TOPTEAMS:
            teamsFilter = const.TOPTEAMS[league]

        resultsquery["home.teamslug"] = { "$in": teamsFilter}
        resultsquery["away.teamslug"] = { "$in": teamsFilter}

    numberofgames = db.results.count_documents(resultsquery)
    
    utils.debuggingPrint("Number of new games found:" + str(numberofgames) + " from " + str(resultsquery))

    if numberofgames > 0:
        
        # Get date of the latest game
        games = db.results.find(resultsquery).sort("date", -1).limit(1)

        # Generate a new table     
        print ("Building New table for Extra Games")       
        data = __buildTable(season, parse(str(games[0]["date"])), league, tableType)

        if data == None:
            utils.debuggingPrint("No tables could be generated")
            return None

    standings = data["standings"]

    # Sort by Name, Goals For, GD and then Points
    # return sorted list - table  [ (team, {data}) ]
    table = sorted(standings.items(),key=lambda x: x[0])
    table = sorted(table,key=lambda x: x[1][scope]["for"], reverse=True)
    table = sorted(table,key=lambda x: x[1][scope]["gd"], reverse=True)
    table = sorted(table,key=lambda x: x[1][scope]["points"], reverse=True)

    closeDatabase()

    return table

def printTable(table):
    if table == None:
        return ""
        
    for x in table:
        print (x[1]["teamname"] + " " + str(x[1]["totals"]["gd"]) + " " + str(x[1]["totals"]["points"]) + \
                " " + str(x[1]["totals"]["form"]))


#scrapeFixtures(2018,const.LA_LIGA)
#scrapeFixtures(2018,const.PREMIER_LEAGUE)

#printTable(getTable(const.LA_LIGA,2018))

printTable(getTable(const.PREMIER_LEAGUE,2018,None,const.TABLE_TOPTEAMS))

#getFixtures(2018,"Liverpool",True)

