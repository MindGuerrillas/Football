#!/usr/bin/env python3

from flask import Flask, redirect, url_for
from flask import render_template
import football as fb
from football import const
import html
import datetime
from datetime import timedelta

app = Flask(__name__)

@app.route("/")
def home():

    output = html.escape("/results/<int:season>/<team>") + "<BR>" + \
        html.escape("/table/<int:season>/<scope>")

    return output


@app.route("/<league>/results/")
@app.route("/<league>/results/<int:season>/")
@app.route("/<league>/results/<int:season>/<team>/")
@app.route("/<league>/results/<int:season>/<int:month>/")
@app.route("/<league>/results/<int:season>/<int:month>/<team>/")
def results(league, season=None, team=None, month=None):

    fixtures = fb.getFixtures(league, season, team, [], month)
    
    output = ""

    for fixture in fixtures:
        home = fixture["home"]
        away = fixture["away"]
        output += home["team"] + " " + str(home["score"]) + \
            "-" + str(away["score"]) + " " + away["team"] + "<BR>"

    return render_template('results.html', data=fixtures)


@app.route("/tables/")  # defaults to current premier league
@app.route("/<league>/table/")
@app.route("/<league>/table/<int:season>/")
@app.route("/<league>/table/<int:season>/<string:scope>/")
@app.route("/<league>/table/until/<int:untilseason>/<int:untilmonth>/<int:untilday>/")
@app.route("/<league>/table/until/<int:untilseason>/<int:untilmonth>/<int:untilday>/<scope>/")
@app.route("/<league>/table/from/<int:fromseason>/<int:frommonth>/<int:fromday>/")
@app.route("/<league>/table/from/<int:fromseason>/<int:frommonth>/<int:fromday>/<scope>/")
@app.route("/<league>/table/from/<int:fromseason>/<int:frommonth>/<int:fromday>/until/<int:untilseason>/<int:untilmonth>/<int:untilday>/")
@app.route("/<league>/table/from/<int:fromseason>/<int:frommonth>/<int:fromday>/until/<int:untilseason>/<int:untilmonth>/<int:untilday>/<scope>/")
def tables(league=const.PREMIER_LEAGUE, season=None, scope="totals", 
            fromseason=None, frommonth=None, fromday=None,
            untilseason=None, untilmonth=None, untilday=None
            ):

    # sanity check on scope
    if scope not in ["totals", "home", "away"]:
        return redirect(url_for("home"))

    fromdate = None
    untildate = None

    if (untilseason != None) and (untilmonth != None) and (untilday != None):
        untildate = str(untilseason) + "-" + str(untilmonth) + "-" + str(untilday)
        season = fb.whichSeason(untilmonth, untilseason)

    if (fromseason != None) and (frommonth != None) and (fromday != None):
        fromdate = str(fromseason) + "-" + str(frommonth) + "-" + str(fromday)
        season = fb.whichSeason(frommonth, fromseason)

    table = fb.getTable(league, season, scope, [], fromdate, untildate)

    if table:
        return render_template('table.html', data=table, scope=scope, league=league)
    else:
        # No table returned: Error
        return redirect(url_for("home"))


@app.route("/bigsixform/")
def bigsixform(league=const.PREMIER_LEAGUE, season=fb.currentSeason()):

    teamFilter = const.TOPTEAMS[league]

    data = []

    for team in teamFilter:

        teamdata = {}

        teamdata["teamname"] = team
        teamdata["data"] = []

        teamdata["formaverage"] = 0

        formtotal = 0
        matchtotal = 0

        # Get team's games against other TOPTEAMS.
        for game in fb.getFixtures(league, season, team, teamFilter):

            # 1. for each game get the opponents form upto the game date - 1            
            form = []
            gameDate = game["date"] - timedelta(days=1) ## MINUS ONE DAY

            if game["home"]["teamslug"] == team: # Home Game
                form = fb.getTeamFormByDate("premier-league",game["away"]["teamslug"],gameDate)
            else:
                form = fb.getTeamFormByDate("premier-league",game["home"]["teamslug"],gameDate)
            
            matchdata = {}

            # Format Game.date to 27 Jan
            game["date"] = game["date"].strftime("%d %b")

            matchdata["game"] = game
            matchdata["form"] = form

            formscore = 0

            for f in form:
                if f == "W":
                    formscore = formscore + 3
                elif f == "D":
                    formscore += 1

            matchdata["formscore"] = formscore

            teamdata["data"].append(matchdata)

            matchtotal += 1
            formtotal = formtotal + formscore

        teamdata["formaverage"] = formtotal / matchtotal

        data.append(teamdata)

    return render_template("bigsixform.html", data=data, league=league)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)
