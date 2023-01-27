from flask import Flask, request, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import requests
from requests.structures import CaseInsensitiveDict
from flask_moment import Moment

app = Flask(__name__)
project_dir = os.path.dirname(os.path.abspath(__file__))
database_file = "sqlite:///{}".format(os.path.join(project_dir, "database.db"))
app.config["SQLALCHEMY_DATABASE_URI"] = database_file
db = SQLAlchemy(app)

def api_get(url, params={}):
    headers = CaseInsensitiveDict()


    headers["accept-language"] = "en"
    headers["Authorization"] = "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiZjc5MzgwNmVlOTU3ZmEyYzkyODk3YTdjMTcxOGE1Zjc2ZDZhNTcxODJlM2U5NmI4Mjc5OWIwNjllMjE3ZDQ4ZjJmY2FlOTdjYmJmM2QzMDIiLCJpYXQiOjE2NzQ3OTg5OTAuMDk1NDkxOSwibmJmIjoxNjc0Nzk4OTkwLjA5NTQ5NTksImV4cCI6MjYyMTU3MDE5MC4wOTIwNDM5LCJzdWIiOiI4NDUxOSIsInNjb3BlcyI6W119.KglMyufEjUZ8WceNQJ2GMWj5e2qQsya1QPm7jHBhYg0cqOgCmWi2UqnaMqLsmJubv-Y5Mv-IWjkQ5E6bD8l57qGsvtGllvms_jW4KmdD8w9iDMo8YFNmuMN4OTt00gmOgOoBPZcSeYVwXJnQoX_WWOlxIyeGPKI11bxUNfJXr9xD4NhTG0wSQyS6yS53hh1XEJtDRzUw7Eeoq_PVWIzipmzOqeFnx2NxHOeRpNQj9dGKNBPiTy1M42wiNi8bErONBfwikddQsk_xN2ePfqC1zsM9qL34pWm3enNPqVn92zTzp1fUiwQcBdPttWt-Y52Gy-VUYVnm5ZMq8s5Xk8pB2op5k9EOTl1-8r1BnSYJepwsJSaDRr_JsuhwAvVTisemSKN7bM5dGjLcb8dr6peQLSXUMnedjmf2Kq3AjEOy-CeazL9tAOQ4kqHU75eNnWJek1J9ulSbuZiv3q3xNlKz_TWzLVItyKPB7JMZPqEmpoqnnUev1ZLNAYyZZDdG0sbRlnjP-Ad8paeoYSASpahoKMchc2FMVM3KaWa69XbKEQJ8sDsP3b0gLcXB_a_uq4NWMHm-0P9yqCGPOuz0NYzLGBfN-Kvq2GUzWxSbixxVp952ESdsiGIARq0yFn0c3Lvfp35UhjuggWHuFnGmVnqYCNjSMqBmWaP6K_BrxP39NMc"

    r = requests.get("https://www.robotevents.com/api/v2/" + url, headers=headers, params=params)
    if r.status_code != 200:
        raise Exception(f"API Error: {r.status_code} {r.text}")
    return r.json()

class Team(db.Model):
    name = db.Column(db.Text, primary_key=True)
    id = db.Column(db.Integer)
    notes = db.Column(db.Text, nullable=False, default='')

    def __repr__(self):
        return self.name

def add_team(team):
    db.session.add(team)
    db.session.commit()

def get_team(name):
    return db.session.query(Team).filter_by(name=name).first()

def team_name_to_team(name):
    teamId = api_get("teams", params={"number": name})['data'][0]['id']
    return Team(name=name, id=teamId)

def update_note(team, notes):
    db.session.query(Team).filter_by(name=team.name).update({
        "notes": notes,
    })
    db.session.commit()


def get_matches(team):
    matches = []
    data = api_get(
        f"teams/{team.id}/matches",
        params={
            "event": "47800",
        }
    )['data']
    for match in data:
        tempMatch = {
            'time': datetime.strptime(
                match['scheduled'],
                "%Y-%m-%dT%H:%M:%S%z"),
            'red': [],
            'blue': []}
        for alliance in match['alliances']:
            for team in alliance['teams']:
                team = team['team']
                tempMatch[alliance['color']].append(
                    Team(name=team['name'], id=team['id']))
        matches.append(tempMatch)
    return matches


def get_awards(team):
    awards = {}
    data = api_get(
        f"teams/{team.id}/awards",
        params={
            "season": "173",
        }
    )['data']
    for award in data:
        eventName = award['event']['name']
        if awards.get(eventName, None) is None:
            awards[eventName] = []
        awards[eventName].append(award['title'])

    return awards


@app.route("/team/<teamNumber>", methods=["POST", "GET"])
def view_team(teamNumber):
    if bool(Team.query.filter_by(name=teamNumber).first()):
        team = get_team(teamNumber)
    else:
        team = team_name_to_team(teamNumber)
        add_team(team)
    if request.method == "POST":
        update_note(team, request.form.get('notes'))
    return render_template(
        "team.html",
        curTeam=team,
        matches=get_matches(team),
        awards=get_awards(team),
    )
@app.route("/", methods=["POST", "GET"])
def view_index():
    # if request.method == "POST":
    #     create_note(request.form['text'])
    return render_template("index.html")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    moment = Moment(app)
    app.run(debug=True, port=5001)
