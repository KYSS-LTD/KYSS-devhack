const userRaw = localStorage.getItem('qb_user');
if (!userRaw) {
  window.location.href = '/login';
}
const user = userRaw ? JSON.parse(userRaw) : null;

const msg = document.getElementById('profile-msg');
const topicsEl = document.getElementById('recent-topics');
const teammatesEl = document.getElementById('teammates');

document.getElementById('logout-btn')?.addEventListener('click', () => {
  localStorage.removeItem('qb_user');
  localStorage.removeItem('qb_player');
  window.location.href = '/login';
});

async function loadProfile() {
  try {
    const res = await fetch(`/users/${user.user_id}/stats`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Не удалось загрузить профиль');

    document.getElementById('profile-username').textContent = `Игрок: ${data.username}`;
    document.getElementById('games-played').textContent = data.games_played;
    document.getElementById('games-finished').textContent = data.games_finished;
    document.getElementById('wins').textContent = data.wins;
    document.getElementById('win-rate').textContent = `${data.win_rate}%`;
    document.getElementById('avg-score').textContent = data.average_team_score;
    document.getElementById('favorite-team').textContent = data.favorite_team || '-';

    topicsEl.innerHTML = '';
    if (data.recent_topics.length === 0) {
      topicsEl.innerHTML = '<li class="muted">Пока нет сыгранных игр</li>';
    } else {
      data.recent_topics.forEach((topic) => {
        const li = document.createElement('li');
        li.textContent = topic;
        topicsEl.appendChild(li);
      });
    }

    teammatesEl.innerHTML = '';
    if (data.frequent_teammates.length === 0) {
      teammatesEl.innerHTML = '<li class="muted">Пока недостаточно данных</li>';
    } else {
      data.frequent_teammates.forEach((mate) => {
        const li = document.createElement('li');
        li.textContent = `${mate.name} — ${mate.games_together} игр`;
        teammatesEl.appendChild(li);
      });
    }
  } catch (err) {
    msg.textContent = err.message;
  }
}

loadProfile();
