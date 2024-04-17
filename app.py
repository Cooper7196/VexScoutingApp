import csv
import hashlib
import hmac
import json
import os
import threading
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, redirect, render_template, request, url_for
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from openskill import create_rating, predict_win, Rating
from requests.structures import CaseInsensitiveDict

import config
from odds import get_odds

app = Flask(__name__)
project_dir = os.path.dirname(os.path.abspath(__file__))
database_file = "sqlite:///{}".format(os.path.join(project_dir, "database.db"))
app.config["SQLALCHEMY_DATABASE_URI"] = database_file
db = SQLAlchemy(app)
trueSkillData = {}
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
    print(r.url)
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
    age_group = db.Column(db.Text, nullable=True)
    # matches = db.relationship("Match", backref="team", lazy=True)

    def __repr__(self):
        return self.number


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team = db.Column(db.Text, db.ForeignKey('team.number'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def load_teams_data():

    # with open("trueSkill.json", "r") as f:
    #     trueSkillData = json.load(f)
    #     trueSkillData = {team[0]: team[1] for team in trueSkillData}
    # with open("CCWM.json", "r") as f:
    #     ccwmData = json.load(f)
    # with open("winrate.json", "r") as f:
    #     winrateData = json.load(f)

    performanceData = {}
    defaultPerformanceData = {
        "True Skill": "N/A",
        "CCWM": "N/A",
        "Total Wins": 0,
        "Total Losses": 0,
        "Total Ties": 0,
    }

    xl_file = pd.read_excel("vrc-data-analysis.xlsx")

    for row in xl_file.itertuples():
        if row.teamNumber == "55692B":
            print(row)
        if row.ccwm != row.ccwm:
            performanceData[row.teamNumber] = defaultPerformanceData
            continue
        performanceData[row.teamNumber] = {
            "True Skill": "N/A" if row.trueskill == "N/A" else float(row.trueskill),
            "CCWM": "N/A" if row.ccwm == "N/A" else float(row.ccwm),
            "Total Wins": row.totalWins,
            "Total Losses": row.totalLosses,
            "Total Ties": row.totalTies,
        }

    skillsData = {}
    for age_group in ["hs", "ms"]:
        with open(f"world-skill-standings-{age_group}.csv", encoding="utf8") as f:
            reader = csv.DictReader(f)
            next(reader)
            for row in reader:
                # print(row[10])
                if row['Event Region'] == "Chinese Taipei":
                    row['Event Region'] = "Taiwan"
                skillsData[row['Team Number']] = row

    # with open("matches.json", "r") as f:
    #     matchesData = json.load(f)
    divisions = {"high-school": ["Math", "Technology", "Science", "Engineering",
                 "Arts", "Innovate", "Spirit", "Design", "Research", "Opportunity"],
                 "middle-school": ["Science", "Technology", "Engineering", "Math", "Arts", "Opportunity"]}

    for age_group in ["high-school", "middle-school"]:
        teams = get_worlds_teams(age_group)
        for index, teamNum in enumerate(teams):
            teamSkillsData = skillsData.get(teamNum, None)
            if teamSkillsData is None:
                print(teamNum)
                teamInfo = team_name_to_team(teamNum)
                teamSkillsData = {}
                teamSkillsData['Event Region'] = teamInfo.region
                teamSkillsData['Team Name'] = teamInfo.name
                time.sleep(0.2)
            team = Team(
                skills_rank=teamSkillsData.get('Rank', "N/A"),
                skills_score_overall=teamSkillsData.get("Score", "N/A"),
                skills_score_autonomous=teamSkillsData.get(
                    'Autonomous Coding Skills', "N/A"),
                skills_score_driver=teamSkillsData.get("Driver Skills", "N/A"),
                number=teamNum,
                name=teamSkillsData.get('Team Name', "N/A"),
                true_skill=performanceData.get(teamNum, defaultPerformanceData)[
                    "True Skill"],
                region=teamSkillsData.get('Event Region', "N/A"),
                division=divisions[age_group][index %
                                              len(divisions[age_group])],
                ccwm=performanceData.get(teamNum, defaultPerformanceData)["CCWM"],
                win_count=performanceData.get(teamNum, defaultPerformanceData)[
                    "Total Wins"],
                loss_count=performanceData.get(teamNum, defaultPerformanceData)[
                    "Total Losses"],
                tie_count=performanceData.get(teamNum, defaultPerformanceData)[
                    "Total Ties"],
                age_group=age_group,
            )
            add_team(team)
    # with open("VRC-HS-Divisions.csv", encoding="utf8") as f:
    #     reader = csv.reader(f)
    #     next(reader)
    #     for row in reader:
    #         divisions[row[0]] = row[1]
    #         teamCCWMData = ccwmData.get(
    #             row[0], {"CCWM": "N/A", "OPR": "N/A", "DPR": "N/A"})
    #         teamWinrateData = winrateData.get(row[0], (0, 0, 0))
    #         teamSkillsData = skillsData.get(row[0], None)
    #         if teamSkillsData is None:
    #             teamInfo = team_name_to_team(row[0])
    #             teamSkillsData = ["N/A"] * 14
    #             teamSkillsData[13] = teamInfo.region
    #             teamSkillsData[11] = teamInfo.name
    #         teanTrueSkill = trueSkillData.get(row[0], "N/A")
    #         team = Team(
    #             skills_rank=teamSkillsData[0],
    #             skills_score_overall=teamSkillsData[1],
    #             skills_score_autonomous=teamSkillsData[2],
    #             skills_score_driver=teamSkillsData[3],
    #             number=row[0],
    #             name=teamSkillsData[11],
    #             true_skill=teanTrueSkill,
    #             region=teamSkillsData[13],
    #             division=row[1],
    #             ccwm=teamCCWMData["CCWM"],
    #             opr=teamCCWMData["OPR"],
    #             dpr=teamCCWMData["DPR"],
    #             win_count=teamWinrateData[0],
    #             loss_count=teamWinrateData[1],
    #             tie_count=teamWinrateData[2],
    #             age_group="high-school",
    #         )
    #         add_team(team)

    # with open("VRC-MS-Divisions.csv", encoding="utf8") as f:
    #     reader=csv.reader(f)
    #     next(reader)
    #     for row in reader:
    #         divisions[row[0]]=row[1]

    # with open("world-skill-standings-ms.csv", encoding="utf8") as f:
    #     reader=csv.reader(f)
    #     next(reader)
    #     for row in reader:
    #         # F(row[10])
    #         try:
    #             team=Team(
    #                 skills_rank=row[0],
    #                 skills_score_overall=row[1],
    #                 skills_score_autonomous=row[2],
    #                 skills_score_driver=row[3],
    #                 number=row[10],
    #                 name=row[11],
    #                 true_skill=teams.get(row[10], None),
    #                 region=row[13],
    #                 division=divisions.get(row[10], None),
    #                 ccwm=ccwmData.get(row[10], None)["CCWM"],
    #                 opr=ccwmData.get(row[10], None)["OPR"],
    #                 dpr=ccwmData.get(row[10], None)["DPR"],
    #                 win_count=winrateData.get(row[10], None)[0],
    #                 loss_count=winrateData.get(row[10], None)[1],
    #                 tie_count=winrateData.get(row[10], None)[2],
    #                 age_group="middle-school",
    #             )
    #         except Exception as e:
    #             print(e)
    #             print(row[10])
    #             continue
    #         add_team(team)


def get_prediction(match):
    for team in match['red']:
        if isinstance(team.true_skill, str):
            team.true_skill = [Rating().mu, Rating().sigma]
    for team in match['blue']:
        if isinstance(team.true_skill, str):
            team.true_skill = [Rating().mu, Rating().sigma]
    return predict_win(
        [
            [
                create_rating(match['red'][0].true_skill),
                create_rating(match['red'][1].true_skill)
            ],
            [
                create_rating(match['blue'][0].true_skill),
                create_rating(match['blue'][1].true_skill),
            ]
        ]
    )


def add_team(team):
    db.session.add(team)
    db.session.commit()


def get_team(number):
    return db.session.query(Team).filter_by(number=number).first()


def team_name_to_team(number):
    teamData = api_get("teams", params={"number": number})['data'][0]
    print(f"{teamData['number']} {teamData['id']}")
    team = Team(
        number=teamData['number'],
        id=teamData['id'],
        name=teamData['team_name'],
        region=teamData['location']['region'],
    )
    return team


def get_team_id(team):
    return api_get("teams", params={"number": team.number, "program": 1})['data'][0]['id']


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
            "event": "53690" if team.age_group == "high-school" else "53691",
        }
    )['data']
    print(team.id)
    for match in data:
        tempMatch = {
    'time': "N/A" if not match['scheduled'] else (datetime.strptime(
        match['scheduled'],
        "%Y-%m-%dT%H:%M:%S%z") -
        timedelta(
            hours=1)).strftime("%B %#d at %#I:%M %p"),
            'name': match['name'],
            'red': [],
             'blue': []}
        for alliance in match['alliances']:
            for team in alliance['teams']:
                team = team['team']
                tempMatch[alliance['color']].append(
                    get_team(team['name']))
        matches.append(tempMatch)
    return matches


def get_awards(team):
    awardData = {}
    data = api_get(
        f"teams/{team.id}/awards",
        params={
            "season": "181",
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


@ app.route("/team/<teamNumber>/", methods=["POST", "GET"])
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
        matches = get_matches(team)
        awards = get_awards(team)
    except Exception as e:
        print(e)
        return render_template("error.html", error="Team is not in VRC")
    matchOdds = []
    for match in matches:
        color = "red" if team in match['red'] else "blue"
        results = get_prediction(match)
        odds = results[0] if color == "red" else results[1]
        match['odds'] = f"{round(odds * 100, 1)}% chance you win"
        matchOdds.append(odds * 100)
        # matchOdds.append(
        #     (100 if get_color(
        #         team,
        #         match) != results['winner'] else results['odds'] * 2) -
        #     results['odds'])
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


@ app.route("/delete/<teamNumber>/", methods=["POST"])
def delete_comment(teamNumber):
    if request.method == "POST":
        db.session.query(Comment).filter_by(
            id=request.form['comment_id']).delete()
        db.session.commit()
        return redirect(url_for('view_team', teamNumber=teamNumber))


@ app.route("/team/", methods=["GET"])
@ app.route("/", methods=["POST", "GET"])
def view_index():
    divisions = {
        "high-school":
        {
            'All': [],
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
        },
        "middle-school":
        {
            'All': [],
            'Science': [],
            "Technology": [],
            "Engineering": [],
            "Math": [],
            "Arts": [],
            "Opportunity": [],
        }
    }
    for team in Team.query.all():
        if team.division:
            divisions[team.age_group][team.division].append(team)
            divisions[team.age_group]['All'].append(team)
    return render_template("index.html", divisions=divisions)


@ app.route('/favicon.ico')
def favicon():
    return url_for('static', filename='favicon.ico')


@ app.route('/webhook', methods=['POST'])
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


def get_worlds_teams(event):
    age_group_to_event = {
        "high-school": 53690,
        "middle-school": 53691
    }
    pageNum = 1
    data = True
    teams = []
    while data:
        data = api_get(
            f"events/{age_group_to_event[event]}/teams",
            params={
                "per_page": 250,
                "page": pageNum,
            }
        )['data']
        for team in data:
            teams.append(team['number'])
        pageNum += 1
    
    return teams

    divisions = ["Math", "Technology", "Science", "Engineering",
                 "Arts", "Innovate", "Spirit", "Design", "Research", "Opportunity"]
    # Set team divisions
    for index, teamNum in enumerate(teams):
        team = Team.query.filter_by(number=teamNum).first()
        if team:
            team.division = divisions[index % len(divisions)]
            db.session.commit()
        else:
            # create Team object
            team = team_name_to_team(teamNum)
            team.division = divisions[index % len(divisions)]
            add_team(team)


# regenerate DB
@ app.route("/regen/", methods=["GET"])
def regen():
    db.drop_all()
    db.create_all()
    load_teams_data()
    # update_divisions()
    return redirect(url_for('view_index'))


def regen_task():
    with app.app_context():
        db.drop_all()
        db.create_all()
        load_teams_data()


if __name__ == "__main__":

    moment = Moment(app)

    if os.environ.get('ENV') == 'prod':
        app.run(host="0.0.0.0", port=80)
    else:
        app.run(debug=True, host="0.0.0.0", port=5001)

if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler = BackgroundScheduler()
    job = scheduler.add_job(regen_task, 'interval', minutes=5)
    scheduler.start()
