// Vex Worlds Scouting — static SPA, UI matching the original Flask templates.

const API = 'https://www.robotevents.com/api/v2/';
const TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiZjc5MzgwNmVlOTU3ZmEyYzkyODk3YTdjMTcxOGE1Zjc2ZDZhNTcxODJlM2U5NmI4Mjc5OWIwNjllMjE3ZDQ4ZjJmY2FlOTdjYmJmM2QzMDIiLCJpYXQiOjE2NzQ3OTg5OTAuMDk1NDkxOSwibmJmIjoxNjc0Nzk4OTkwLjA5NTQ5NTksImV4cCI6MjYyMTU3MDE5MC4wOTIwNDM5LCJzdWIiOiI4NDUxOSIsInNjb3BlcyI6W119.KglMyufEjUZ8WceNQJ2GMWj5e2qQsya1QPm7jHBhYg0cqOgCmWi2UqnaMqLsmJubv-Y5Mv-IWjkQ5E6bD8l57qGsvtGllvms_jW4KmdD8w9iDMo8YFNmuMN4OTt00gmOgOoBPZcSeYVwXJnQoX_WWOlxIyeGPKI11bxUNfJXr9xD4NhTG0wSQyS6yS53hh1XEJtDRzUw7Eeoq_PVWIzipmzOqeFnx2NxHOeRpNQj9dGKNBPiTy1M42wiNi8bErONBfwikddQsk_xN2ePfqC1zsM9qL34pWm3enNPqVn92zTzp1fUiwQcBdPttWt-Y52Gy-VUYVnm5ZMq8s5Xk8pB2op5k9EOTl1-8r1BnSYJepwsJSaDRr_JsuhwAvVTisemSKN7bM5dGjLcb8dr6peQLSXUMnedjmf2Kq3AjEOy-CeazL9tAOQ4kqHU75eNnWJek1J9ulSbuZiv3q3xNlKz_TWzLVItyKPB7JMZPqEmpoqnnUev1ZLNAYyZZDdG0sbRlnjP-Ad8paeoYSASpahoKMchc2FMVM3KaWa69XbKEQJ8sDsP3b0gLcXB_a_uq4NWMHm-0P9yqCGPOuz0NYzLGBfN-Kvq2GUzWxSbixxVp952ESdsiGIARq0yFn0c3Lvfp35UhjuggWHuFnGmVnqYCNjSMqBmWaP6K_BrxP39NMc';

const SEASONS = { V5RC: 197, VURC: 198 };

let DATA;
const BY_NUMBER = {};
const APP = document.getElementById('app');

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

async function reApi(path, params = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v)) v.forEach(x => qs.append(k, x));
    else qs.append(k, v);
  }
  const r = await fetch(API + path + (qs.toString() ? '?' + qs : ''), {
    headers: { Authorization: 'Bearer ' + TOKEN, 'accept-language': 'en' },
  });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

async function reApiAll(path, params = {}) {
  let page = 1, all = [];
  while (true) {
    const d = await reApi(path, { ...params, page, per_page: 250 });
    all = all.concat(d.data);
    if (d.data.length < 250) return all;
    page++;
  }
}

function fmtMatchTime(iso) {
  if (!iso) return 'N/A';
  // Match the original's "April 22 at 1:28 PM" format, US locale
  return new Date(iso).toLocaleString('en-US', {
    month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true,
  }).replace(',', ' at');
}

function navigate(path) {
  history.pushState({}, '', path);
  route();
}

// ---------- routing ----------

function route() {
  const p = location.pathname.replace(/\/+$/, '') || '/';
  let m;
  if ((m = p.match(/^\/team\/([^\/]+)$/))) {
    return showTeam(decodeURIComponent(m[1]).toUpperCase());
  }
  return showIndex();
}

// ---------- shared: team number sort (from original template) ----------
function customSort(sortName, sortOrder, data) {
  const cmpNum = (a, b) => {
    let aEl = document.createElement('div'); aEl.innerHTML = a;
    let bEl = document.createElement('div'); bEl.innerHTML = b;
    let at = aEl.textContent, bt = bEl.textContent;
    const aNum = parseInt(at.substring(0, at.length - 1));
    const bNum = parseInt(bt.substring(0, bt.length - 1));
    if (aNum === bNum) {
      return at.charCodeAt(at.length - 1) - bt.charCodeAt(bt.length - 1);
    }
    return aNum - bNum;
  };
  if (sortName === 'number') {
    data.sort((a, b) => cmpNum(a.number, b.number));
  } else if (sortName === 'win_rate') {
    data.sort((a, b) => parseFloat(String(a.win_rate).replace('%','')) - parseFloat(String(b.win_rate).replace('%','')));
  } else {
    data.sort((a, b) => {
      let x = a[sortName], y = b[sortName];
      if (x == 'N/A') x = Number.NEGATIVE_INFINITY;
      if (y == 'N/A') y = Number.NEGATIVE_INFINITY;
      x = parseFloat(x); y = parseFloat(y);
      if (sortName === 'rank') {
        if (isNaN(x)) return 1;
        if (isNaN(y)) return -1;
      }
      if (isNaN(x)) return -1;
      if (isNaN(y)) return 1;
      return x - y;
    });
  }
  if (sortOrder === 'desc') data.reverse();
}
window.customSort = customSort;

// ---------- index view ----------

function rowForTeam(t) {
  const s = t.skills || {};
  const w = t.wins, l = t.losses, ti = t.ties;
  const total = w + l + ti;
  const wlt = total > 0 ? `${w} / ${l} / ${ti}` : 'N/A';
  const win_rate = total > 0 ? `${((w / total) * 100).toFixed(1)}%` : 'N/A';
  return {
    number: `<a href="/team/${encodeURIComponent(t.number)}/" data-link>${esc(t.number)}</a>`,
    div: esc(t.division || 'N/A'),
    name: esc(t.name || 'N/A'),
    region: esc(t.region || 'N/A'),
    rank: s.rank != null ? s.rank : 'N/A',
    score: s.score != null ? s.score : 'N/A',
    true_skill: 'N/A',
    ccwm: 'N/A',
    wlt,
    win_rate,
  };
}

// tableId -> row data, populated during render, consumed when initializing bootstrap-table.
const PENDING_TABLES = new Map();

function buildDivisionTables(event) {
  const divs = ['All', ...event.divisions];
  const navItems = divs.map(d => `
    <li class="nav-item" role="presentation">
      <button class="nav-link ${d === 'All' ? 'active' : ''}"
              data-bs-toggle="tab"
              data-bs-target="#${event.key}-${cssId(d)}-pane"
              type="button" role="tab">${esc(d)}</button>
    </li>`).join('');

  const panes = divs.map(d => {
    const teams = d === 'All' ? event.teams : event.teams.filter(t => t.division === d);
    const tableId = `tbl-${event.key}-${cssId(d)}`;
    PENDING_TABLES.set(tableId, teams.map(rowForTeam));
    const showDiv = d === 'All';
    return `
      <div class="tab-pane fade ${d === 'All' ? 'show active' : ''}"
           id="${event.key}-${cssId(d)}-pane" role="tabpanel">
        <table class="table table-hover" id="${tableId}"
               data-toggle="table"
               data-search="true"
               data-show-columns="true"
               data-custom-sort="customSort">
          <thead>
            <tr>
              <th data-field="number" data-sortable="true">Number</th>
              ${showDiv ? '<th data-field="div" data-searchable="false">Division</th>' : ''}
              <th data-field="name">Name</th>
              <th data-field="region">Region</th>
              <th data-field="rank" data-sortable="true" data-searchable="false">Skills Rank</th>
              <th data-field="score" data-sortable="true" data-searchable="false">Skills Score</th>
              <th data-field="true_skill" data-sortable="true" data-searchable="false">True Skill</th>
              <th data-field="ccwm" data-sortable="true" data-searchable="false">CCWM</th>
              <th data-field="wlt" data-sortable="false" data-searchable="false">Win/Loss/Tie</th>
              <th data-field="win_rate" data-sortable="true" data-searchable="false">Win Rate</th>
            </tr>
          </thead>
        </table>
      </div>`;
  }).join('');

  return `
    <ul class="nav nav-tabs" role="tablist">${navItems}</ul>
    <div class="tab-content">${panes}</div>`;
}

function cssId(s) {
  return s.replace(/[^A-Za-z0-9_-]/g, '_');
}

function showIndex() {
  document.title = 'Vex Scouting App';

  // Top-level: age group tabs
  const topNav = DATA.events.map((e, i) => `
    <li class="nav-item" role="presentation">
      <button class="nav-link ${i === 0 ? 'active' : ''}"
              id="${e.key}-top-tab"
              data-bs-toggle="tab"
              data-bs-target="#${e.key}-top-pane"
              type="button" role="tab">${esc(e.label)}</button>
    </li>`).join('');

  const topPanes = DATA.events.map((e, i) => `
    <div class="tab-pane fade ${i === 0 ? 'show active' : ''}"
         id="${e.key}-top-pane" role="tabpanel">
      ${buildDivisionTables(e)}
    </div>`).join('');

  APP.innerHTML = `
    <ul class="nav nav-tabs" role="tablist">${topNav}</ul>
    <div class="tab-content">${topPanes}</div>`;

  // Activate bootstrap-table with in-memory data for each table.
  for (const [tableId, data] of PENDING_TABLES.entries()) {
    // eslint-disable-next-line no-undef
    $('#' + tableId).bootstrapTable({ data });
  }
  PENDING_TABLES.clear();
}

// ---------- team detail view ----------

async function showTeam(number) {
  const entry = BY_NUMBER[number];
  if (!entry) {
    APP.innerHTML = `<div class="container py-4">
      <div class="alert alert-warning">
        Team <strong>${esc(number)}</strong> is not registered at Worlds this season.
      </div>
      <a href="/" data-link>&larr; back</a>
    </div>`;
    return;
  }
  const { team, event } = entry;
  document.title = team.number;
  const s = team.skills || {};

  APP.innerHTML = `
    <div class="container-fluid pt-3">
      <h4 class="display-4">Matches</h4>
      <p>RobotEvents: <a target="_blank" href="https://www.robotevents.com/teams/${esc(event.program)}/${esc(team.number)}">${esc(team.number)}</a></p>
      <p>Region: ${esc(team.region || 'N/A')}</p>
      <p>Division: ${esc(team.division || 'N/A')}</p>
      <table class="table table-hover" id="matches-table">
        <tr><td class="text-muted" colspan="7">Loading matches&hellip;</td></tr>
      </table>

      <h4 class="display-4 mb-3">Awards</h4>
      <table class="table table-hover">
        <tr>
          <th>World Skills Rank</th>
          <th>Best Driver</th>
          <th>Best Prog</th>
          <th>Best Score</th>
        </tr>
        <tr>
          <td>${s.rank != null ? s.rank : 'N/A'}</td>
          <td>${s.driver != null ? s.driver : 'N/A'}</td>
          <td>${s.auto != null ? s.auto : 'N/A'}</td>
          <td>${s.score != null ? s.score : 'N/A'}</td>
        </tr>
      </table>
      <br>
      <table class="table table-bordered" id="awards-table">
        <tbody><tr><td class="text-muted">Loading awards&hellip;</td></tr></tbody>
      </table>
    </div>`;

  loadMatches(team, event);
  loadAwards(team, event);
}

async function loadMatches(team, event) {
  const tbl = document.getElementById('matches-table');
  try {
    const matches = await reApiAll(`teams/${team.id}/matches`, { 'event[]': event.id });
    matches.sort((a, b) => (a.scheduled || '').localeCompare(b.scheduled || ''));

    // Determine alliance size (V5RC = 2, VURC = 3) from first match's data.
    const allianceSize = matches.length
      ? Math.max(...matches.flatMap(m => m.alliances.map(a => a.teams.length)))
      : 2;

    const header = `<tr>
      <th>Time</th>
      <th>Name</th>
      ${Array.from({length: allianceSize}, (_, i) => `<th>Red ${i+1}</th>`).join('')}
      ${Array.from({length: allianceSize}, (_, i) => `<th>Blue ${i+1}</th>`).join('')}
    </tr>`;

    const cell = (num, color) => {
      const bold = num === team.number ? 'fw-bold ' : '';
      const cls = color === 'red' ? 'text-danger' : 'text-primary';
      return `<td class="${bold}"><a class="${cls}" href="/team/${encodeURIComponent(num)}/" data-link>${esc(num)}</a></td>`;
    };

    let body;
    if (matches.length === 0) {
      body = `<tr><td colspan="${2 + allianceSize * 2}">No matches found</td></tr>`;
    } else {
      body = matches.map(m => {
        const red = m.alliances.find(a => a.color === 'red');
        const blue = m.alliances.find(a => a.color === 'blue');
        const redNums = red.teams.map(x => x.team.name);
        const blueNums = blue.teams.map(x => x.team.name);
        while (redNums.length < allianceSize) redNums.push('');
        while (blueNums.length < allianceSize) blueNums.push('');
        return `<tr>
          <td>${esc(fmtMatchTime(m.started || m.scheduled))}</td>
          <td>${esc(m.name)}</td>
          ${redNums.map(n => n ? cell(n, 'red') : '<td></td>').join('')}
          ${blueNums.map(n => n ? cell(n, 'blue') : '<td></td>').join('')}
        </tr>`;
      }).join('');
    }
    tbl.innerHTML = header + body;
  } catch (e) {
    tbl.innerHTML = `<tr><td colspan="7" class="text-danger">Failed to load matches: ${esc(e.message)}</td></tr>`;
  }
}

async function loadAwards(team, event) {
  const tbl = document.getElementById('awards-table');
  try {
    const season = SEASONS[event.program];
    const awards = await reApiAll(`teams/${team.id}/awards`, { 'season[]': season });
    if (!awards.length) {
      tbl.innerHTML = '<tbody><tr><td class="text-muted">No awards this season.</td></tr></tbody>';
      return;
    }
    const byEvent = new Map();
    for (const a of awards) {
      const k = a.event.code || a.event.id;
      if (!byEvent.has(k)) byEvent.set(k, { name: a.event.name, code: a.event.code, list: [] });
      byEvent.get(k).list.push(a.title);
    }
    const rows = [];
    for (const ev of byEvent.values()) {
      ev.list.forEach((title, i) => {
        if (i === 0) {
          rows.push(`<tr>
            <th class="table-info" scope="row" rowspan="${ev.list.length}">
              <a class="text-dark" target="_blank"
                 href="https://www.robotevents.com/robot-competitions/vex-robotics-competition/${esc(ev.code)}.html">${esc(ev.name)}</a>
            </th>
            <td>${esc(title)}</td>
          </tr>`);
        } else {
          rows.push(`<tr><td>${esc(title)}</td></tr>`);
        }
      });
    }
    tbl.innerHTML = `<tbody>${rows.join('')}</tbody>`;
  } catch (e) {
    tbl.innerHTML = `<tbody><tr><td class="text-danger">Failed to load awards: ${esc(e.message)}</td></tr></tbody>`;
  }
}

// ---------- boot ----------

async function boot() {
  try {
    const r = await fetch('/static/teams.json');
    DATA = await r.json();
  } catch (e) {
    APP.innerHTML = `<div class="alert alert-danger m-3">Failed to load teams data.</div>`;
    return;
  }
  for (const ev of DATA.events) {
    for (const t of ev.teams) {
      BY_NUMBER[t.number] = { team: t, event: ev };
    }
  }

  document.getElementById('searchForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const q = document.getElementById('searchBar').value.trim().toUpperCase();
    if (q) navigate(`/team/${encodeURIComponent(q)}/`);
  });

  document.body.addEventListener('click', (e) => {
    const a = e.target.closest('a[data-link]');
    if (!a) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    navigate(a.getAttribute('href'));
    window.scrollTo(0, 0);
  });

  window.addEventListener('popstate', route);
  route();
}

boot();
