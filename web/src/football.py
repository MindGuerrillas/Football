#!/usr/bin/env python3

from lxml import html
import requests
import pymongo
from pymongo import MongoClient
from dateutil.parser import parse
import hashlib
import datetime
import time
from datetime import timedelta
import constant as const
import unicodedata
import utilities as utils
from collections import deque

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
    return teamslug.title().replace("-", " ")


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


def getFixtures(league=const.PREMIER_LEAGUE, season=currentSeason(), club=None, teamFilter = [], month=None):
    
    # Sanity check
    if season == None:
        season = currentSeason()
    if league == None:
        league = const.PREMIER_LEAGUE

    db = getDatabase()
 
    resultsQuery = {}
    resultsQuery["season"] = season
    resultsQuery["league"] = league

    if month:
        resultsQuery["$expr"] = { "$eq": [{ "$month": "$date" }, month] }

    if club:
        club = __teamnameSlug(club)
        resultsQuery["$or"] = [{"home.teamslug": club}, {"away.teamslug": club}]

    #resultsQuery["date"] = {"$gte": fromDate,"$lte":untilDate}
    
    if teamFilter != []:
        resultsQuery["home.teamslug"] = { "$in": teamFilter}
        resultsQuery["away.teamslug"] = { "$in": teamFilter}

    utils.debuggingPrint("Running Results Query: " + str(resultsQuery))
    fixtures = db.results.find(resultsQuery).sort([("date", 1), ("home.team", 1)])

    return list(fixtures)


# Get the date of the nearest game to the given targetDate for the given query
# Either before it SORT_ORDER_DESC or after it SORT_ORDER_ASC
def getNearestGameDate(query, targetDate, beforeOrAfter):
    
    db = getDatabase()

    if beforeOrAfter == const.SORT_ORDER_ASC:
        query["date"] = {"$gte":targetDate}
    elif beforeOrAfter == const.SORT_ORDER_DESC:
        query["date"] = {"$lte":targetDate}

    game = db.results.find(query, {"date": 1}).sort("date", beforeOrAfter).limit(1)
    
    for result in game:
        return result["date"]

    return targetDate

# Get start and end date of season so far
def getSeasonDates(query):
    
    seasonDates = { "startDate": None, "endDate": None}

    db = getDatabase()
    
    # get first game
    game = db.results.find(query, {"date": 1}).sort("date", const.SORT_ORDER_ASC).limit(1)
    
    for result in game:
        seasonDates["startDate"] = result["date"]

    # get last game
    game = db.results.find(query, {"date": 1}).sort("date", const.SORT_ORDER_DESC).limit(1)
    
    for result in game:
        seasonDates["endDate"] = result["date"]

    return seasonDates

def __buildTable(league=const.PREMIER_LEAGUE, season=currentSeason(), fromDate=None, untilDate=None, teamFilter=[]):

    # Analyse results for season & generate a league table
    
    # Table format
    #
    # _id:          SHA1 hash of league + teamFilter + untilDate and fromDate
    # fromdate:     date the table starts at i.e. date of first fixture
    # untildate:    date table goes up to i.e. date of last fixture
    # created:      datetime that table was generated
    # season:       season id tag e.g. 2018
    # league:       league tag e.g. premier-league
    # filter: []    list of teamslugs to filter by 
    # standings {   a dictionary containing 1 dictionary per team
    #   "liverpool": # This is the __teamnameSlug e.g. west-ham-united
    #   {
    #       "teamname": Liverpool,
    #       "position": Only set after sorting in getTable
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

    resultsQuery = {}
    resultsQuery["season"] = season
    resultsQuery["league"] = league
    
    dateFilter  = {}

    if untilDate != None:
        dateFilter["$lte"] = parse(str(untilDate))
    if fromDate != None:
        dateFilter["$gte"] = parse(str(fromDate))
    if dateFilter:
        resultsQuery["date"] = dateFilter

    if teamFilter != []:
        resultsQuery["home.teamslug"] = { "$in": teamFilter}
        resultsQuery["away.teamslug"] = { "$in": teamFilter}

    utils.debuggingPrint("Running Results Query: " + str(resultsQuery))

    fixtures = db.results.find(resultsQuery).sort([("date", 1), ("home.team", 1)])

    lastFixtureDate = None
    fixture_count = 0
    
    ############################################################
    # Build an empty table containing all teams for specified season and league

    table = {}
    table["league"] = league
    table["season"] = season

    table["fromdate"] = parse(str(fromDate))
    table["untildate"] = None
    table["created"] = parse(str(datetime.datetime.now()))

    table["filter"] = teamFilter    
    table["standings"] = {}

    standings = {}

    # Get Teams list
    seasonQuery = { "season": season, "league": league}

    seasonResults = db.seasons.find(seasonQuery).next()

    for team in seasonResults["teams"]:
        addTeam = True
        if teamFilter:
            if team["teamslug"] not in teamFilter:
                addTeam = False
        
        if addTeam == True:
            standings[team["teamslug"]] = {
                        "teamname": team["teamname"],
                        "home": {"played": 0,"won": 0,"drawn": 0,"lost": 0,"for": 0,"against": 0,"gd": 0,"points": 0,"form": deque([],5)},
                        "away": {"played": 0,"won": 0,"drawn": 0,"lost": 0,"for": 0,"against": 0,"gd": 0,"points": 0,"form": deque([],5)},
                        "totals": {"played": 0,"won": 0,"drawn": 0,"lost": 0,"for": 0,"against": 0,"gd": 0,"points": 0,"form": deque([],5)}
                        }
    ############################################################

    for fixture in fixtures:

        if lastFixtureDate == None:
            lastFixtureDate = fixture["date"]
        else:
            if fixture["date"] > lastFixtureDate:
                lastFixtureDate = fixture["date"]

        home = fixture["home"]
        away = fixture["away"]            
        
        # Add goals to table
        # home team
        standings[home["teamslug"]]["home"]["for"] += home["score"]
        standings[home["teamslug"]]["home"]["against"] += away["score"]
        standings[home["teamslug"]]["home"]["gd"] += (home["score"] - away["score"])
        # away team
        standings[away["teamslug"]]["away"]["for"] += away["score"]
        standings[away["teamslug"]]["away"]["against"] += home["score"]
        standings[away["teamslug"]]["away"]["gd"] += (away["score"] - home["score"])       

        # Who won? # Update Points and Form for each outcome
        if home["score"] > away["score"]: # Home Win
            standings[home["teamslug"]]["home"]["won"] += 1
            standings[home["teamslug"]]["home"]["points"] += 3
            standings[away["teamslug"]]["away"]["lost"] += 1
            
            standings[home["teamslug"]]["home"]["form"].append("W")
            standings[away["teamslug"]]["away"]["form"].append("L")            
            standings[home["teamslug"]]["totals"]["form"].append("W")
            standings[away["teamslug"]]["totals"]["form"].append("L")

        elif away["score"] > home["score"]: # Away Win
            standings[away["teamslug"]]["away"]["won"] += 1
            standings[away["teamslug"]]["away"]["points"] += 3
            standings[home["teamslug"]]["home"]["lost"] += 1

            standings[home["teamslug"]]["home"]["form"].append("L")
            standings[away["teamslug"]]["away"]["form"].append("W")
            standings[home["teamslug"]]["totals"]["form"].append("L")
            standings[away["teamslug"]]["totals"]["form"].append("W")            
                        
        else: # draw
            standings[home["teamslug"]]["home"]["drawn"] += 1
            standings[home["teamslug"]]["home"]["points"] += 1
            standings[away["teamslug"]]["away"]["drawn"] += 1
            standings[away["teamslug"]]["away"]["points"] += 1

            standings[home["teamslug"]]["home"]["form"].append("D")
            standings[away["teamslug"]]["away"]["form"].append("D")
            standings[home["teamslug"]]["totals"]["form"].append("D")
            standings[away["teamslug"]]["totals"]["form"].append("D")

        # Add the game
        standings[home["teamslug"]]["home"]["played"] += 1
        standings[away["teamslug"]]["away"]["played"] += 1

        fixture_count += 1

    if fixture_count == 0: # No fixtures processed so no table either
        utils.debuggingPrint("No games found - No table produced")
        return None

    table["standings"] = standings
    table["untildate"] = parse(str(lastFixtureDate))
    
    # generate _id hash
    idhash = league + str(teamFilter) + str(table["untildate"]) + str(table["fromdate"])
    table["_id"] = hashlib.sha1(idhash.encode()).hexdigest()

    # Calculate Totals
    for team in table["standings"]:
        t = table["standings"][team]

        # Add home & away numbers
        for item in ["played","won","lost","drawn","for","against","gd","points"]:
            t["totals"][item] = t["home"][item] + t["away"][item]
            
        # Form - change deque objects to list for json storage
        for scope in ["home","away","totals"]:
            t[scope]["form"] = list(t[scope]["form"])
        
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

# scope must be totals, home or away
def getTable(league=const.PREMIER_LEAGUE, season=currentSeason(), 
            scope=None, teamFilter=[], 
            fromDate = None,
            untilDate=datetime.datetime.now()            
            ):

    # Sanity check variables
    if season == None:
        season = currentSeason()
    if teamFilter == None:
        teamFilter = []
    if untilDate == None:
        untilDate = datetime.datetime.now()
    if fromDate == None:  # Default to beginning of season
        fromDate = str(season) + "-" + str(const.SEASON_START_MONTH) + "-01" 
    
    if scope not in ["totals","home","away"]:
        scope = "totals"
    if league == None:
        league = const.PREMIER_LEAGUE

    # Sort teamFilter to ensure matches
    teamFilter.sort()

    # check for invalid dates being passed in
    try:
        untilDate = parse(str(untilDate))
    except: # goto default setting
        untilDate = parse(str(datetime.datetime.now()))
    
    try:
        fromDate = parse(str(fromDate))
    except: # goto default setting
        fromDate = parse(str(season) + "-" + str(const.SEASON_START_MONTH) + "-01")

    # scope will order the final table by home, away or combined totals
    if (scope != "home") and (scope != "away"):
        scope = "totals"

    # Get table
    db = getDatabase()

    # 1. find nearest game dates for fromDate and untilDate

    resultsQuery = {}
    resultsQuery["league"] = league
    resultsQuery["season"] = season
    resultsQuery["date"] = {"$gte": fromDate,"$lte":untilDate}
    
    if teamFilter != []:
        resultsQuery["home.teamslug"] = { "$in": teamFilter}
        resultsQuery["away.teamslug"] = { "$in": teamFilter}

    firstGameDate = getNearestGameDate(resultsQuery, fromDate, const.SORT_ORDER_ASC)
    lastGameDate = getNearestGameDate(resultsQuery, untilDate, const.SORT_ORDER_DESC)

    # 2. check if table exists for exact current parameters, match on _id hash
    
    # generate _id hash
    idhash = league + str(teamFilter) + str(lastGameDate) + str(firstGameDate)
    _id = hashlib.sha1(idhash.encode()).hexdigest()

    tableQuery = {}
    tableQuery["_id"] = _id

    utils.debuggingPrint("Search for Table _id: " + _id)

    # 3. Find Table
    try:        
        utils.debuggingPrint("Running Table Query: " + str(tableQuery))
        
        # use .next() to get document rather than cursor
        # pull the latest table from the database        
        data = db.tables.find(tableQuery).sort("untildate", -1).limit(1).next() 

    except StopIteration:
        utils.debuggingPrint("No tables found - Generate one")

        data = __buildTable(league, season, firstGameDate, lastGameDate, teamFilter)

        if data == None:
            utils.debuggingPrint("No tables could be generated")
            return None

    standings = data["standings"]

    # Sort by Name, Goals For, GD and then Points for the requested scope (home, away, totals)
    # return sorted list - table - as [ (team, {data}) ]
    table = sorted(standings.items(),key=lambda x: x[0])
    table = sorted(table,key=lambda x: x[1][scope]["for"], reverse=True)
    table = sorted(table,key=lambda x: x[1][scope]["gd"], reverse=True)
    table = sorted(table,key=lambda x: x[1][scope]["points"], reverse=True)

    # Set Position for each team in current sorted state
    position = 1

    for team in table:
        team[1]["position"] = position
        position += 1

    return table


# Returns a team's form on a given date
def getTeamFormByDate(league, teamslug, atDate=datetime.datetime.now()):

    # Generate a table for the date
    table = getTable(league, season=whichSeason(None,None,atDate), 
            scope=None, teamFilter=[], 
            fromDate = None,
            untilDate=atDate)
    
    # Find the team and return the form
    for team in table:
        if team[0] == teamslug:
            return team[1]["totals"]["form"]

    return []


def printTable(table):
    if table == None:
        return ""
        
    for x in table:
        print (x[1]["teamname"] + " " + str(x[1]["totals"]["gd"]) + " " + str(x[1]["totals"]["points"]) + \
                " " + str(x[1]["totals"]["form"]))


def buildPositionsGraph(league, season, teamFilter=[]):

    # 1. Build array in form    [
    #                               ['Week', 'liverpool', 'chelsea'.... ]
    #                               [   1       1           3           ]
    #                               [   2       1           4           ]
    #                           ]
    # listing position of teams after 1 week intervals from the first weekend

    # Get dates of matches in season
    resultsQuery = {}
    resultsQuery["league"] = league
    resultsQuery["season"] = season
    
    db = getDatabase()

    matchDates = db.results.distinct("date", resultsQuery)
    
    matchDates.sort()

    # 2. Get a table for each match day

    dataArray = []
    headerArray = []

    for matchdate in matchDates:

        standings = getTable(league, season, None, [], None, matchdate)
        
        # sort by name to ensure array consistancy
        standings = sorted(standings,key=lambda x: x[0])

        # build header array of team names on 1st pass
        if not headerArray:
            headerArray.append("Match Day")

            for team in standings:
                if teamFilter:
                    if team[0] in teamFilter:
                        headerArray.append(team[0])
                else:
                    headerArray.append(team[0])

            dataArray.append(headerArray)

        # Add details to array
        weeklyData = []
        
        weeklyData.append(matchdate.strftime("%d %b"))

        for team in standings:
            if teamFilter:
                if team[0] in teamFilter:            
                    weeklyData.append(team[1]["position"])
            else:
                weeklyData.append(team[1]["position"])

        dataArray.append(weeklyData)

    return dataArray

def buildPointsGraph(league, season, teamFilter=[]):

    # 1. Build array in form    [
    #                               ['Week', 'liverpool', 'chelsea'.... ]
    #                               [   1       3           3           ]
    #                               [   2       6           4           ]
    #                           ]
    # listing position of teams after 1 week intervals from the first weekend

    # Get start and end date for season
    resultsQuery = {}
    resultsQuery["league"] = league
    resultsQuery["season"] = season
    
    seasonDates = getSeasonDates(resultsQuery)

    # 2. Get a table for each week from startdate
    currentWeek = seasonDates["startDate"] + timedelta(days=3) ## Add days until end of weekend   

    dataArray = []
    headerArray = []

    while currentWeek <= seasonDates["endDate"] + timedelta(days=3):

        standings = getTable(league, season, None, [], None, currentWeek)
        
        # sort by name to ensure array consistancy
        standings = sorted(standings,key=lambda x: x[0])

        # build header array of team names on 1st pass
        if not headerArray:
            headerArray.append("Week")

            for team in standings:
                if teamFilter:
                    if team[0] in teamFilter:
                        headerArray.append(team[0])
                else:
                    headerArray.append(team[0])

            dataArray.append(headerArray)

        # Add details to array
        weeklyData = []
        
        weeklyData.append(currentWeek.strftime("%d %b"))

        for team in standings:
            if teamFilter:
                if team[0] in teamFilter:            
                    weeklyData.append(team[1]["totals"]["points"])
            else:
                weeklyData.append(team[1]["totals"]["points"])

        dataArray.append(weeklyData)

        currentWeek = currentWeek + timedelta(days=7)

    return dataArray

def buildLeagueTeamsList(league, season, teamList=[]):

    try:
        # Store teams as

        # "league": "premier-league"
        # "season": 2018
        # "teams": [{ "teamname": "Manchester City", "teamslug": "manchester-city"}]

        data = {}
        idhash = league + str(season)

        data["_id"] = hashlib.sha1(idhash.encode()).hexdigest()
        data["league"] = league
        data["season"] = season
        data["teams"] = []

        for team in teamList:
            data["teams"].append({ "teamname": team, "teamslug": __teamnameSlug(team)})

        # save results to database
        db = getDatabase()
        collection = db.seasons
        collection.insert_one(data)
        
        print ("Teams Stored")

    except:
        return

    return

def getDistinctTeams(league, season):
    db = getDatabase()
    query = { "league": league, "season": season}

    teams = db.results.distinct("home.team", query)
    teams.sort()
    print (teams)



"""
premier_teams_2018 = ['AFC Bournemouth', 'Arsenal', 'Brighton & Hove Albion', 'Burnley', 'Cardiff City', 
                'Chelsea', 'Crystal Palace', 'Everton', 'Fulham', 'Huddersfield Town', 'Leicester City', 
                'Liverpool', 'Manchester City', 'Manchester United', 'Newcastle United', 'Southampton', 
                'Tottenham Hotspur', 'Watford', 'West Ham United', 'Wolverhampton Wanderers']

la_liga_teams_2018 = ['Alavés', 'Athletic Bilbao', 'Atlético Madrid', 'Barcelona', 'Celta Vigo', 'Eibar', 
                    'Espanyol', 'Getafe', 'Girona', 'Huesca', 'Leganés', 'Levante', 'Rayo Vallecano', 'Real Betis', 
                    'Real Madrid', 'Real Sociedad', 'Real Valladolid', 'Sevilla', 'Valencia', 'Villarreal']
"""

#getDistinctTeams(const.LA_LIGA,2018)

#buildLeagueTeamsList(const.LA_LIGA, 2018,la_liga_teams_2018)

#print (buildPositionsGraph("premier-league",2018))

#scrapeFixtures(2018,const.LA_LIGA)
#scrapeFixtures(2018,const.PREMIER_LEAGUE)

"""getTable(league=const.PREMIER_LEAGUE, season=currentSeason(), 
            scope=None, teamFilter=[], 
            fromDate = None,
            untilDate=datetime.datetime.now()            
            ):
"""

# PL full table 
#printTable(getTable(const.PREMIER_LEAGUE,2018,None,const.TOPTEAMS[const.PREMIER_LEAGUE]))

# PL BIG 6 Pre & Post New Year
#printTable(getTable(const.PREMIER_LEAGUE,2018,None,const.TOPTEAMS[const.PREMIER_LEAGUE],None,"2018-12-31"))
#printTable(getTable(const.PREMIER_LEAGUE,2018,None,const.TOPTEAMS[const.PREMIER_LEAGUE],"2019-1-1"))

# PL table from Start of season until end of 2018
#printTable(getTable(const.PREMIER_LEAGUE,2018,None,[],None,"2018-12-31"))

# PL table from start of 2019 to now
#printTable(getTable(const.PREMIER_LEAGUE,2018,None,[],"2019-1-1"))

#printTable(getTable(const.PREMIER_LEAGUE,2018,None,[],None, "2018-11-20"))


#for game in getFixtures(const.PREMIER_LEAGUE, 2018, "Liverpool", const.TOPTEAMS[const.PREMIER_LEAGUE]):
#    print (game["home"]["team"] + " vs " + game["away"]["team"] + "  -  " + str(game["date"]))