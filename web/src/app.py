#!/usr/bin/env python3

from flask import Flask, redirect, url_for
from flask import render_template
import football
import html

app = Flask(__name__)


@app.route("/")
def home():

    output = html.escape("/results/<int:season>/<team>") + "<BR>" + \
        html.escape("/table/<int:season>/<scope>")

    return output


@app.route("/results/")
@app.route("/results/<int:season>/")
@app.route("/results/<int:season>/<team>/")
@app.route("/results/<int:season>/<int:month>/<team>/")
def results(season=None, team=None, month=None):

    fixtures = football.getFixtures(season, team, month)

    output = ""

    for fixture in fixtures:
        home = fixture["home"]
        away = fixture["away"]
        output += home["team"] + " " + str(home["score"]) + \
            "-" + str(away["score"]) + " " + away["team"] + "<BR>"

    return render_template('results.html', data=fixtures)


@app.route("/table/")
@app.route("/table/<int:season>/")
@app.route("/table/<int:season>/<string:scope>/")
@app.route("/table/<int:season>/<int:month>/<int:day>/")
@app.route("/table/<int:season>/<int:month>/<int:day>/<scope>/")
def table(season=None, scope="totals", month=None, day=None):

    # sanity check on scope
    if scope not in ["totals", "home", "away"]:
        return redirect(url_for("home"))

    lastdate = None

    if (season != None) and (month != None) and (day != None):
        lastdate = str(season) + "-" + str(month) + "-" + str(day)
        season = football.whichSeason(month, season)

    table = football.getTable(season, scope, lastdate)

    if table:
        return render_template('table.html', data=table, scope=scope)
    else:
        # No table returned: Error
        return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)
