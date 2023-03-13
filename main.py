from bs4 import BeautifulSoup
from flask import Flask, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import timedelta, datetime
import os
import requests
from requests.structures import CaseInsensitiveDict
from flask_moment import Moment
import json
from odds import get_odds

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


def get_skills_rank(team):
    r = requests.get(f"https://www.robotevents.com/teams/VRC/{team.name.upper()}")
    if r.status_code != 200:
        raise Exception(f"API Error: {r.status_code} {r.text}")
    soup = BeautifulSoup(r.text, "html.parser")
    return soup.select('tr:-soup-contains("World Skills Rank:")')[0].select("td")[0].text


class Team(db.Model):
    name = db.Column(db.Text, primary_key=True)
    id = db.Column(db.Integer)

    def __repr__(self):
        return self.name

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team = db.Column(db.Text, db.ForeignKey('team.name'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def get_prediction(match):
    # print()
    url = "http://vrc-data-analysis.com/_dash-update-component"
    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"
    data = {
        "output": "..prediction-output.children...trueskill-graph.figure..",
        "outputs": [
            {
                "id": "prediction-output",
                "property": "children"
            },
            {
                "id": "trueskill-graph",
                "property": "figure"
            }
        ],
        "inputs": [
            {
                "id": "predict-match-button",
                "property": "n_clicks",
                "value": 3
            }
        ],
        "changedPropIds": [
            "predict-match-button.n_clicks"
        ],
        "state": [
            {
                "id": "red_team1",
                "property": "value",
                "value": match['red'][0].name
            },
            {
                "id": "red_team2",
                "property": "value",
                "value": match['red'][1].name
            },
            {
                "id": "blue_team1",
                "property": "value",
                "value": match['blue'][0].name
            },
            {
                "id": "blue_team2",
                "property": "value",
                "value": match['blue'][1].name
            }
        ]
    }
    resp = requests.post(url, headers=headers, data=json.dumps(data))
    result = resp.json()['response']['prediction-output']['children'].split()
    out = {
        "winner": result[0],
        "odds": float(result[3]),
    }
    return out
    # return resp.json()



def add_team(team):
    db.session.add(team)
    db.session.commit()

def get_team(name):
    return db.session.query(Team).filter_by(name=name).first()

def team_name_to_team(name):
    teamId = api_get("teams", params={"number": name})['data'][0]['id']
    return Team(name=name, id=teamId)
def get_color(team, match):
    # print(team.name, match['red'])
    return "Red" if team.name in [team.name for team in match['red']] else "Blue"

def add_comment(team, text):
    db.session.add(Comment(team=team.name, text=text))
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
                "%Y-%m-%dT%H:%M:%S%z").strftime("%B %#d at %#I:%M %p"),
                
            'name': match['name'],
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
    awardData = {}
    data = api_get(
        f"teams/{team.id}/awards",
        params={
            "season": "173",
        }
    )['data']
    for award in data:
        eventName = award['event']['name']
        eventCode = award['event']['code']
        eventName = eventName + "|" + eventCode
        if awardData.get(eventName, None) is None:
            awardData[eventName] = []
        awardData[eventName].append(award['title'])
    awards = []
    for event, awardList in awardData.items():
        eventData = event.split("|")
        awards.append(
            {"event": {"name": eventData[0], "code": eventData[1]}, "awards": awardList})
    return awards

@app.route("/team/<teamNumber>", methods=["POST", "GET"])
def view_team(teamNumber):
    if bool(Team.query.filter_by(name=teamNumber).first()):
        team = get_team(teamNumber)
    else:
        try:
            team = team_name_to_team(teamNumber)
            add_team(team)
        except Exception as e:
            return render_template("error.html", error = "Team not found")
    if request.method == "POST":
        add_comment(team, request.form.get('comment'))
        return redirect(url_for('view_team', teamNumber=teamNumber))
    
    try:
        matches, awards, skillsRank = get_matches(team), get_awards(team), get_skills_rank(team)
    except Exception as e:
        return render_template("error.html", error="Team is not in VRC")
        matches, awards, skillsRank = [], [], "N/A"
    matchOdds = []
    for match in matches:
        color = "red" if team.name in match['red'] else "blue"
        results = get_prediction(match)
        match['odds'] = f"{results['odds']}% chance you {'win' if get_color(team, match) == results['winner'] else 'lose'}"
        matchOdds.append(
            (100 if get_color(
                team,
                match) != results['winner'] else results['odds'] * 2) -
            results['odds'])
    # print(get_odds(matchOdds))
    # print(matchOdds)
    return render_template(
        "team.html",
        curTeam=team,
        matches=matches,
        awards=awards,
        skillsRank=skillsRank,
        comments=Comment.query.filter_by(team=team.name).all(),
        score=f"{get_odds(matchOdds[1:]):.2f} / {len(matchOdds) - 1}"
    )


@app.route("/delete/<teamNumber>", methods=["POST"])
def delete_comment(teamNumber):
    if request.method == "POST":
        db.session.query(Comment).filter_by(
            id=request.form['comment_id']).delete()
        db.session.commit()
        return redirect(url_for('view_team', teamNumber=teamNumber))


@app.route("/team/", methods=["GET"])
@app.route("/", methods=["POST", "GET"])
def view_index():
    # if request.method == "POST":
    #     create_note(request.form['text'])
    return render_template("base.html")


@app.route('/favicon.ico')
def favicon():
    return url_for('static', filename='favicon.ico')

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    moment = Moment(app)
    app.run(debug=True, host="0.0.0.0", port=5001)
