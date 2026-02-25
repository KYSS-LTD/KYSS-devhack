const userRaw = localStorage.getItem('qb_user');
if (!userRaw) {
  window.location.href = '/login';
}
const user = userRaw ? JSON.parse(userRaw) : null;

const userLabel = document.getElementById('current-user');
const hostName = document.getElementById('host-name');
const joinName = document.getElementById('join-name');
const createMsg = document.getElementById('create-msg');
const joinMsg = document.getElementById('join-msg');

if (user) {
  userLabel.textContent = `Пользователь: ${user.username}`;
  hostName.value = user.username;
  joinName.value = user.username;
}

document.getElementById('logout-btn')?.addEventListener('click', () => {
  localStorage.removeItem('qb_user');
  localStorage.removeItem('qb_player');
  window.location.href = '/login';
});

document.getElementById('create-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  createMsg.textContent = 'Создаём игру...';
  const form = e.currentTarget;
  const payload = Object.fromEntries(new FormData(form).entries());
  payload.questions_per_team = Number(payload.questions_per_team);

  try {
    const res = await fetch('/games', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Ошибка создания игры');

    localStorage.setItem('qb_player', JSON.stringify({
      pin: data.pin,
      player_id: data.host_player_id,
      name: payload.host_name,
      is_host: true,
    }));
    window.location.href = `/game/${data.pin}`;
  } catch (err) {
    createMsg.textContent = err.message;
  }
});

document.getElementById('join-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  joinMsg.textContent = 'Подключаемся...';
  const form = e.currentTarget;
  const formData = Object.fromEntries(new FormData(form).entries());
  const pin = formData.pin.toUpperCase();

  try {
    const res = await fetch(`/games/${pin}/join`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name: formData.name}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Ошибка подключения');

    localStorage.setItem('qb_player', JSON.stringify({
      pin,
      player_id: data.player_id,
      name: formData.name,
      is_host: false,
    }));
    window.location.href = `/game/${pin}`;
  } catch (err) {
    joinMsg.textContent = err.message;
  }
});
