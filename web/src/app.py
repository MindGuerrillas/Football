#!/usr/bin/env python3

from flask import Flask, redirect, url_for
from flask import render_template
import football

app = Flask(__name__)

@app.route("/")
def home():
    html = "Hello World"
    return html


@app.route("/results/")
@app.route("/results/<int:season>/")
@app.route("/results/<int:season>/<team>/")
def results(season=football.currentSeason(), team=None):

    fixtures = football.getFixtures(season, team)

    output = ""

    for fixture in fixtures:
        home = fixture["home"]
        away = fixture["away"]
        output += home["team"] + " " + str(home["score"]) + \
            "-" + str(away["score"]) + " " + away["team"] + "<BR>"

    return render_template('results.html', data=fixtures)


@app.route("/table/")
@app.route("/table/<int:season>/")
@app.route("/table/<int:season>/<scope>")
def table(season=football.currentSeason(), scope="totals"):

    table = football.getTable(season,scope)

    if table:
        return render_template('table.html', data=table, scope=scope)
    else:
        # No table returned: Error
        return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)
