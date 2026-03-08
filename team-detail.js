const API_BASE = "http://localhost:8000";

// Official NBA logo + headshot CDN
function logoUrl(teamId) {
  return `https://cdn.nba.com/logos/nba/${teamId}/primary/L/logo.svg`;
}
function headshotUrl(playerId) {
  return `https://cdn.nba.com/headshots/nba/latest/260x190/${playerId}.png`;
}

function getTeamId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id");
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function fetchTeamData() {
  const rawId = getTeamId();
  if (!rawId) {
    document.body.innerHTML = "<p>Team not found</p>";
    return;
  }

  // The app primarily uses INTERNAL DB ids in URLs (1..30-ish),
  // but users sometimes paste NBA ids (16106127xx). We support both.
  const isLikelyNbaId = /^\d{9,}$/.test(String(rawId)) && Number(rawId) > 1600000000;

  const tbody = document.getElementById("roster-tbody");
  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">Loading roster…</td></tr>`;
  }

  let internalId = rawId;
  try {
    // Try direct (works for internal ids)
    const team = await fetchJson(`${API_BASE}/api/teams/${internalId}`);
    await displayTeamHeader(team);

    try {
      const players = await fetchJson(`${API_BASE}/api/teams/${internalId}/players`);
      displayRoster(players);
    } catch (rosterErr) {
      console.error("Roster error:", rosterErr);
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">Roster unavailable. Backend error: <code>${rosterErr.message}</code></td></tr>`;
      }
    }

  } catch (error) {
    // If user pasted an NBA id, resolve it to the internal DB id via /api/teams list.
    if (isLikelyNbaId) {
      try {
        const allTeams = await fetchJson(`${API_BASE}/api/teams`);
        const match = Array.isArray(allTeams)
          ? allTeams.find(t => String(t.nba_team_id) === String(rawId))
          : null;

        if (match && match.id) {
          internalId = match.id;
          const team = await fetchJson(`${API_BASE}/api/teams/${internalId}`);
          await displayTeamHeader(team);

          try {
            const players = await fetchJson(`${API_BASE}/api/teams/${internalId}/players`);
            displayRoster(players);
            return;
          } catch (rosterErr) {
            console.error("Roster error:", rosterErr);
            if (tbody) {
              tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">Roster unavailable. Backend error: <code>${rosterErr.message}</code></td></tr>`;
            }
            return;
          }
        }
      } catch (e2) {
        console.error("NBA id resolve failed:", e2);
      }
    }

    console.error("Error fetching team data:", error);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">Could not load team. Backend error: <code>${error.message}</code></td></tr>`;
    }
  }
}



async function loadFirstWorkingImage(urls) {
  for (const url of urls) {
    if (!url) continue;
    const ok = await new Promise((resolve) => {
      const test = new Image();
      // Avoid some hotlink/referrer issues on certain networks
      try { test.referrerPolicy = "no-referrer"; } catch (e) {}
      test.onload = () => resolve(true);
      test.onerror = () => resolve(false);
      test.src = url;
    });
    if (ok) return url;
  }
  return null;
}

function buildLogoCandidates(team) {
  const nbaId = team.nba_team_id || team.nbaId || null;
  const abbr = team.abbreviation || team.abbrev || "";
  const candidates = [];

  // If backend already provided a logo url, try it first.
  if (team.logo_url) candidates.push(team.logo_url);

  if (nbaId) {
    // "global" tends to be the most reliable path, but keep primary as fallback.
    candidates.push(`https://cdn.nba.com/logos/nba/${nbaId}/global/L/logo.svg`);
    candidates.push(`https://cdn.nba.com/logos/nba/${nbaId}/global/L/logo.png`);
    candidates.push(`https://cdn.nba.com/logos/nba/${nbaId}/primary/L/logo.svg`);
    candidates.push(`https://cdn.nba.com/logos/nba/${nbaId}/primary/L/logo.png`);
  }

  // Local fallbacks (only work if those files exist in your project)
  if (abbr) {
    candidates.push(`database/static/Logos/${abbr}.png`);
    candidates.push(`static/Logos/${abbr}.png`);
    candidates.push(`/static/Logos/${abbr}.png`);
  }

  return candidates;
}

async function displayTeamHeader(team) {
  const img = document.getElementById("team-logo-img");
  const fallback = document.getElementById("team-logo-fallback");

  const showImg = () => {
    img.style.display = "block";
    fallback.style.display = "none";
  };
  const showFallback = () => {
    img.style.display = "none";
    fallback.style.display = "inline";
  };

  // Build candidate urls and pick the first one that actually loads.
  const candidates = buildLogoCandidates(team);
  const chosen = await loadFirstWorkingImage(candidates);

  if (chosen) {
    // Set handlers BEFORE setting src (covers cached + async decoding)
    img.onerror = () => showFallback();
    img.onload = () => showImg();

    // Some browsers won't fire onload for cached images reliably if we keep display:none.
    // Set src, then if it's already complete, show immediately.
    img.src = chosen;

    // If cached, show immediately
    if (img.complete && img.naturalWidth > 0) showImg();
    else showImg(); // show container even while decoding
  } else {
    showFallback();
  }

  document.getElementById('team-arena').textContent = team.arena ? `Arena: ${team.arena}` : 'Arena: Arena TBD';
  document.getElementById("team-name").textContent = team.full_name || team.name || "Team";
  document.getElementById("team-record").textContent = `${team.wins ?? 0}W - ${team.losses ?? 0}L`;

  const wins = Number(team.wins || 0);
  const losses = Number(team.losses || 0);
  const winRate = wins + losses > 0 ? ((wins / (wins + losses)) * 100).toFixed(1) : "0.0";
  document.getElementById("team-win-rate").textContent = `Win Rate: ${winRate}%`;
}



function displayRoster(players) {
  const tbody = document.getElementById("roster-tbody");
  tbody.innerHTML = "";

  if (!Array.isArray(players) || players.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="padding:16px;">No roster returned.</td></tr>`;
    return;
  }

  players.forEach((p) => {
    const row = document.createElement("tr");

    const playerId = p.id || 0;
    const imgHtml = playerId
      ? `<img src="${p.headshot_url || headshotUrl(playerId)}" alt="${p.name}" style="width:48px;height:36px;object-fit:cover;border-radius:6px;" onerror="this.style.display='none'">`
      : "";

    row.innerHTML = `
      <td style="padding:10px 12px;">${imgHtml}</td>
      <td style="padding:10px 12px;">${p.jersey ?? "-"}</td>
      <td style="padding:10px 12px; font-weight:600;">${p.name ?? ""}</td>
      <td style="padding:10px 12px;">${p.position ?? "-"}</td>
      <td style="padding:10px 12px;">${p.height ?? "-"}</td>
    `;
    tbody.appendChild(row);
  });
}

fetchTeamData();
