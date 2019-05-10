#!/usr/bin/env python3

from flask import Flask, redirect, url_for
from flask import render_template
import football as fb
from football import const
import html

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

    fixtures = fb.getFixtures(league, season, team, month)
    
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
@app.route("/<league>/table/<int:season>/<int:month>/<int:day>/")
@app.route("/<league>/table/<int:season>/<int:month>/<int:day>/<scope>/")
def tables(league=None, season=None, scope="totals", month=None, day=None):

    # sanity check on scope
    if scope not in ["totals", "home", "away"]:
        return redirect(url_for("home"))

    lastdate = None

    if (season != None) and (month != None) and (day != None):
        lastdate = str(season) + "-" + str(month) + "-" + str(day)
        season = fb.whichSeason(month, season)

    table = fb.getTable(league, season, scope, const.TABLE_FULL, lastdate)

    if table:
        return render_template('table.html', data=table, scope=scope, league=league)
    else:
        # No table returned: Error
        return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)
