#!/usr/bin/env python3

from flask import Flask
from flask import render_template
import football

app = Flask(__name__)
 

@app.route("/")
def hello():

    fixtures = football.getFixtures(2018)

    output = ""

    for fixture in fixtures:
        home = fixture["home"]
        away = fixture["away"]
        output += home["team"] + " " + str(home["score"]) + \
            "-" + str(away["score"]) + " " + away["team"] + "<BR>"

    #html = "<h3>Hello World!</h3>" + output

    return render_template('results.html', data=fixtures)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)
