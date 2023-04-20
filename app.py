import csv
import hashlib
import hmac
import json
import os
import threading
import time
import config
from datetime import datetime, timedelta

import requests
from flask import Flask, redirect, render_template, request, url_for
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from openskill import create_rating, predict_win
from requests.structures import CaseInsensitiveDict

from odds import get_odds

app = Flask(__name__)
project_dir = os.path.dirname(os.path.abspath(__file__))
database_file = "sqlite:///{}".format(os.path.join(project_dir, "database.db"))
app.config["SQLALCHEMY_DATABASE_URI"] = database_file
db = SQLAlchemy(app)
# Check if teams have been loaded


def api_get(url, params={}):
    headers = CaseInsensitiveDict()

    headers["accept-language"] = "en"
    headers["Authorization"] = "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiZjc5MzgwNmVlOTU3ZmEyYzkyODk3YTdjMTcxOGE1Zjc2ZDZhNTcxODJlM2U5NmI4Mjc5OWIwNjllMjE3ZDQ4ZjJmY2FlOTdjYmJmM2QzMDIiLCJpYXQiOjE2NzQ3OTg5OTAuMDk1NDkxOSwibmJmIjoxNjc0Nzk4OTkwLjA5NTQ5NTksImV4cCI6MjYyMTU3MDE5MC4wOTIwNDM5LCJzdWIiOiI4NDUxOSIsInNjb3BlcyI6W119.KglMyufEjUZ8WceNQJ2GMWj5e2qQsya1QPm7jHBhYg0cqOgCmWi2UqnaMqLsmJubv-Y5Mv-IWjkQ5E6bD8l57qGsvtGllvms_jW4KmdD8w9iDMo8YFNmuMN4OTt00gmOgOoBPZcSeYVwXJnQoX_WWOlxIyeGPKI11bxUNfJXr9xD4NhTG0wSQyS6yS53hh1XEJtDRzUw7Eeoq_PVWIzipmzOqeFnx2NxHOeRpNQj9dGKNBPiTy1M42wiNi8bErONBfwikddQsk_xN2ePfqC1zsM9qL34pWm3enNPqVn92zTzp1fUiwQcBdPttWt-Y52Gy-VUYVnm5ZMq8s5Xk8pB2op5k9EOTl1-8r1BnSYJepwsJSaDRr_JsuhwAvVTisemSKN7bM5dGjLcb8dr6peQLSXUMnedjmf2Kq3AjEOy-CeazL9tAOQ4kqHU75eNnWJek1J9ulSbuZiv3q3xNlKz_TWzLVItyKPB7JMZPqEmpoqnnUev1ZLNAYyZZDdG0sbRlnjP-Ad8paeoYSASpahoKMchc2FMVM3KaWa69XbKEQJ8sDsP3b0gLcXB_a_uq4NWMHm-0P9yqCGPOuz0NYzLGBfN-Kvq2GUzWxSbixxVp952ESdsiGIARq0yFn0c3Lvfp35UhjuggWHuFnGmVnqYCNjSMqBmWaP6K_BrxP39NMc"

    r = requests.get(
        "https://www.robotevents.com/api/v2/" +
        url,
        headers=headers,
        params=params)
    if r.status_code != 200:
        raise Exception(f"API Error: {r.status_code} {r.text}")
    return r.json()

class Team(db.Model):
    number = db.Column(db.Text, primary_key=True)
    id = db.Column(db.Integer)
    name = db.Column(db.Text)
    region = db.Column(db.Text)
    division = db.Column(db.Text)
    skills_rank = db.Column(db.Integer, nullable=True)
    skills_score_overall = db.Column(db.Integer, nullable=True)
    skills_score_autonomous = db.Column(db.Integer, nullable=True)
    skills_score_driver = db.Column(db.Integer, nullable=True)
    true_skill = db.Column(db.JSON, nullable=True)
    ccwm = db.Column(db.Integer, nullable=True)
    opr = db.Column(db.Integer, nullable=True)
    dpr = db.Column(db.Integer, nullable=True)
    win_count = db.Column(db.Integer, nullable=True)
    loss_count = db.Column(db.Integer, nullable=True)
    tie_count = db.Column(db.Integer, nullable=True)
    # matches = db.relationship("Match", backref="team", lazy=True)

    def __repr__(self):
        return self.number


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team = db.Column(db.Text, db.ForeignKey('team.number'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def load_teams_data():
    with open("trueSkill.json", "r") as f:
        teams = json.load(f)
        teams = {team[0]: team[1] for team in teams}

    divisions = {}
    with open("VRC-HS-Divisions.csv", encoding="utf8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            divisions[row[0]] = row[1]
    with open("CCWM.json", "r") as f:
        ccwmData = json.load(f)
    with open("winrate.json", "r") as f:
        winrateData = json.load(f)
    with open("matches.json", "r") as f:
        matchesData = json.load(f)
    with open("world-skill-standings.csv", encoding="utf8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            # print(row[10])
            try:
                team = Team(
                    skills_rank=row[0],
                    skills_score_overall=row[1],
                    skills_score_autonomous=row[2],
                    skills_score_driver=row[3],
                    number=row[10],
                    name=row[11],
                    true_skill=teams.get(row[10], None),
                    region=row[13],
                    division=divisions.get(row[10], None),
                    ccwm=ccwmData.get(row[10], None)["CCWM"],
                    opr=ccwmData.get(row[10], None)["OPR"],
                    dpr=ccwmData.get(row[10], None)["DPR"],
                    win_count=winrateData.get(row[10], None)[0],
                    loss_count=winrateData.get(row[10], None)[1],
                    tie_count=winrateData.get(row[10], None)[2],
                )
            except Exception as e:
                print(e)
                print(row[10])
                continue
            add_team(team)


def get_prediction(match):
    result = predict_win(
        [
            [
                teams[match['red'][0].name],
                teams[match['red'][1].name]],
            [
                teams[match['blue'][0].name],
                teams[match['blue'][1].name]
            ]
        ])
    return {
        "winner": "Blue" if result[0] > result[1] else "Red",
        "odds": float(f"{max(result) * 100:.1f}"),
    }


def add_team(team):
    db.session.add(team)
    db.session.commit()


def get_team(number):
    return db.session.query(Team).filter_by(number=number).first()


def team_name_to_team(number):
    teamData = api_get("teams", params={"number": number})['data'][0]
    team = Team(
        number=teamData['number'],
        id=teamData['id'],
        name=teamData['team_name'],
        region=teamData['location']['region'],
    )
    return team


def get_team_id(team):
    return api_get("teams", params={"number": team.number})['data'][0]['id']


def get_color(team, match):
    return "Red" if team.number in [
        team.number for team in match['red']] else "Blue"


def add_comment(team, text):
    db.session.add(Comment(team=team.number, text=text))
    db.session.commit()


def get_matches(team):
    matches = []
    data = api_get(
        f"teams/{team.id}/matches",
        params={
            "event": "49725",
        }
    )['data']
    for match in data:
        tempMatch = {

            'time': "N/A" if not match['scheduled'] else datetime.strptime(
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
@app.route("/team/<teamNumber>/", methods=["POST", "GET"])
def view_team(teamNumber):
    teamNumber = teamNumber.upper()
    if bool(Team.query.filter_by(number=teamNumber).first()):
        team = get_team(teamNumber)
    else:
        try:
            team = team_name_to_team(teamNumber)
            add_team(team)
        except Exception as e:
            print(e)
            return render_template("error.html", error="Team not found")
    if request.method == "POST":
        add_comment(team, request.form.get('comment'))
        print(team, request.form.get('comment'))
        return redirect(url_for('view_team', teamNumber=teamNumber))
    if team.id is None:
        team.id = get_team_id(team)
        db.session.commit()
    try:
        # time each api call
        start = time.time()
        matches = get_matches(team)
        print(f"Matches: {time.time() - start}")
        start = time.time()
        awards = get_awards(team)
        print(f"Awards: {time.time() - start}")
    except Exception as e:
        print(e)
        return render_template("error.html", error="Team is not in VRC")
    matchOdds = []
    # for match in matches:
    #     color = "red" if team.number in match['red'] else "blue"
    #     results = get_prediction(match)
    #     match['odds'] = f"{results['odds']}% chance you {'win' if get_color(team, match) == results['winner'] else 'lose'}"
    #     matchOdds.append(
    #         (100 if get_color(
    #             team,
    #             match) != results['winner'] else results['odds'] * 2) -
    #         results['odds'])
    # print(get_odds(matchOdds))
    # print(matchOdds)
    # awards = dict(reversed(awards.items()))
    return render_template(
        "team.html",
        curTeam=team,
        matches=matches,
        awards=reversed(awards),
        comments=Comment.query.filter_by(team=team.number).all(),
        score=f"{get_odds(matchOdds[1:]):.2f} / {max(0, len(matchOdds) - 1)}"
    )


@app.route("/delete/<teamNumber>/", methods=["POST"])
def delete_comment(teamNumber):
    if request.method == "POST":
        db.session.query(Comment).filter_by(
            id=request.form['comment_id']).delete()
        db.session.commit()
        return redirect(url_for('view_team', teamNumber=teamNumber))


@app.route("/team/", methods=["GET"])
@app.route("/", methods=["POST", "GET"])
def view_index():
    divisions = {'All': [],
                 'Math': [],
                 "Technology": [],
                 "Science": [],
                 "Engineering": [],
                 "Arts": [],
                 "Innovate": [],
                 "Spirit": [],
                 "Design": [],
                 "Research": [],
                 "Opportunity": [],
                 }
    for team in Team.query.all():
        if team.division:
            divisions[team.division].append(team)
            divisions['All'].append(team)
    # order divisions
    return render_template("index.html", divisions=divisions)


@app.route('/favicon.ico')
def favicon():
    return url_for('static', filename='favicon.ico')



@app.route('/webhook', methods=['POST'])
def webhook():
    # X-Hub-Signature-256: sha256=<hash>
    sig_header = 'X-Hub-Signature-256'
    if sig_header in request.headers:
        header_splitted = request.headers[sig_header].split("=")
        if len(header_splitted) == 2:
            req_sign = header_splitted[1]
            computed_sign = hmac.new(
                config.webhook.encode('utf-8'),
                request.data,
                hashlib.sha256).hexdigest()
            # is the provided signature ok?
            if hmac.compare_digest(req_sign, computed_sign):
                # create a thread to return a response (so GitHub is happy) and start a 2s timer before exiting this app
                # this is supposed to be run by systemd unit which will restart it automatically
                # the [] syntax for lambda allows to have 2 statements
                threading.Thread(
                    target=lambda: [time.sleep(2), os._exit(-1)]).start()
    return "ok"



if __name__ == "__main__":
    with app.app_context():
        # db.drop_all()
        db.create_all()
        if not Team.query.first():
            load_teams_data()
    moment = Moment(app)
    if os.environ['ENV'] == 'prod':
        app.run(host="0.0.0.0", port=80)
    else:
        app.run(debug=True, host="127.0.0.1", port=5001)
