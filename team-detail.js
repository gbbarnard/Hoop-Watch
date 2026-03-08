const teamLogos = {
    'ATL': 'https://cdn.nba.com/logos/nba/1610612737/primary/L/logo.svg',
    'BOS': 'https://cdn.nba.com/logos/nba/1610612738/primary/L/logo.svg',
    'BKN': 'https://cdn.nba.com/logos/nba/1610612751/primary/L/logo.svg',
    'CHA': 'https://cdn.nba.com/logos/nba/1610612766/primary/L/logo.svg',
    'CHI': 'https://cdn.nba.com/logos/nba/1610612741/primary/L/logo.svg',
    'CLE': 'https://cdn.nba.com/logos/nba/1610612739/primary/L/logo.svg',
    'DAL': 'https://cdn.nba.com/logos/nba/1610612742/primary/L/logo.svg',
    'DEN': 'https://cdn.nba.com/logos/nba/1610612743/primary/L/logo.svg',
    'DET': 'https://cdn.nba.com/logos/nba/1610612765/primary/L/logo.svg',
    'GSW': 'https://cdn.nba.com/logos/nba/1610612744/primary/L/logo.svg',
    'HOU': 'https://cdn.nba.com/logos/nba/1610612745/primary/L/logo.svg',
    'IND': 'https://cdn.nba.com/logos/nba/1610612754/primary/L/logo.svg',
    'LAC': 'https://cdn.nba.com/logos/nba/1610612746/primary/L/logo.svg',
    'LAL': 'https://cdn.nba.com/logos/nba/1610612747/primary/L/logo.svg',
    'MEM': 'https://cdn.nba.com/logos/nba/1610612763/primary/L/logo.svg',
    'MIA': 'https://cdn.nba.com/logos/nba/1610612748/primary/L/logo.svg',
    'MIL': 'https://cdn.nba.com/logos/nba/1610612749/primary/L/logo.svg',
    'MIN': 'https://cdn.nba.com/logos/nba/1610612750/primary/L/logo.svg',
    'NOP': 'https://cdn.nba.com/logos/nba/1610612740/primary/L/logo.svg',
    'NYK': 'https://cdn.nba.com/logos/nba/1610612752/primary/L/logo.svg',
    'OKC': 'https://cdn.nba.com/logos/nba/1610612760/primary/L/logo.svg',
    'ORL': 'https://cdn.nba.com/logos/nba/1610612753/primary/L/logo.svg',
    'PHI': 'https://cdn.nba.com/logos/nba/1610612755/primary/L/logo.svg',
    'PHX': 'https://cdn.nba.com/logos/nba/1610612756/primary/L/logo.svg',
    'POR': 'https://cdn.nba.com/logos/nba/1610612757/primary/L/logo.svg',
    'SAC': 'https://cdn.nba.com/logos/nba/1610612758/primary/L/logo.svg',
    'SAS': 'https://cdn.nba.com/logos/nba/1610612759/primary/L/logo.svg',
    'TOR': 'https://cdn.nba.com/logos/nba/1610612761/primary/L/logo.svg',
    'UTA': 'https://cdn.nba.com/logos/nba/1610612762/primary/L/logo.svg',
    'WAS': 'https://cdn.nba.com/logos/nba/1610612764/primary/L/logo.svg'
};

function getTeamId() {
    const params = new URLSearchParams(window.location.search);
    return params.get('id');
}

async function fetchTeamData() {
    const teamId = getTeamId();
    if (!teamId) {
        document.body.innerHTML = '<p>Team not found</p>';
        return;
    }
    
    try {
        const [teamResponse, playersResponse] = await Promise.all([
            fetch(`/api/teams/${teamId}`),
            fetch(`/api/teams/${teamId}/players`)
        ]);
        
        const team = await teamResponse.json();
        const players = await playersResponse.json();
        
        displayTeamHeader(team);
        displayRoster(players);
    } catch (error) {
        console.error('Error fetching team data:', error);
    }
}

function displayTeamHeader(team) {
    const logoContainer = document.getElementById('team-logo');
    const teamAbbr = team.abbreviation;
    const logoUrl = teamLogos[teamAbbr];
    
    if (logoUrl) {
        logoContainer.innerHTML = `<img src="${logoUrl}" alt="${team.full_name}" style="width: 120px; height: 120px;">`;
    } else {
        logoContainer.textContent = '🏀';
    }
    
    document.getElementById('team-name').textContent = team.full_name;
    document.getElementById('team-record').textContent = `${team.wins}W - ${team.losses}L`;
    
    const winRate = team.wins + team.losses > 0 
        ? (team.wins / (team.wins + team.losses) * 100).toFixed(1) 
        : 0;
    document.getElementById('team-win-rate').textContent = `Win Rate: ${winRate}%`;
}

function displayRoster(players) {
    const tbody = document.getElementById('roster-tbody');
    tbody.innerHTML = '';
    
    players.forEach(player => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${player.jersey}</td>
            <td>${player.name}</td>
            <td>${player.position}</td>
            <td>${player.height}</td>
        `;
        tbody.appendChild(row);
    });
}

fetchTeamData();