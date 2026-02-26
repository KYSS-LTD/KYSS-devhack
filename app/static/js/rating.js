const list = document.getElementById('rating-list');
const msg = document.getElementById('rating-msg');

(async function loadRating() {
  try {
    const res = await fetch('/rating/data');
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Не удалось загрузить рейтинг');
    list.innerHTML = '';
    data.rows.forEach((row) => {
      const li = document.createElement('li');
      li.textContent = `${row.username} — побед: ${row.wins}, завершено игр: ${row.games_finished}`;
      list.appendChild(li);
    });
  } catch (err) {
    msg.textContent = err.message;
  }
})();
