#!/usr/bin/env python3

from lxml import html
import requests
import json

# BBC Sport Football results scraper v0.1

baseurl = "https://www.bbc.co.uk/sport/football/premier-league/scores-fixtures/" # dateslug "/2019-04"

def printJSON(data, indentvalue=2):
    parsed_data = json.loads(data)

    print (json.dumps(parsed_data, indent=indentvalue, sort_keys=True))

def getMonthlyFixtures(dateslugyear=None, dateslugmonth=None):
    
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

    x = 0
    matchDate = ""
    matchcounter = 0

    while x <= len(fixtures) - 1:

        if isinstance(fixtures[x], html.HtmlElement): #It's a date
            matchDate = fixtures[x].text_content() + " " + str(dateslugyear)
            x = x + 1
        else: # It's a fixture
            #print (matchDate + ' ' + fixtures[x] + ' ' + fixtures[x+1] + ' ' + fixtures[x+2] + ' ' + fixtures[x+3])
            
            # Store match in data[]
            matchdetails = {}
            matchdetails["date"] = matchDate
            matchdetails["hometeam"] = fixtures[x]
            matchdetails["homescore"] = fixtures[x+1]
            matchdetails["awayteam"] = fixtures[x+2]
            matchdetails["awayscore"] = fixtures[x+3]

            data.append(matchdetails)

            matchcounter += 1
            x += 4
    
    return data

# Get fixtures for 2018/19 Season - from 2018-08 to 2019-04 - i.e 9 months
numberofmonths = 9
currentmonth = 8
currentyear = 2018

# Sore results in list of match dictionaries
results = []

for m in range(numberofmonths):

    results.append(getMonthlyFixtures(currentyear, currentmonth))

    #printJSON(json.dumps(results))

    if currentmonth >= 12:
        currentmonth = 1
        currentyear += 1
    else:
        currentmonth += 1

printJSON(json.dumps(results))
