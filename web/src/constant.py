#!/usr/bin/env python3

# Database
MONGODB_SERVER      =   "mongo"
MONGODB_USER        =   "root"
MONGODB_PASSWORD    =   "example"

VERBOSE             =   True

# dateslug "/2019-04"
BASE_URL = "https://www.bbc.co.uk/sport/football/LEAGUETAG/scores-fixtures/"

SEASON_START_MONTH  =   8
SEASON_LENGTH       =   10

SORT_ORDER_ASC      =   1
SORT_ORDER_DESC     =   -1

# Leagues
PREMIER_LEAGUE  =   "premier-league"
CHAMPIONSHIP    =   "championship"
LA_LIGA         =   "spanish-la-liga"


TOPTEAMS = {
            "premier-league" : ["liverpool","manchester-united","manchester-city","arsenal","chelsea","tottenham-hotspur"],
            "spanish-la-liga" : ["real-madrid","barcelona","valencia","sevilla","atletico-madrid"]
        }
